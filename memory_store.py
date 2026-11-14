
import sqlite3
from uuid import uuid4

import database


# ==========================================
# 1. 记忆类型与来源
# ==========================================

MEMORY_TYPES = {
    "profile",
    "preference",
    "project",
    "fact",
    "goal",
}

MEMORY_SOURCES = {
    "manual",
    "conversation",
    "import",
    "system",
}


# ==========================================
# 2. 参数校验
# ==========================================

def _validate_text(
    value,
    field_name,
    max_length,
):
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name}必须是字符串"
        )

    value = value.strip()

    if not value:
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


def _validate_importance(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= 5
    ):
        raise ValueError(
            "importance 必须是 1～5 的整数"
        )

    return value


def _validate_agent_id(agent_id):
    return _validate_text(
        agent_id,
        "Agent ID",
        64,
    )


def _validate_memory_id(memory_id):
    return _validate_text(
        memory_id,
        "Memory ID",
        64,
    )


def _ensure_agent_exists(conn, agent_id):
    row = conn.execute(
        """
        SELECT id
        FROM agents
        WHERE id = ?
        """,
        (agent_id,),
    ).fetchone()

    if row is None:
        raise LookupError(
            f"Agent 不存在：{agent_id}"
        )


def _row_to_memory(row):
    if row is None:
        return None

    return dict(row)


def _handle_integrity_error(error):
    """将同一 Agent 下的记忆名称冲突转换为可读错误。"""

    message = str(error)

    if (
        "agent_memories.agent_id" in message
        and "agent_memories.memory_key" in message
    ):
        raise ValueError(
            "该 Agent 已存在同名记忆，请修改名称或更新原记忆"
        ) from error

    raise error


# ==========================================
# 3. 创建记忆
# ==========================================

