import os
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional, List

from wechatv3.sqlite_tool import SQLiteTool


class Status(str, Enum):
    PENDING = '待处理'
    IN_PROGRESS = '操作中'
    SUCCESS = '已完成'
    FAIL = '操作失败'

    def __str__(self):
        return self.value


@dataclass
class MessageRecord:
    # 类常量
    TABLE_NAME: ClassVar[str] = "invoice"
    DB_PATH: ClassVar[str] = os.getcwd() + "/db/invoice.db"

    # 数据字段
    id: str
    type: str
    sender: str
    original_message: str
    duration: int
    over_time: str
    status: str = Status.PENDING.value
    reason: Optional[str] = None
    send_time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    def init_db(cls):
        """初始化数据库表（自动处理枚举转换）"""
        with SQLiteTool(cls.DB_PATH) as db:
            db.execute(f"""
                CREATE TABLE IF NOT EXISTS {cls.TABLE_NAME} (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    sender TEXT,
                    original_message TEXT,
                    status TEXT CHECK(status IN ('待处理', '操作中', '已完成', '操作失败')),
                    duration INTEGER,
                    reason TEXT,
                    send_time TEXT,
                    over_time TEXT,
                )
            """)

    def to_dict(self) -> dict:
        """将实例转换为字典（类型安全的实现）"""
        return {
            "id": self.id,
            "type": self.type,
            "sender": self.sender,
            "original_message": self.original_message,
            "duration": self.duration,
            "status": str(self.status),
            "reason": self.reason,
            "send_time": self.send_time,
            "over_time": self.over_time
        }

    def save(self) -> None:
        """保存记录（自动转换枚举值为字符串）"""
        with SQLiteTool(self.DB_PATH) as db:
            db.insert(self.TABLE_NAME, self.to_dict())

    @classmethod
    def from_row(cls, row: dict) -> 'MessageRecord':
        """从数据库行创建实例（字符串转枚举）"""
        return cls(
            id=row.get('id'),
            type=row.get('type'),
            sender=row.get('sender'),
            original_message=row.get('original_message'),
            status=row.get('status'),
            duration=row.get('duration'),
            reason=row.get('reason'),
            send_time=row.get('send_time'),
            over_time=row.get('over_time'),
        )

    @classmethod
    def get_by_statuses(cls, statuses: List[Status]) -> List['MessageRecord']:
        """查询多个状态的记录（使用IN语句）"""
        with SQLiteTool(cls.DB_PATH) as db:
            # 生成占位符 (?,?,...)
            placeholders = ','.join(['?'] * len(statuses))
            # 转换枚举为字符串
            status_values = [s.value for s in statuses]

            all_data = db.fetchall(
                f"SELECT * FROM {cls.TABLE_NAME} WHERE status IN ({placeholders})",
                tuple(status_values)
            )
            return [cls.from_row(row) for row in all_data]

    def set_status(self,
                   new_status: Status,
                   reason: Optional[str] = None) -> None:
        if not isinstance(new_status, Status):
            raise ValueError("必须使用Status枚举成员")

        self.status = new_status
        self.reason = reason
        self.save()


if __name__ == "__main__":
    pass
