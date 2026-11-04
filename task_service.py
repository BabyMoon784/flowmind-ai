
import sqlite3
from contextlib import contextmanager

import database


# 默认使用真正的 FlowMind 数据库
# 测试时可以替换成临时数据库路径
DB_FILE = database.DB_FILE


@contextmanager
def open_database():
    """打开数据库，并在操作结束后关闭连接。"""
    database.init_database(DB_FILE)

    conn = database.get_connection(DB_FILE)

    try:
        with conn:
            yield conn
    finally:
        conn.close()


def list_tasks():
    """获取全部任务，返回原有的字典列表格式。"""
    with open_database() as conn:
        rows = conn.execute(
            """
            SELECT id, title, status
            FROM tasks
            ORDER BY id
            """
        ).fetchall()

        return [dict(row) for row in rows]


def create_task(title):
    """创建任务，让 SQLite 自动生成 ID。"""
    if not isinstance(title, str):
        raise ValueError("任务名称必须是字符串")

    title = title.strip()

    if not title or len(title) > 100:
        raise ValueError("任务名称必须是 1～100 个字符")

    with open_database() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, status)
            VALUES (?, ?)
            """,
            (title, "待完成"),
        )

        task_id = cursor.lastrowid

        return {
            "id": task_id,
            "title": title,
            "status": "待完成",
        }


def update_task_status(task_id, status):
    """修改指定任务的状态。"""
    if status not in ("待完成", "已完成"):
        raise ValueError("任务状态不合法")

    with open_database() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
            SET status = ?
            WHERE id = ?
            """,
            (status, task_id),
        )

        if cursor.rowcount == 0:
            raise LookupError(f"任务 {task_id} 不存在")

        row = conn.execute(
            """
            SELECT id, title, status
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        return dict(row)


def get_task_summary():
    """统计总任务数、已完成数、未完成数。"""
    with open_database() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(
                    CASE WHEN status = '已完成'
                    THEN 1 END
                ) AS completed
            FROM tasks
            """
        ).fetchone()

        total = row["total"]
        completed = row["completed"]

        return {
            "total": total,
            "completed": completed,
            "pending": total - completed,
        }

