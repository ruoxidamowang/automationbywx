from datetime import datetime
import customtkinter as ctk
from customtkinter import CTkTextbox

# 在这个模块里也可以选择初始化 GUI 控件，但要由 main.py 调用初始化函数

log_text: CTkTextbox | None = None  # 外部要设置

def set_log_text_widget(widget: CTkTextbox):
    """设置 log_text 控件引用"""
    global log_text
    log_text = widget

def log_message(message: str):
    """将日志信息写入 GUI 的日志框"""
    if log_text is None:
        print(f"[LOG] {message}")  # fallback，如果没设置 log_text 就打印
        return

    log_text.configure(state=ctk.NORMAL, spacing3=4)
    log_text.insert(ctk.END, f"{message}\n")
    log_text.yview(ctk.END)
    log_text.configure(state=ctk.DISABLED)