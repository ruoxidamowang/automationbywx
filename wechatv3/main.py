import csv
import os
import queue
import threading
from functools import partial

import customtkinter as ctk
import keyboard

from wechatv3 import wechat_client
from wechatv3.common import get_config
from wechatv3.gui_msg import set_log_text_widget, log_message
from wechatv3.logger_config import LoggerManager
from wechatv3.msg_unique_queue import DedupQueue
from wechatv3.process_invoice import InvoiceProcessor
from wechatv3.wechat_client import WeChatListener


class AppController:
    def __init__(self, logger_manager, wechat):
        self.logger = logger_manager.get_logger()
        # GUI
        self.root = ctk.CTk()
        self.root.title('发货单自动化处理')

        # 设定窗口大小
        win_width = 400
        win_height = 260

        # 获取屏幕分辨率
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # 计算右下角位置
        x = screen_width - win_width - 240
        y = screen_height - win_height - 260

        # 设置窗口位置
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")

        self.root.geometry(f"{win_width}x{win_height}")
        self.root.wm_attributes("-topmost", True)

        self.log_text = ctk.CTkTextbox(self.root, width=win_width, height=win_height, activate_scrollbars=False)
        self.log_text.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # create CTk scrollbar
        # ctk_textbox_scrollbar = ctk.CTkScrollbar(self.root, command=self.log_text.yview)
        # ctk_textbox_scrollbar.grid(row=0, column=1, sticky="ns")
        #
        # # connect textbox scroll event to CTk scrollbar
        # self.log_text.configure(yscrollcommand=ctk_textbox_scrollbar.set)
        set_log_text_widget(self.log_text)

        self.status_var = ctk.StringVar(value="状态：未启动")
        ctk.CTkLabel(self.root, textvariable=self.status_var, font=("Arial", 14)) \
          .grid(row=1, column=0, columnspan=2)

        # self.queue_listbox = tk.Listbox(self.root, width=80, height=10)
        # self.queue_listbox.grid(row=2, column=0, padx=10, pady=5)

        ctk.CTkButton(
            self.root,
            text="暂停/恢复 (Ctrl+K)",
            font=("Arial", 12),
            width=100,
            command=self.toggle_pause
        ).grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        ctk.CTkButton(
            self.root,
            text="查看当前待处理",
            font=("Arial", 12),
            width=100,
            command=self.show_queue
        ).grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # 微信消息队列
        self.msg_queue = DedupQueue()
        self.preload_messages()

        # 业务对象
        self.listener = WeChatListener(logger_manager, self.msg_queue)
        self.processor = InvoiceProcessor(logger_manager, self.listener)

        # 远程保持连接事件
        self.keep_remote = threading.Event()
        self.keep_remote.clear()

        # 全局暂停
        self.global_pause = threading.Event()
        self.global_pause.clear()
        self.paused = True

        self.threads = []

    # def refresh_queue_display(self):
    #     self.queue_listbox.delete(0, tk.END)  # 清空旧的显示
    #     items = list(self.msg_queue.queue)  # 获取 queue 中的当前内容
    #     for item in items:
    #         self.queue_listbox.insert(tk.END, item)
    #     self.root.after(2000, self.refresh_queue_display)  # 每 2 秒自动刷新

    def _start_hotkey(self):
        keyboard.add_hotkey('ctrl+k', lambda: self.root.after(0, self.toggle_pause) or None)
        log_message("热键已启动，按 Ctrl+K 切换暂停和恢复")

    def _safe_gui_update(self, func, *args):
        """线程安全的GUI更新方法"""
        self.root.after(0, partial(func, *args))

    def preload_messages(self):
        for item in self._init_file():
            self.msg_queue.put(item)

    def _init_file(self):
        pending_file = os.path.join(get_config().base.pending_path, get_config().base.pending_file_name)
        os.makedirs(os.path.dirname(pending_file), exist_ok=True)

        # 写入表头（如果不存在）
        if not os.path.exists(pending_file):
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
                self.logger.info(f'读取到未执行的单据: {", ".join(first_column)}')
                return first_column

    def show_queue(self):
        items = self.msg_queue.snapshot()
        if items:
            log_message(f"当前待处理单据: {items}")
        else:
            log_message("暂无待处理单据")

    def start(self):
        self.threads = [
            threading.Thread(target=lambda: self.listener.start(self.global_pause), daemon=True),
            threading.Thread(target=lambda: self.processor.start(self.msg_queue, self.keep_remote, self.global_pause), daemon=True),
            threading.Thread(target=lambda: self.processor.keep_remote_alive(self.keep_remote, self.global_pause), daemon=True),
            threading.Thread(target=self._start_hotkey, daemon=True),
        ]
        for t in self.threads:
            t.start()

    def toggle_pause(self):
        if self.paused:
            log_message("全部任务恢复")
            self.status_var.set("状态：运行中")
            with self.msg_queue.mutex:
                self.msg_queue.queue.clear()
            self.preload_messages()
            self.global_pause.set()
        else:
            log_message("全部任务暂停")
            self.status_var.set("状态：已暂停")
            self.global_pause.clear()
        self.paused = not self.paused

    def run(self):
        self.start()
        # self.refresh_queue_display()
        self.root.mainloop()

if __name__ == '__main__':
    app = AppController(LoggerManager(), wechat_client)
    app.run()