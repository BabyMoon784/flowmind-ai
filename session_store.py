
import sqlite3
from pathlib import Path


DB_FILE = Path(__file__).resolve().parent / "chat_sessions.db"


def get_connection():
    """连接聊天会话数据库。"""
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



def init_database():
    """创建会话表和聊天消息表。"""
    conn = get_connection()

    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL
                        CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    FOREIGN KEY(session_id)
                        REFERENCES sessions(id)
                )
            """)
    finally:
        conn.close()



def load_history(session_id, limit=10):
    """读取指定会话最近的消息。"""
    conn = get_connection()

    try:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,)
        ).fetchone()

        if session is None:
            raise LookupError("聊天会话不存在")

        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit)
        ).fetchall()

        return [
            {"role": row["role"], "content": row["content"]}
            for row in reversed(rows)
        ]
    finally:
        conn.close()


def save_turn(session_id, question, answer, new_session=False):
    """原子保存一轮用户消息与 AI 回复。"""
    conn = get_connection()

    try:
        with conn:
            if new_session:
                conn.execute(
                    "INSERT INTO sessions (id) VALUES (?)",
                    (session_id,)
                )
            else:
                exists = conn.execute(
                    "SELECT id FROM sessions WHERE id = ?",
                    (session_id,)
                ).fetchone()

                if exists is None:
                    raise LookupError("聊天会话不存在")

            conn.execute(
                """
                INSERT INTO messages
                    (session_id, role, content)
                VALUES (?, 'user', ?)
                """,
                (session_id, question)
            )

            conn.execute(
                """
                INSERT INTO messages
                    (session_id, role, content)
                VALUES (?, 'assistant', ?)
                """,
                (session_id, answer)
            )
    finally:
        conn.close()

    return load_history(session_id)
