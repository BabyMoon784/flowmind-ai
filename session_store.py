
import sqlite3
from pathlib import Path

from database import DEFAULT_AGENT_ID


DB_FILE = (
    Path(__file__).resolve().parent
    / "chat_sessions.db"
)


class SessionAgentMismatchError(ValueError):
    """同一聊天会话尝试使用其他 Agent。"""


def get_connection():
    """连接聊天会话数据库。"""

    conn = sqlite3.connect(
        DB_FILE,
        timeout=10,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


# ==========================================
# 1. 创建或迁移数据库
# ==========================================

def init_database():
    """
    初始化聊天数据库。

    新数据库：
        sessions 包含 agent_id。

    旧数据库：
        使用 ALTER TABLE 新增 agent_id，
        保留全部原有聊天记录。
    """

    conn = get_connection()

    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,

                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    agent_id TEXT NOT NULL
                        DEFAULT
                        '00000000-0000-4000-8000-000000000001'
                )
            """)

            # 检查旧数据库是否缺少 agent_id
            columns = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(sessions)"
                ).fetchall()
            }

            if "agent_id" not in columns:
                # 这里的默认 ID 是项目内固定常量，
                # 不是用户传入的 SQL。
                conn.execute(
                    f"""
                    ALTER TABLE sessions
                    ADD COLUMN agent_id TEXT NOT NULL
                    DEFAULT '{DEFAULT_AGENT_ID}'
                    """
                )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    session_id TEXT NOT NULL,

                    role TEXT NOT NULL
                        CHECK(
                            role IN ('user', 'assistant')
                        ),

                    content TEXT NOT NULL,

                    FOREIGN KEY(session_id)
                        REFERENCES sessions(id)
                )
            """)

    finally:
        conn.close()


# ==========================================
# 2. 获取会话绑定信息
# ==========================================

def get_session(session_id):
    """读取指定会话及其绑定的 Agent ID。"""

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT id, created_at, agent_id
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise LookupError("聊天会话不存在")

    return dict(row)


# ==========================================
# 3. 读取聊天历史
# ==========================================

def load_history(session_id, limit=10):
    """读取指定会话最近的消息。"""

    conn = get_connection()

    try:
        exists = conn.execute(
            """
            SELECT id
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if exists is None:
            raise LookupError("聊天会话不存在")

        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()

        return [
            {
                "role": row["role"],
                "content": row["content"],
            }
            for row in reversed(rows)
        ]

    finally:
        conn.close()


# ==========================================
# 4. 分页读取历史
# ==========================================

def load_history_page(
    session_id,
    limit=50,
    offset=0,
):
    """分页读取历史及会话绑定关系。"""

    conn = get_connection()

    try:
        session = conn.execute(
            """
            SELECT id, agent_id
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if session is None:
            raise LookupError("聊天会话不存在")

        if not 1 <= limit <= 100:
            raise ValueError(
                "limit 必须在 1 到 100 之间"
            )

        if offset < 0:
            raise ValueError(
                "offset 不能小于 0"
            )

        rows = conn.execute(
            """
            SELECT id, role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (session_id, limit + 1, offset),
        ).fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]

        messages = [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
            }
            for row in reversed(rows)
        ]

        return {
            "messages": messages,
            "has_more": has_more,
            "agent_id": session["agent_id"],
        }

    finally:
        conn.close()


# ==========================================
# 5. 保存一轮聊天
# ==========================================

def save_turn(
    session_id,
    question,
    answer,
    new_session=False,
    agent_id=None,
):
    """
    原子保存一轮聊天。

    新会话：
        保存 agent_id。

    旧会话：
        校验 agent_id 与已绑定的 Agent 一致。

    保留旧版调用方式。
    """

    conn = get_connection()

    try:
        with conn:

            if new_session:
                bound_agent_id = (
                    agent_id or DEFAULT_AGENT_ID
                )

                conn.execute(
                    """
                    INSERT INTO sessions (
                        id,
                        agent_id
                    )
                    VALUES (?, ?)
                    """,
                    (
                        session_id,
                        bound_agent_id,
                    ),
                )

            else:
                session = conn.execute(
                    """
                    SELECT agent_id
                    FROM sessions
                    WHERE id = ?
                    """,
                    (session_id,),
                ).fetchone()

                if session is None:
                    raise LookupError(
                        "聊天会话不存在"
                    )

                # 执行写入前再次检查绑定关系
                if (
                    agent_id is not None
                    and session["agent_id"] != agent_id
                ):
                    raise SessionAgentMismatchError(
                        "该聊天会话已经绑定其他 Agent，"
                        "请新建会话。"
                    )

            conn.execute(
                """
                INSERT INTO messages
                    (session_id, role, content)
                VALUES (?, 'user', ?)
                """,
                (session_id, question),
            )

            conn.execute(
                """
                INSERT INTO messages
                    (session_id, role, content)
                VALUES (?, 'assistant', ?)
                """,
                (session_id, answer),
            )

    finally:
        conn.close()

    return load_history(session_id)


# ==========================================
# 6. 列出聊天会话
# ==========================================

def list_sessions():
    """列出会话，包含绑定的 Agent ID。"""

    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT
                s.id,
                s.created_at,
                s.agent_id,

                COALESCE(
                    (
                        SELECT SUBSTR(
                            m.content, 1, 30
                        )
                        FROM messages AS m
                        WHERE m.session_id = s.id
                          AND m.role = 'user'
                        ORDER BY m.id ASC
                        LIMIT 1
                    ),
                    '新对话'
                ) AS title,

                (
                    SELECT COUNT(*)
                    FROM messages AS m
                    WHERE m.session_id = s.id
                ) AS message_count

            FROM sessions AS s

            ORDER BY
                s.created_at DESC,
                s.rowid DESC
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


# ==========================================
# 7. 删除聊天会话
# ==========================================

def delete_session(session_id):
    """删除会话及其聊天消息。"""

    conn = get_connection()

    try:
        with conn:
            exists = conn.execute(
                """
                SELECT id
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()

            if exists is None:
                return False

            conn.execute(
                """
                DELETE FROM messages
                WHERE session_id = ?
                """,
                (session_id,),
            )

            conn.execute(
                """
                DELETE FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )

        return True

    finally:
        conn.close()
