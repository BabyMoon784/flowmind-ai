
"""
Agent 长期记忆上下文模块。

从 SQLite 读取指定 Agent 的记忆，
转换为可传入 Prompt Builder 的文本。
"""

import memory_store


MAX_MEMORY_ITEMS = 30
MAX_MEMORY_CHARS = 6000


def format_agent_memories(
    agent_id,
    *,
    db_path=None,
    limit=MAX_MEMORY_ITEMS,
    max_chars=MAX_MEMORY_CHARS,
):
    """
    格式化指定 Agent 的长期记忆。

    返回:
        str: 格式化后的记忆文本

    特点:
        1. 只查询指定 Agent
        2. 不混用其他 Agent 的记忆
        3. 限制记忆数量和总长度
        4. 没有记忆时返回空字符串
    """

    if not isinstance(agent_id, str):
        raise ValueError("agent_id 必须是字符串")

    agent_id = agent_id.strip()

    if not agent_id:
        raise ValueError("agent_id 不能为空")

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 500
    ):
        raise ValueError("limit 必须是 1～500 的整数")

    if (
        isinstance(max_chars, bool)
        or not isinstance(max_chars, int)
        or max_chars < 1
    ):
        raise ValueError("max_chars 必须是正整数")

    # Day 1 的记忆服务已经提供 Agent 隔离
    memories = memory_store.list_memories(
        agent_id,
        limit=limit,
        offset=0,
        db_path=db_path,
    )

    if not memories:
        return ""

    lines = []
    used_chars = 0

    for memory in memories:

        line = (
            f"[{memory['memory_type']}] "
            f"{memory['memory_key']}: "
            f"{memory['content']}"
        )

        needed = len(line) + (1 if lines else 0)

        # 超出上下文预算时停止加入新记忆
        if used_chars + needed > max_chars:
            break

        lines.append(line)
        used_chars += needed

    return "\n".join(lines)
