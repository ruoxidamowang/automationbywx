import sqlite3
from typing import Dict, Any, Optional, List


class SQLiteTool:
    def __init__(self, db_path: str = ':memory:'):
        """
        初始化SQLite工具类

        :param db_path: 数据库文件路径，默认为内存数据库
        """
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def connect(self) -> None:
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path, autocommit=True)
            self.cursor = self.connection.cursor()
            print(f"成功连接到数据库: {self.db_path}")
        except sqlite3.Error as e:
            print(f"连接数据库失败: {e}")

    def close(self) -> None:
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            print("数据库连接已关闭")

    def execute(self, sql: str, params: Optional[tuple] = None) -> None:
        """
        执行SQL语句

        :param sql: SQL语句
        :param params: 参数元组
        """
        try:
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"执行SQL失败: {e}")
            self.connection.rollback()

    def executemany(self, sql: str, params_list: List[tuple]) -> None:
        """
        批量执行SQL语句

        :param sql: SQL语句
        :param params_list: 参数元组列表
        """
        try:
            self.cursor.executemany(sql, params_list)
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"批量执行SQL失败: {e}")
            self.connection.rollback()

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """
        查询单条记录

        :param sql: SQL查询语句
        :param params: 参数元组
        :return: 单条记录字典或None
        """
        try:
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)

            columns = [col[0] for col in self.cursor.description]
            row = self.cursor.fetchone()

            if row:
                return dict(zip(columns, row))
            return None
        except sqlite3.Error as e:
            print(f"查询单条记录失败: {e}")
            return None

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        查询多条记录

        :param sql: SQL查询语句
        :param params: 参数元组
        :return: 记录字典列表
        """
        try:
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)

            columns = [col[0] for col in self.cursor.description]
            rows = self.cursor.fetchall()

            return [dict(zip(columns, row)) for row in rows]
        except sqlite3.Error as e:
            print(f"查询多条记录失败: {e}")
            return []

    def create_table(self, table_name: str, columns: Dict[str, str]) -> None:
        """
        创建表

        :param table_name: 表名
        :param columns: 列名和类型的字典，如 {'id': 'INTEGER PRIMARY KEY', 'name': 'TEXT'}
        """
        columns_sql = ', '.join([f"{name} {type_}" for name, type_ in columns.items()])
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})"
        self.execute(sql)

    def insert(self, table_name: str, data: Dict[str, Any]) -> Optional[int]:
        """
        插入一条记录

        :param table_name: 表名
        :param data: 数据字典
        :return: 插入行的ID或None
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        try:
            self.execute(sql, tuple(data.values()))
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"插入记录失败: {e}")
            return None

    def update(self, table_name: str, data: Dict[str, Any], condition: str, params: tuple = ()) -> int:
        """
        更新记录

        :param table_name: 表名
        :param data: 要更新的数据字典
        :param condition: WHERE条件语句
        :param params: WHERE条件的参数
        :return: 影响的行数
        """
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {condition}"

        try:
            self.execute(sql, tuple(data.values()) + params)
            return self.cursor.rowcount
        except sqlite3.Error as e:
            print(f"更新记录失败: {e}")
            return 0

    def delete(self, table_name: str, condition: str, params: tuple = ()) -> int:
        """
        删除记录

        :param table_name: 表名
        :param condition: WHERE条件语句
        :param params: WHERE条件的参数
        :return: 影响的行数
        """
        sql = f"DELETE FROM {table_name} WHERE {condition}"

        try:
            self.execute(sql, params)
            return self.cursor.rowcount
        except sqlite3.Error as e:
            print(f"删除记录失败: {e}")
            return 0

    def __enter__(self):
        """支持with语句"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持with语句"""
        self.close()

if __name__ == '__main__':
    pass
    # con = sqlite3.connect(get_config().base_dir + '/db/invoice.db', factory=sqlite3.Connection, autocommit=True)
    # cur = con.cursor()
    # cur.execute('drop table if exists invoice')
    # cur.execute('create table if not exists invoice(id , "type", send_time, sender, raw_msg, status, reason)')
    # now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # cur.execute('insert into invoice values(?,?,?,?,?,?,?)', ("FHD10000000", "发货单", now, "自己", "FHD25041470 FHD25041471", "待处理", ""))
    # # cur.execute('delete from invoice where id = ?', ("FHD10000000",))
    # res = cur.execute('select id, type, send_time, sender, raw_msg, status, reason from invoice')
    # print(res.fetchall())
    # with SQLiteTool(get_config().base_dir + '/db/invoice.db') as db:
    #     # 创建表
    #     db.create_table('invoice', {
    #         'id': 'text primary key',
    #         'type': 'text',
    #         'send_time': 'text',
    #         'sender': 'text',
    #         'raw_msg': 'text',
    #         'status': 'text',
    #         'reason': 'text',
    #     })
    #
    #     now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #     # 插入数据
    #     invoice_id = db.insert('invoice', {
    #         'id': 'FHD10000001',
    #         'type': '发货单',
    #         'send_time': now,
    #         'sender': '自己',
    #         'raw_msg': 'FHD25041470 FHD25041471',
    #         'status': '待处理',
    #         'reason': '',
    #     })
    #     print(f"插入的ID: {invoice_id}")
    #
    #     alldata = db.fetchall('SELECT * FROM invoice')
    #     print(alldata)

        # 批量插入
        # users = [
        #     {'name': 'Bob', 'age': 30, 'email': 'bob@example.com'},
        #     {'name': 'Charlie', 'age': 35, 'email': 'charlie@example.com'}
        # ]
        # for user in users:
        #     db.insert('users', user)
        #
        # # 查询单条记录
        # user = db.fetchone("SELECT * FROM users WHERE name = ?", ('Alice',))
        # print(f"查询到的用户: {user}")
        #
        # # 查询所有记录
        # all_users = db.fetchall("SELECT * FROM users")
        # print("所有用户:")
        # for u in all_users:
        #     print(u)
        #
        # # 更新记录
        # rows_affected = db.update('users', {'age': 26}, "id = ?", (user_id,))
        # print(f"更新了 {rows_affected} 条记录")
        #
        # # 删除记录
        # rows_deleted = db.delete('users', "age > ?", (30,))
        # print(f"删除了 {rows_deleted} 条记录")