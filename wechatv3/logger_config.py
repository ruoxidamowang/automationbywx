import logging
from logging import LoggerAdapter
import coloredlogs
from datetime import datetime
import os

from wechatv3.common import get_config

class InvoiceLoggerAdapter(LoggerAdapter):
    """用于打印带单据号的日志适配器"""
    def __init__(self, logger, invoice_id: str):
        super().__init__(logger, {})
        self.invoice_id = invoice_id

    def process(self, msg, kwargs):
        return f"[{self.invoice_id}] {msg}", kwargs


class LoggerManager:
    def __init__(self, log_level=logging.INFO):
        self.log_level = log_level
        self.logger = logging.getLogger()
        self.logger.setLevel(log_level)
        self._setup_handlers()
        self.invoice_logger: InvoiceLoggerAdapter | None = None

    def _setup_handlers(self):
        os.makedirs(get_config().base.log_path, exist_ok=True)
        log_filename = os.path.join(get_config().base.log_path, datetime.now().strftime('%Y-%m-%d') + ".log")

        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            stream_handler = logging.StreamHandler()

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            stream_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(stream_handler)

            coloredlogs.install(
                logger=self.logger,
                level=self.log_level,
                fmt='%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                level_styles={
                    'debug': {'color': 'cyan'},
                    'info': {'color': 'green'},
                    'warning': {'color': 'yellow'},
                    'error': {'color': 'red'},
                    'critical': {'color': 'magenta'},
                },
                field_styles={
                    'asctime': {'color': 'white'},
                }
            )

    def get_logger(self) -> logging.Logger:
        return self.logger

    def get_invoice_logger(self, invoice_id: str) -> InvoiceLoggerAdapter:
        return InvoiceLoggerAdapter(self.logger, invoice_id)