def create_memory(
    agent_id,
    memory_key,
    content,
    *,
    memory_type="fact",
    source="manual",
    importance=3,
    db_path=None,
):
    """创建一条长期记忆。"""

    agent_id = _validate_agent_id(agent_id)

    memory_key = _validate_text(
        memory_key,
        "记忆名称",
        100,
    )

    content = _validate_text(
        content,
        "记忆内容",
        3000,
    )

    memory_type = _validate_choice(
        memory_type,
        "记忆类型",
        MEMORY_TYPES,
    )

    source = _validate_choice(
        source,
        "记忆来源",
        MEMORY_SOURCES,
    )

    importance = _validate_importance(
        importance
    )

    memory_id = str(uuid4())

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        try:
            with conn:

                _ensure_agent_exists(
                    conn,
                    agent_id,
                )

                conn.execute(
                    """
                    INSERT INTO agent_memories (
                        id,
                        agent_id,
                        memory_key,
                        memory_type,
                        content,
                        source,
                        importance
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        agent_id,
                        memory_key,
                        memory_type,
                        content,
                        source,
                        importance,
                    ),
                )

        except sqlite3.IntegrityError as error:
            _handle_integrity_error(error)

        row = conn.execute(
            """
            SELECT *
            FROM agent_memories
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()

        return _row_to_memory(row)

    finally:
        conn.close()


# ==========================================
# 4. 查询单条记忆
# ==========================================

def get_memory(
    memory_id,
    agent_id,
    *,
    db_path=None,
):
    """
    根据记忆 ID 和 Agent ID 查询。

    如果记忆不属于该 Agent，返回 None。
    """

    memory_id = _validate_memory_id(
        memory_id
    )

    agent_id = _validate_agent_id(
        agent_id
    )

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        _ensure_agent_exists(
            conn,
            agent_id,
        )

        row = conn.execute(
            """
            SELECT *
            FROM agent_memories
            WHERE id = ?
              AND agent_id = ?
            """,
            (
                memory_id,
                agent_id,
            ),
        ).fetchone()

        return _row_to_memory(row)

    finally:
        conn.close()


# ==========================================
# 5. 查询 Agent 的记忆列表
# ==========================================

def list_memories(
    agent_id,
    *,
    memory_type=None,
    limit=100,
    offset=0,
    db_path=None,
):
    """获取指定 Agent 的记忆列表。"""

    agent_id = _validate_agent_id(
        agent_id
    )

    if memory_type is not None:
        memory_type = _validate_choice(
            memory_type,
            "记忆类型",
            MEMORY_TYPES,
        )

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 500
    ):
        raise ValueError(
            "limit 必须是 1～500 的整数"
        )

    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
    ):
        raise ValueError(
            "offset 必须是非负整数"
        )

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        _ensure_agent_exists(
            conn,
            agent_id,
        )

        sql = """
            SELECT *
            FROM agent_memories
            WHERE agent_id = ?
        """

        params = [agent_id]

        if memory_type is not None:
            sql += " AND memory_type = ?"
            params.append(memory_type)

        sql += """
            ORDER BY
                updated_at DESC,
                created_at DESC,
                id DESC
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        rows = conn.execute(
            sql,
            params,
        ).fetchall()

        return [
            _row_to_memory(row)
            for row in rows
        ]

    finally:
        conn.close()


# ==========================================
# 6. 更新记忆
# ==========================================

def update_memory(
    memory_id,
    agent_id,
    *,
    memory_key=None,
    content=None,
    memory_type=None,
    source=None,
    importance=None,
    db_path=None,
):
    """更新指定 Agent 的一条记忆。"""

    memory_id = _validate_memory_id(
        memory_id
    )

    agent_id = _validate_agent_id(
        agent_id
    )

    updates = {}

    if memory_key is not None:
        updates["memory_key"] = _validate_text(
            memory_key,
            "记忆名称",
            100,
        )

    if content is not None:
        updates["content"] = _validate_text(
            content,
            "记忆内容",
            3000,
        )

    if memory_type is not None:
        updates["memory_type"] = _validate_choice(
            memory_type,
            "记忆类型",
            MEMORY_TYPES,
        )

    if source is not None:
        updates["source"] = _validate_choice(
            source,
            "记忆来源",
            MEMORY_SOURCES,
        )

    if importance is not None:
        updates["importance"] = _validate_importance(
            importance
        )

    if not updates:
        raise ValueError(
            "至少需要提供一个更新字段"
        )

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        try:
            with conn:

                _ensure_agent_exists(
                    conn,
                    agent_id,
                )

                assignments = ", ".join(
                    f"{column} = ?"
                    for column in updates
                )

                sql = (
                    f"UPDATE agent_memories "
                    f"SET {assignments}, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ? AND agent_id = ?"
                )

                params = [
                    *updates.values(),
                    memory_id,
                    agent_id,
                ]

                cursor = conn.execute(
                    sql,
                    params,
                )

                if cursor.rowcount == 0:
                    raise LookupError(
                        f"记忆不存在：{memory_id}"
                    )

        except sqlite3.IntegrityError as error:
            _handle_integrity_error(error)

        row = conn.execute(
            """
            SELECT *
            FROM agent_memories
            WHERE id = ?
              AND agent_id = ?
            """,
            (
                memory_id,
                agent_id,
            ),
        ).fetchone()

        return _row_to_memory(row)

    finally:
        conn.close()


# ==========================================
# 7. 删除记忆
# ==========================================

def delete_memory(
    memory_id,
    agent_id,
    *,
    db_path=None,
):
    """
    删除指定 Agent 的记忆。

    成功返回 True，不存在或不属于该 Agent 返回 False。
    """

    memory_id = _validate_memory_id(
        memory_id
    )

    agent_id = _validate_agent_id(
        agent_id
    )

    database.init_database(db_path)

    conn = database.get_connection(db_path)

    try:
        with conn:

            _ensure_agent_exists(
                conn,
                agent_id,
            )

            cursor = conn.execute(
                """
                DELETE FROM agent_memories
                WHERE id = ?
                  AND agent_id = ?
                """,
                (
                    memory_id,
                    agent_id,
                ),
            )

            return cursor.rowcount > 0

    finally:
        conn.close()
