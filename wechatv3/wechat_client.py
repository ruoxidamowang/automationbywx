import csv
import os
import queue
import re
import threading
import time
from datetime import datetime

from wxauto import WeChat

from wechatv3.logger_config import LoggerManager
from .gui_msg import log_message
from wechatv3.common import get_config


class WeChatListener:
    def __init__(self, logger_manager: LoggerManager, msg_queue: queue.Queue):
        self._wx: WeChat | None = None
        self.msg_queue = msg_queue
        self.logger = logger_manager.get_logger()
        self._pattern = re.compile(r"(FHD\d{8})")
        self.finished_data = WeChatListener._init_finished_data()
        self._init_wechat()

    def _init_history_msg(self, who: str, find_str: str):
        log_message(f"开始加载历史单据，关键字: {find_str}")
        history = []
        seen = set()
        if not who or not find_str:
            return history

        self._wx.ChatWith(who, timeout=30)

        def _get_history():
            # 限制最多加载的次数，避免死循环
            max_scroll_times = 20
            scroll_count = 0

            while scroll_count < max_scroll_times:
                if scroll_count > 0:
                    self._wx.LoadMoreMessage()
                in_msgs = self._wx.GetAllMessage()

                for in_msg in reversed(in_msgs):
                    in_matches = self._pattern.findall(in_msg.content)
                    for in_match in in_matches:
                        if find_str == in_match:
                            self.logger.info(f"符合的历史单据: {history}")
                            return history
                        if in_match not in seen:
                            seen.add(in_match)
                            history.append(in_msg)

                scroll_count += 1
                time.sleep(1)  # 等微信加载
        for msg in _get_history():
            matches = self._pattern.findall(msg.content)
            for match in matches:
                if match in self.msg_queue:
                    self.logger.info(f"匹配到单号: [{match}] 已在待处理，跳过")
                    continue
                line = self._add_pending_msg(match, msg)

                self.logger.info(f"已保存 {line.strip()}")
                log_message(f"已保存 {line.strip()}")

    @staticmethod
    def _init_finished_data() -> list[any]:
        # 读取已处理的第一条
        processed_file = os.path.join(get_config().base.processed_path, get_config().base.processed_file_name)
        with open(processed_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)
            rows = [row for row in reader if row and any(field.strip() for field in row)]
            return rows

    # 获取最后处理的单号
    def _get_last_no(self) -> str:
        # 读取待处理的最后一条
        pending_file = os.path.join(get_config().base.pending_path, get_config().base.pending_file_name)
        with open(pending_file, 'r', encoding='utf-8-sig') as f:
            reader = list(csv.reader(f))
            # 跳过第一行表头
            for row in reversed(reader[1:]):
                if row and row[0].strip():  # 确保这一行存在并且第一个字段不为空
                    return row[0]

        # 读取已处理的第一条
        for row in reversed(self.finished_data):
            if row and row[0].strip():  # 确保这一行存在并且第一个字段不为空
                return row[0]
        return ''

    def _init_wechat(self):
        try:
            if self._wx is None:
                self._wx = WeChat()
                self._wx.GetSessionList()
                last_no = self._get_last_no()
                self.logger.info(f"最后处理的单据号: {last_no}")
                for name in get_config().wechat_user:
                    self._init_history_msg(name, last_no)
                log_message("已添加未处理历史消息")
                self._init_listener()
        except Exception as e:
            log_message("初始化微信失败，请确定微信已启动")
            raise e

    def _init_listener(self):
        for name in get_config().wechat_user:
            self._wx.AddListenChat(name)
        log_message("微信实例已初始化并添加监听联系人")

    def _listen_loop(self, global_pause: threading.Event):
        listening = False

        self.logger.info("监听微信消息中...")
        log_message("监听微信消息中...")

        """内部监听循环，自动写入数据文件"""
        while True:
            # global_pause.wait()

            # if not listening:
            #     self.logger.info("监听微信消息中...")
            #     log_message("监听微信消息中...")
            #     listening = True  # 已打印，设置为正在监听状态

            msgs = self._wx.GetListenMessage()

            for chat in msgs:
                for msg in msgs.get(chat, []):
                    matches = self._pattern.findall(msg.content)
                    for match in matches:
                        if match in self.msg_queue:
                            self.logger.info(f"匹配到单号: [{match}] 已在待处理，跳过")
                            continue
                        if match in list(item[0] for item in self.finished_data):
                            self.logger.info(f"匹配到单号: [{match}] 单据已处理过，跳过")
                            continue
                        line = self._add_pending_msg(match, msg)

                        self.logger.info(f"已保存 {line.strip()}")
                        self.logger.info(f"待处理单据: {list(self.msg_queue.queue)}")
                        log_message(f"已保存 {line.strip()}")
                        log_message(f"剩余待处理单据: {list(self.msg_queue.queue)}")
            time.sleep(5)

    def _add_pending_msg(self, match, msg) -> str:
        doc_type = "退货单" if "退货单" in msg.content else "发货单"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        contact = '自己' if msg.sender == 'Self' else msg.sender
        raw_msg = msg.content.replace('\n', ' ').replace(',', '，').strip()
        line = f"{match},{doc_type},{timestamp},{contact},{raw_msg}\n"
        pending_file = os.path.join(get_config().base.pending_path, get_config().base.pending_file_name)
        with open(pending_file, "a", encoding="utf-8") as f:
            f.write(line)
        self.msg_queue.put(match)
        return line

    def start(self, global_pause: threading.Event):
        self._listen_loop(global_pause)

    def send_msg(self, content, who):
        try:
            self._wx.SendMsg(content, who)
        except Exception:
            log_message(f"微信消息发送失败: [{who}]-->{content}")


if __name__ == '__main__':
    pass