
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "flowmind.db"


def get_connection(db_path=None):
    """建立 SQLite 数据库连接。"""
    path = db_path if db_path is not None else DB_FILE

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    return conn


def init_database(db_path=None):
    """初始化数据库和任务表。"""
    conn = get_connection(db_path)

    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '待完成'
                        CHECK(status IN ('待完成', '已完成'))
                )
            """)
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
    print("FlowMind AI 数据库初始化成功！")
