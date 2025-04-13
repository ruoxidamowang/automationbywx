import os
from types import SimpleNamespace
import yaml

class ConfigNamespace(SimpleNamespace):

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        return getattr(self, key)

    def __repr__(self):
        return f"{self.__dict__}"


class AppConfig:
    base_dir = os.getcwd()

    DEFAULT_BASE = {
        "notify_user": "初代",
        "sleep_time": 2,
        "file_base_path": base_dir,
        "log_path": "日志",  # 注意这里只是相对路径名
        "pending_path": "单据处理",
        "pending_file_name": "待处理.csv",
        "processed_path": "单据处理",
        "processed_file_name": "已处理.csv",
        "base_result_dir": "处理结果",
    }

    RELATIVE_KEYS = ["log_path", "pending_path", "processed_path", "base_result_dir"]

    def __init__(self, config_path: str):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件未找到: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)

        self._parse(raw_config)

    def _parse(self, data: dict):
        # 转成属性访问形式
        self.wechat_user = data.get("wechat_user", [])

        # 获取 paths 和 base 字典
        paths_data = data.get("paths", {})
        base_data = data.get("base", {})

        # 应用默认值
        for key, default in self.DEFAULT_BASE.items():
            val = base_data.get(key)
            base_data[key] = val if val else default

        # 拼接相对路径字段
        base_dir = base_data["file_base_path"]
        for key in self.RELATIVE_KEYS:
            value = base_data[key]
            # 如果不是绝对路径，则拼接 file_base_path
            if not os.path.isabs(value):
                base_data[key] = os.path.normpath(os.path.join(base_dir, value))

        self.paths = ConfigNamespace(**paths_data)
        self.base = ConfigNamespace(**base_data)

    def __repr__(self):
        return f"<AppConfig wechat_user={self.wechat_user}, paths={self.paths}, base={self.base}>"

# 全局单例实例
_config_instance: AppConfig | None = None

def get_config() -> AppConfig:
    global _config_instance
    if _config_instance is None:
        config_path = os.path.join(AppConfig.base_dir, 'config.yaml')
        _config_instance = AppConfig(config_path)
    return _config_instance