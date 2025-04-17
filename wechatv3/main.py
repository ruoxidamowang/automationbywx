import csv
import ctypes
import os
import threading
from ctypes import wintypes
from functools import partial

import customtkinter as ctk
import keyboard

from wechatv3.common import get_config
from wechatv3.global_var import global_pause
from wechatv3.gui_msg import set_log_text_widget, log_message
from wechatv3.logger_config import LoggerManager
from wechatv3.msg_unique_queue import DedupQueue
from wechatv3.process_invoice import InvoiceProcessor
from wechatv3.wechat_client import WeChatListener

logger = LoggerManager().get_logger()

class AppController:
    def __init__(self):
        # GUI
        self.root = ctk.CTk()
        self.root.title('发货单自动化处理')

        # 设定窗口大小
        win_width = 400
        win_height = 260

        user32 = ctypes.windll.user32

        # 获取任务栏窗口句柄
        hwnd = user32.FindWindowW("Shell_TrayWnd", None)

        # 获取矩形
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        # 计算右下角位置
        x = rect.right - win_width
        y = rect.top - win_height - 34

        # 设置窗口位置
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")
        self.root.wm_attributes("-topmost", True)

        self.log_text = ctk.CTkTextbox(self.root,  activate_scrollbars=False)
        self.log_text.grid(row=0, column=0, columnspan=23, sticky="nsew")

        set_log_text_widget(self.log_text)

        self.status_var = ctk.StringVar(value="状态：未启动")
        self.status_label = ctk.CTkLabel(self.root, textvariable=self.status_var, justify=ctk.CENTER, text_color="#E57373",font=("微软雅黑", 14))
        self.status_label.grid(row=1, column=0, columnspan=23, padx=5, pady=5)

        # self.queue_listbox = tk.Listbox(self.root, width=80, height=10)
        # self.queue_listbox.grid(row=2, column=0, padx=10, pady=5)

        ctk.CTkButton(
            self.root,
            text="暂停/恢复 (Ctrl+K)",
            font=("Arial", 12),
            command=self.toggle_pause
        ).grid(row=2, column=0, columnspan=11, padx=(10, 5), pady=5, sticky="ew")

        ctk.CTkButton(
            self.root,
            text="查看当前待处理 (Ctrl+N)",
            font=("Arial", 12),
            command=self.show_queue
        ).grid(row=2, column=12, columnspan=11, padx=(5,10), pady=5, sticky="ew")

        self.root.grid_rowconfigure(0, weight=1)
        for i in range(24):
            self.root.grid_columnconfigure(i, weight=1)

        # 微信消息队列
        self.msg_queue = DedupQueue()

        # 加载未处理文件中的数据
        self.preload_messages()

        # 业务对象
        self.listener = WeChatListener(self.msg_queue)
        self.processor = InvoiceProcessor(self.listener)

        # 远程保持连接事件
        self.keep_remote = threading.Event()
        self.keep_remote.clear()

        # 全局暂停
        global_pause.clear()
        self.paused = True

        self.threads = []

    def _start_hotkey(self):
        keyboard.add_hotkey('ctrl+k', lambda: self.root.after(0, self.toggle_pause) or None)
        keyboard.add_hotkey('ctrl+n', lambda: self.root.after(0, self.show_queue) or None)
        log_message("热键已启动，按 Ctrl+K 切换暂停和恢复，按 Ctrl+N 查看当前待处理单据")

    def _safe_gui_update(self, func, *args):
        """线程安全的GUI更新方法"""
        self.root.after(0, partial(func, *args))

    def preload_messages(self):
        for item in self._init_file():
            self.msg_queue.put(item)

    def _init_file(self):
        pending_file = os.path.join(get_config().base.pending_path, get_config().base.pending_file_name)
        processed_file = os.path.join(get_config().base.processed_path, get_config().base.processed_file_name)

        if not os.path.exists(processed_file):
            os.makedirs(os.path.dirname(processed_file), exist_ok=True)
            with open(processed_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["编号", "类型", "时间", "联系人", "状态", "原始消息", "原因"])

        # 写入表头（如果不存在）
        if not os.path.exists(pending_file):
            os.makedirs(os.path.dirname(pending_file), exist_ok=True)
            with open(pending_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["编号", "类型", "时间", "联系人", "原始消息"])
                return []
        else:
            with open(pending_file, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)
                rows = [row for row in reader if row and any(field.strip() for field in row)]
                first_column = [row[0] for row in rows if row]
                log_message(f'读取到未执行的单据: {", ".join(first_column)}')
                logger.info(f'读取到未执行的单据: {", ".join(first_column)}')
                return first_column

    def show_queue(self):
        items = self.msg_queue.snapshot()
        if items:
            log_message(f"当前待处理单据: {items}")
        else:
            log_message("暂无待处理单据")

    def start(self):
        self.threads = [
            threading.Thread(target=lambda: self.listener.start(), daemon=True),
            threading.Thread(target=lambda: self.processor.start(self.msg_queue, self.keep_remote), daemon=True),
            threading.Thread(target=lambda: self.processor.keep_remote_alive(self.keep_remote), daemon=True),
            threading.Thread(target=self._start_hotkey, daemon=True),
        ]
        for t in self.threads:
            t.start()

    def set_status(self, text: str, color: str):
        self.status_var.set(text)
        self.status_label.configure(text_color=color)

    def toggle_pause(self):
        if self.paused:
            log_message("全部任务恢复")
            self.set_status("状态：运行中", "#81C784")
            global_pause.set()
        else:
            log_message("全部任务暂停")
            self.set_status("状态：已暂停", "#E57373")
            global_pause.clear()
        self.paused = not self.paused

    def run(self):
        self.start()
        self.root.mainloop()

if __name__ == '__main__':
    app = AppController()
    app.run()