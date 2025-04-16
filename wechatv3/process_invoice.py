import csv
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import pyautogui
import pyperclip
from pyautogui import ImageNotFoundException
from pywinauto import Application

from wechatv3.global_var import global_pause
from wechatv3.gui_msg import log_message
from wechatv3.logger_config import LoggerManager, InvoiceLoggerAdapter
from .common import get_config

logger = LoggerManager().get_logger()
_invoice_logger = None

class ResultType(str, Enum):
    SUCCESS = '已完成'
    FAIL = '操作失败'


@dataclass
class ProcessResult:
    status: ResultType  # 比如：'已完成'、'操作失败'
    reason: Optional[str] = ''

    @classmethod
    def success(cls, reason: str = '') -> 'ProcessResult':
        return cls(ResultType.SUCCESS, reason)

    @classmethod
    def fail(cls, reason: str) -> 'ProcessResult':
        return cls(ResultType.FAIL, reason)

    def is_success(self) -> bool:
        return self.status == '已完成'

    def __str__(self):
        return f"[{self.status.value}] {self.reason}"


class InvoiceProcessor:
    def __init__(self, wechat_client):
        self.wechat_client = wechat_client
        self.worker = InvoiceAutomationWorker(wechat_client)

        logger.info("任务实例初始化")

    def _read_pending_file(self):
        pending_file = os.path.join(get_config().base.pending_path, get_config().base.pending_file_name)
        if not os.path.exists(pending_file):
            logger.error("找不到待处理文件")
            log_message("找不到待处理文件")
            return None, None

        # 读取所有待处理数据（跳过表头）
        with open(pending_file, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = [row for row in reader if row and any(field.strip() for field in row)]
            if len(rows) <= 1:
                return None, None

            header = rows[0]
            data_rows = rows[1:]

        return header, data_rows

    def save_processed(self, invoice_id, doc_type, sender, raw_msg, status, reason):
        processed_file = os.path.join(get_config().base.processed_path, get_config().base.processed_file_name)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if os.path.exists(processed_file):
            with open(processed_file, 'a', newline='', encoding='utf-8-sig') as f:
                if reason is not None:
                    if isinstance(reason, Exception):
                        reason = str(reason)
                    reason = reason.replace('\n', ' ').replace(',', '，').strip()
                else:
                    reason = ''
                f.write(f"{invoice_id},{doc_type},{timestamp},{sender},{status},{raw_msg},{reason}\n")

    def _process_one_invoice(self):
        global _invoice_logger
        result: ProcessResult | None = None

        header, data_rows = self._read_pending_file()
        if header is None or data_rows is None:
            logger.info("没有待处理数据")
            log_message("没有待处理数据")
            return

        invoice_id, doc_type, timestamp, sender, raw_message = data_rows[0]

        _invoice_logger = LoggerManager().get_invoice_logger(invoice_id)

        _invoice_logger.info(f"开始处理单据: {invoice_id}")
        log_message(f"开始处理单据: {invoice_id}")

        try:
            start_time = time.time()

            result = self.worker.do_process_invoices(invoice_id, doc_type)

            duration = int(time.time() - start_time)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            result_text = (
                f"单据号: {invoice_id}\n"
                f"单据类型: {doc_type}\n"
                f"处理开始时间: {now}\n"
                f"处理时长: {duration} 秒\n"
                f"状态: {result.status.value}\n"
                f"备注信息: {result.reason}\n"
                f"源消息: {raw_message}\n"
            )

            # 结果写入文件
            today_dir = datetime.now().strftime("%Y%m%d")
            result_dir = os.path.join(get_config().base.base_result_dir, today_dir)
            os.makedirs(result_dir, exist_ok=True)

            time_part = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").strftime("%H%M%S")
            result_file_path = os.path.join(result_dir, f"{invoice_id}_{time_part}.txt")

            with open(result_file_path, "w", encoding="utf-8") as f:
                f.write(result_text)

            _invoice_logger.info(f"结果保存在: {result_file_path}")
            log_message(f"结果保存在: {result_file_path}")

            # 从 CSV 移除已处理项
            header1, data_rows1 = self._read_pending_file()
            remaining = [header1] + data_rows1[1:]
            pending_path = os.path.join(get_config().base.pending_path, get_config().base.pending_file_name)
            with open(pending_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerows(remaining)

            self.save_processed(invoice_id=invoice_id, doc_type=doc_type, sender=sender, raw_msg=raw_message,
                                status=result.status.value, reason=result.reason)

            _invoice_logger.info(f"操作完成: {invoice_id}")
            log_message(f"操作完成: {invoice_id}")
        except Exception as e:
            _invoice_logger.error(f"单据操作失败: {invoice_id}，{e}")
            log_message(f"单据操作失败: {invoice_id}，{e}")
            self.save_processed(invoice_id=invoice_id, doc_type=doc_type, sender=sender, raw_msg=raw_message,
                                status=result.status.value, reason=result.reason)

        time.sleep(get_config().base.sleep_time)

    def start(self, msg_queue: queue.Queue, keep_remote: threading.Event):
        starting = False
        """启动自动处理任务"""
        while True:
            global_pause.wait()
            time.sleep(0.5)
            if not starting:
                log_message("自动处理任务已启动")
                logger.info("自动处理任务已启动")
                starting = True

            try:
                data = msg_queue.get(timeout=3)
                keep_remote.clear()
                logger.info(f"开始处理单据：{data}")
                self._process_one_invoice()
            except queue.Empty:
                if not keep_remote.is_set():
                    keep_remote.set()

    def keep_remote_alive(self, keep_remote: threading.Event):
        def do_keep():
            logger.info(f"无任务，远程保活中")
            log_message(f"无任务，远程保活中")
            self.worker.bring_window_to_front()
            searchx, searchy = self.worker.find_search_input()
            pyautogui.moveTo(searchx, searchy, 0.3)
            pyautogui.doubleClick(searchx, searchy)
            pyautogui.press('backspace')
            logger.info(f"执行防断连点击操作，位置: {searchx}, {searchy}")

        while True:
            try:
                global_pause.wait()
                keep_remote.wait()
                if not keep_remote.is_set():
                    logger.info(f"有任务，远程保活停止")
                    log_message(f"有任务，远程保活停止")
                do_keep()
            except Exception as e:
                pass
            time.sleep(10)


class InvoiceAutomationWorker:
    def __init__(self, wechat_client):
        self.wechat_client = wechat_client
        self.image_paths = get_config().paths  # 字典形式管理路径

        pyautogui.PAUSE = 0.4
        pyautogui.FAILSAFE = False

    def safe_locate_center(self, image_key, confidence=0.9, grayscale=False, min_search_time=3):
        image_path = self.image_paths.get(image_key)
        try:
            return pyautogui.locateCenterOnScreen(image_path, confidence=confidence, grayscale=grayscale,
                                                  minSearchTime=min_search_time)
        except ImageNotFoundException:
            logger.error(f"未找到元素: {image_path}")
            return None

    # 将远程桌面置于顶层
    def bring_window_to_front(self, window_title=get_config().base.get('remote_win_name')):
        global_pause.wait()
        try:
            app = Application().connect(title=window_title)
            window = app.window(title=window_title)
            window.set_focus()  # 设置窗口为最上层
            logger.info(f"窗口 '{window_title}' 已被设置为最上层")
        except Exception as e:
            logger.error(f"找不到窗口 '{window_title}'")
            log_message(f"找不到窗口 '{window_title}'")
            raise e

    # 找输入框输入单号
    def find_search_input(self):
        global_pause.wait()
        pyautogui.sleep(2)
        searchx, searchy = self.safe_locate_center('search_icon')
        pyautogui.moveTo(searchx - 60, searchy)
        return searchx - 60, searchy

    def valid_invoice_id(self, invoice_id):
        global_pause.wait()
        fhdhx, fhdhy = self.safe_locate_center('fahuodanhao')
        _invoice_logger.info(f"发货单号的位置: {fhdhx}, {fhdhy}")
        pyautogui.moveTo(fhdhx + 80, fhdhy, 0.5)
        pyautogui.sleep(2)
        pyautogui.doubleClick(fhdhx + 80, fhdhy, interval=0.1)
        pyautogui.sleep(0.5)
        _invoice_logger.info(f"复制前的值: {pyperclip.paste()}")
        log_message(f"复制前的值: {pyperclip.paste()}")
        pyautogui.hotkey('ctrl', 'c')
        _invoice_logger.info(f"复制后的值: {pyperclip.paste()}")
        log_message(f"复制后的值: {pyperclip.paste()}")
        time.sleep(0.5)
        pyautogui.doubleClick(fhdhx + 80, fhdhy, interval=0.1)
        pyautogui.hotkey('ctrl', 'c')
        value = pyperclip.paste()
        return value == invoice_id, value

    def do_process_invoices(self, invoice_id, doc_type) -> ProcessResult:
        global _invoice_logger
        global_pause.wait()
        _invoice_logger = LoggerManager().get_invoice_logger(invoice_id)
        from_path = self.safe_locate_center
        log = _invoice_logger
        log.info(f'单据类型: {doc_type}')
        log_message(f'单据: {invoice_id} 类型: {doc_type}')
        try:
            # 将远程桌面置于最顶层
            self.bring_window_to_front()
            # 找输入框输入单号进行查询
            searchx, searchy = self.find_search_input()

            def input_invoice_no():
                pyautogui.doubleClick(searchx, searchy, interval=0.1)
                pyautogui.sleep(0.5)
                pyautogui.keyDown('backspace')
                time.sleep(3)
                pyautogui.keyUp('backspace')
                pyautogui.write(invoice_id, 0.15)  # 输入单号
                pyautogui.press('enter')

            global_pause.wait()
            input_invoice_no()

            # 提示找不到则直接返回并记录
            global_pause.wait()
            if from_path('zbd'):
                qdlocation = from_path('queding')
                pyautogui.moveTo(qdlocation.x, qdlocation.y)
                pyautogui.click(qdlocation.x, qdlocation.y)
                log.info("提示未找到单据")
                log_message(f"[{invoice_id}] 提示未找到单据")
                return ProcessResult.success('提示未找到单据')


            # 找到单据 校验单据号是否一致
            log.info("开始校验单号")
            log_message("开始校验单号")
            valid, invoice_no = self.valid_invoice_id(invoice_id)
            if not valid:
                msg = f'单号不一致，搜索到的: {invoice_no} 需要的: {invoice_id}'
                log.info(msg)
                log_message(msg)
                return ProcessResult.fail(msg)

            # 找到是否为0 为0则可以打印
            global_pause.wait()
            zero_location = from_path('zero', confidence=0.84)
            zero2_location = from_path('zero2', confidence=0.84)
            if zero_location is None and zero2_location is None:
                log.info(f'跳过，单据左下角不为0')
                log_message(f'跳过，单据[{invoice_id}]左下角不为0')
                return ProcessResult.success(f'单据[{invoice_id}]左下角不为0')

            def shuaxincunliang():
                global_pause.wait()
                log.info(f"点击存量")
                # 点击 存量
                cunliang_location = from_path('cunliang')
                pyautogui.moveTo(cunliang_location.x + 24, cunliang_location.y)
                pyautogui.click(cunliang_location.x + 24, cunliang_location.y)

                log.info(f"存量位置: {cunliang_location.x + 24}, {cunliang_location.y}")

                time.sleep(0.3)

                log.info(f"点击刷新存量")
                # 点击 刷新表现体存量
                sx_cunliang_location = from_path('shuaxincunliang')
                pyautogui.moveTo(sx_cunliang_location.x, sx_cunliang_location.y)
                pyautogui.click(sx_cunliang_location.x, sx_cunliang_location.y)

                log.info(f"刷新存量位置: {sx_cunliang_location.x}, {sx_cunliang_location.y}")

            # 找有没有件数字段 没有则勾选完模板再去打印
            global_pause.wait()
            jianshu_location = from_path('jianshu')
            if jianshu_location is None:
                log.info(f"没有找到件数，切换模板")
                bcgs_location = from_path('baocungeshi')
                if bcgs_location is None:
                    log.error(f"需要切换模板，根据'保存格式'定位，但是没找到'保存格式'")
                    log_message(f"[{invoice_id}] 需要切换模板，根据'保存格式'定位，但是没找到'保存格式'")
                    return ProcessResult.fail("需要切换模板，根据'保存格式'定位，但是没找到'保存格式'")
                else:
                    pyautogui.moveTo(bcgs_location.x, bcgs_location.y + 26)
                    pyautogui.click(bcgs_location.x, bcgs_location.y + 26)
                    pyautogui.sleep(0.5)
                    zhixiang_location = from_path('zhixiang')
                    log.info(f"寻找纸箱打印模板")
                    if zhixiang_location is None:
                        log.info(f"没找到 纸箱打印模板")
                        log_message(f"[{invoice_id}] 没找到 纸箱打印模板")
                        return ProcessResult.fail("没找到 纸箱打印模板")
                    else:
                        pyautogui.moveTo(zhixiang_location.x, zhixiang_location.y)
                        pyautogui.click(zhixiang_location.x, zhixiang_location.y)
                        log.info(f"选择纸箱打印模板")
            else:
                # 点击存量刷新存量
                shuaxincunliang()

                log.info(f"找到件数")
                # 点击发货单打印模板
                bcgs_location = from_path('baocungeshi')
                pyautogui.moveTo(bcgs_location.x, bcgs_location.y + 26)
                pyautogui.click(bcgs_location.x, bcgs_location.y + 26)
                fahuodan_location = from_path('fahuodan')
                log.info(f"寻找发货单打印模板")
                if fahuodan_location is None:
                    log.info(f"没找到 发货单打印模板")
                    log_message(f"[{invoice_id}] 没找到 发货打印模板")
                    return ProcessResult.fail("没找到 发货单打印模板")
                else:
                    pyautogui.moveTo(fahuodan_location.x, fahuodan_location.y)
                    pyautogui.click(fahuodan_location.x, fahuodan_location.y)
                    log.info(f"选择发货单打印模板")
                pyautogui.moveTo(jianshu_location.x, jianshu_location.y)

            # 点击 打印
            global_pause.wait()
            print_location = from_path('print')
            if print_location is not None:
                pyautogui.moveTo(print_location.x, print_location.y)
                pyautogui.click(print_location.x, print_location.y)

                # 点击不再弹出
                bztc_location = from_path('buzaitanchu')
                if bztc_location is not None:
                    pyautogui.moveTo(bztc_location.x, bztc_location.y)
                    pyautogui.click(bztc_location.x, bztc_location.y)
                    # 点击 确定
                    quedingdayin_location = from_path('quedingdayin')
                    if quedingdayin_location is not None:
                        pyautogui.moveTo(quedingdayin_location.x, quedingdayin_location.y)
                        pyautogui.click(quedingdayin_location.x, quedingdayin_location.y)


            # 再次点击 打印 打印机执行打印操作
            global_pause.wait()
            dayin_location = from_path('dayin', min_search_time=5)
            if dayin_location is not None:
                pyautogui.moveTo(dayin_location.x, dayin_location.y)
                # 打印
                # pyautogui.click(dayin_location.x, dayin_location.y)
                # 循环等待打印窗口消失后再继续
                while True:
                    dayin_location = from_path('dayin')
                    if dayin_location is None:
                        break
            else:
                log.info(f"点击打印失败，没有找到打印按钮")
                log_message(f"点击打印失败，没有找到打印按钮")

                # 不能打印的发微信通知 跳过此单
                global_pause.wait()
                buneng_location = from_path('buneng')
                if buneng_location is not None:
                    # 找到提示的确定按钮
                    bn_qd_location = from_path('queding')
                    if bn_qd_location is not None:
                        pyautogui.moveTo(bn_qd_location.x, bn_qd_location.y, 1)
                        pyautogui.click(bn_qd_location.x, bn_qd_location.y)
                    self.wechat_client.send_msg(f'不能打印{invoice_id}', get_config().base.notify_user)
                    log.info("系统提示不能打印")
                    log_message(f"系统提示不能打印: {invoice_id}")
                    return ProcessResult.success('系统提示不能打印')


        except Exception as e:
            log.error(f"脚本执行失败: {e}")
            log_message(f"脚本执行失败: {invoice_id}, 原因: {e}")
            # self.wechat_client.send_msg(f'脚本执行失败，单号: {invoice_id}', get_config().base.notify_user)
            return ProcessResult.fail(str(e))
        return ProcessResult.success()

if __name__ == '__main__':
    pass
