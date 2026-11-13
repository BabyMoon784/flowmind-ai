
import json
from uuid import uuid4

import database


DEFAULT_AGENT_ID = database.DEFAULT_AGENT_ID

PERSONALITIES = {
    "professional",
    "companion",
    "efficient",
    "creative",
}

RESPONSE_STYLES = {
    "concise",
    "balanced",
    "detailed",
}

AVAILABLE_TOOLS = {
    "get_task_summary",
    "list_tasks",
    "create_task",
    "update_task_status",
}


# ==========================================
# 1. 配置参数校验
# ==========================================

def _validate_text(
    value,
    field_name,
    max_length,
    allow_empty=True,
):
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name}必须是字符串"
        )

    value = value.strip()

    if not allow_empty and not value:
        raise ValueError(
            f"{field_name}不能为空"
        )

    if len(value) > max_length:
        raise ValueError(
            f"{field_name}最多允许{max_length}个字符"
        )

    return value


def _validate_choice(value, field_name, choices):
    if not isinstance(value, str) or value not in choices:
        raise ValueError(
            f"{field_name}不合法，可选值："
            + ", ".join(sorted(choices))
        )

    return value


def _validate_tools(tools):
    """校验工具列表，过滤重复项。"""

    if not isinstance(tools, list):
        raise ValueError(
            "enabled_tools 必须是列表"
        )

    if any(
        not isinstance(name, str)
        for name in tools
    ):
        raise ValueError(
            "工具名称必须是字符串"
        )

    unknown = set(tools) - AVAILABLE_TOOLS

    if unknown:
        raise ValueError(
            "存在未注册的工具："
            + ", ".join(sorted(unknown))
        )

    return list(dict.fromkeys(tools))


# ==========================================
# 2. 数据库记录转换
# ==========================================

def _row_to_agent(row):
    """将 SQLite Row 转换为前端可使用的字典。"""

    if row is None:
        return None

    agent = dict(row)

    agent["enabled_tools"] = json.loads(
        agent["enabled_tools"]
    )

    return agent


# ==========================================
# 3. 创建 Agent
# ==========================================

def create_agent(
    name,
    *,
    description="",
    personality="professional",
    response_style="balanced",
    custom_instructions="",
    enabled_tools=None,
    db_path=None,
):
    """
    创建并持久化一个 Agent。

    db_path 主要用于测试时指定临时数据库。
    """

    name = _validate_text(
        name,
        "Agent 名称",
        40,
        allow_empty=False,
    )

    description = _validate_text(
        description,
        "Agent 描述",
        300,
    )

    personality = _validate_choice(
        personality,
        "人格类型",
        PERSONALITIES,
    )

    response_style = _validate_choice(
        response_style,
        "回复风格",
        RESPONSE_STYLES,
    )

    custom_instructions = _validate_text(
        custom_instructions,
        "自定义指令",
        2000,
    )

    if enabled_tools is None:
        enabled_tools = list(
            database.DEFAULT_AGENT_TOOLS
        )

    enabled_tools = _validate_tools(
        enabled_tools
    )

    agent_id = str(uuid4())

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        with conn:
            conn.execute(
                """
                INSERT INTO agents (
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
                    agent_id,
                    name,
                    description,
                    personality,
                    response_style,
                    custom_instructions,
                    json.dumps(
                        enabled_tools,
                        ensure_ascii=False,
                    ),
                ),
            )

    finally:
        conn.close()

    return get_agent(
        agent_id,
        db_path=db_path,
    )


# ==========================================
# 4. 查询单个 Agent
# ==========================================

def get_agent(agent_id, *, db_path=None):
    """通过 ID 获取 Agent 配置。"""

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        row = conn.execute(
            """
            SELECT *
            FROM agents
            WHERE id = ?
            """,
            (agent_id,),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise LookupError(
            f"Agent 不存在：{agent_id}"
        )

    return _row_to_agent(row)


# ==========================================
# 5. 获取 Agent 列表
# ==========================================

def list_agents(*, db_path=None):
    """返回全部 Agent 配置。"""

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM agents
            ORDER BY created_at DESC, rowid DESC
            """
        ).fetchall()

    finally:
        conn.close()

    return [
        _row_to_agent(row)
        for row in rows
    ]


# ==========================================
# 6. 更新 Agent 配置
# ==========================================

def update_agent(
    agent_id,
    *,
    name=None,
    description=None,
    personality=None,
    response_style=None,
    custom_instructions=None,
    enabled_tools=None,
    db_path=None,
):
    """
    仅更新传入的字段。

    None 表示不修改该字段。
    空字符串可以用于清空描述或自定义指令。
    空列表可以用于禁用全部工具。
    """

    updates = {}

    if name is not None:
        updates["name"] = _validate_text(
            name,
            "Agent 名称",
            40,
            allow_empty=False,
        )

    if description is not None:
        updates["description"] = _validate_text(
            description,
            "Agent 描述",
            300,
        )

    if personality is not None:
        updates["personality"] = _validate_choice(
            personality,
            "人格类型",
            PERSONALITIES,
        )

    if response_style is not None:
        updates["response_style"] = _validate_choice(
            response_style,
            "回复风格",
            RESPONSE_STYLES,
        )

    if custom_instructions is not None:
        updates["custom_instructions"] = _validate_text(
            custom_instructions,
            "自定义指令",
            2000,
        )

    if enabled_tools is not None:
        updates["enabled_tools"] = json.dumps(
            _validate_tools(enabled_tools),
            ensure_ascii=False,
        )

    if not updates:
        raise ValueError(
            "至少需要提供一个更新字段"
        )

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    # 字段名来自上面固定的白名单，
    # 不是外部传入的任意 SQL 字符串。
    assignments = ", ".join(
        f"{column} = ?"
        for column in updates
    )

    sql = (
        f"UPDATE agents SET {assignments}, "
        "updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?"
    )

    params = [
        *updates.values(),
        agent_id,
    ]

    try:
        with conn:
            cursor = conn.execute(
                sql,
                params,
            )

            if cursor.rowcount == 0:
                raise LookupError(
                    f"Agent 不存在：{agent_id}"
                )

    finally:
        conn.close()

    return get_agent(
        agent_id,
        db_path=db_path,
    )
