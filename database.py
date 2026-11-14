
import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "flowmind.db"


# 默认 Agent 使用固定 UUID，方便兼容旧接口
DEFAULT_AGENT_ID = (
    "00000000-0000-4000-8000-000000000001"
)

DEFAULT_AGENT_TOOLS = [
    "get_task_summary",
    "list_tasks",
    "create_task",
    "update_task_status",
]


def get_connection(db_path=None):
    """建立 SQLite 数据库连接。"""

    path = db_path if db_path is not None else DB_FILE

    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def init_database(db_path=None):
    """
    初始化数据库。

    保留 tasks 和 agents 原有数据。
    新增 agent_memories 记忆表。
    """

    conn = get_connection(db_path)

    try:
        with conn:

            # ==================================
            # 1. 原有任务表
            # ==================================

            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '待完成'
                        CHECK(status IN ('待完成', '已完成'))
                )
            """)

            # ==================================
            # 2. 原有 Agent 配置表
            # ==================================

            conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,

                    name TEXT NOT NULL,

                    description TEXT NOT NULL
                        DEFAULT '',

                    personality TEXT NOT NULL
                        DEFAULT 'professional'
                        CHECK(
                            personality IN (
                                'professional',
                                'companion',
                                'efficient',
                                'creative'
                            )
                        ),

                    response_style TEXT NOT NULL
                        DEFAULT 'balanced'
                        CHECK(
                            response_style IN (
                                'concise',
                                'balanced',
                                'detailed'
                            )
                        ),

                    custom_instructions TEXT NOT NULL
                        DEFAULT '',

                    enabled_tools TEXT NOT NULL
                        DEFAULT '[]',

                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ==================================
            # 3. 初始化默认 Agent
            # ==================================

            conn.execute(
                """
                INSERT OR IGNORE INTO agents (
                    id,
                    name,
                    description,
                    personality,
                    response_style,
                    custom_instructions,
                    enabled_tools
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    DEFAULT_AGENT_ID,
                    "My Agent",
                    "可自定义的个人 AI 助手",
                    "professional",
                    "balanced",
                    "",
                    json.dumps(
                        DEFAULT_AGENT_TOOLS,
                        ensure_ascii=False,
                    ),
                ),
            )

            # ==================================
            # 4. 新增 Agent 长期记忆表
            # ==================================

            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memories (

                    id TEXT PRIMARY KEY,

                    agent_id TEXT NOT NULL,

                    memory_key TEXT NOT NULL,

                    memory_type TEXT NOT NULL
                        DEFAULT 'fact',

                    content TEXT NOT NULL,

                    source TEXT NOT NULL
                        DEFAULT 'manual',

                    importance INTEGER NOT NULL
                        DEFAULT 3
                        CHECK(importance BETWEEN 1 AND 5),

                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY(agent_id)
                        REFERENCES agents(id)
                        ON DELETE CASCADE,

                    UNIQUE(agent_id, memory_key),

                    CHECK(length(trim(memory_key)) > 0),

                    CHECK(length(trim(content)) > 0)
                )
            """)

            # ==================================
            # 5. 创建查询索引
            # ==================================

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_agent_memories_agent_updated
                ON agent_memories(
                    agent_id,
                    updated_at DESC,
                    created_at DESC
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_agent_memories_agent_type
                ON agent_memories(
                    agent_id,
                    memory_type
                )
            """)

    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
    print("FlowMind AI 数据库初始化成功！")
