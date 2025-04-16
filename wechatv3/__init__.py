import sqlite3
from datetime import datetime

from wechatv3.common import get_config
from wechatv3.sqlite_tool import SQLiteTool

if __name__ == '__main__':
    # con = sqlite3.connect(get_config().base_dir + '/db/invoice.db', factory=sqlite3.Connection, autocommit=True)
    # cur = con.cursor()
    # cur.execute('drop table if exists invoice')
    # cur.execute('create table if not exists invoice(id , "type", send_time, sender, raw_msg, status, reason)')
    # now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # cur.execute('insert into invoice values(?,?,?,?,?,?,?)', ("FHD10000000", "发货单", now, "自己", "FHD25041470 FHD25041471", "待处理", ""))
    # # cur.execute('delete from invoice where id = ?', ("FHD10000000",))
    # res = cur.execute('select id, type, send_time, sender, raw_msg, status, reason from invoice')
    # print(res.fetchall())
    with SQLiteTool(get_config().base_dir + '/db/invoice.db') as db:
        # 创建表
        db.create_table('invoice', {
            'id': 'text primary key',
            'type': 'text',
            'send_time': 'text',
            'sender': 'text',
            'raw_msg': 'text',
            'status': 'text',
            'reason': 'text',
        })

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 插入数据
        invoice_id = db.insert('invoice', {
            'id': 'FHD10000001',
            'type': '发货单',
            'send_time': now,
            'sender': '自己',
            'raw_msg': 'FHD25041470 FHD25041471',
            'status': '待处理',
            'reason': '',
        })
        print(f"插入的ID: {invoice_id}")

        alldata = db.fetchall('SELECT * FROM invoice')
        print(alldata)

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
    pass