
"""
Agent 长期记忆上下文模块。

Phase 3 Day 4:
- 不提供 query：保留 Day 3 的最近记忆模式
- 提供 query：使用相关性检索
- 限制记忆数量和上下文长度
"""

import memory_store

from memory_retrieval import (
    search_relevant_memories,
)


MAX_MEMORY_ITEMS = 30
MAX_MEMORY_CHARS = 6000


def format_agent_memories(
    agent_id,
    *,
    query=None,
    db_path=None,
    limit=MAX_MEMORY_ITEMS,
    max_chars=MAX_MEMORY_CHARS,
):
    """
    格式化指定 Agent 的记忆。

    query=None:
        兼容 Day 3，读取最近记忆。

    query="用户问题":
        按相关性检索。
        无匹配时返回空字符串。
    """

    if not isinstance(agent_id, str):
        raise ValueError(
            "agent_id 必须是字符串"
        )

    agent_id = agent_id.strip()

    if not agent_id:
        raise ValueError(
            "agent_id 不能为空"
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
        isinstance(max_chars, bool)
        or not isinstance(max_chars, int)
        or max_chars < 1
    ):
        raise ValueError(
            "max_chars 必须是正整数"
        )

    if query is None:

        # 兼容旧调用，读取最近记忆
        memories = memory_store.list_memories(
            agent_id,
            limit=limit,
            offset=0,
            db_path=db_path,
        )

    else:

        # Day 4：根据用户问题选取相关记忆
        memories = search_relevant_memories(
            agent_id,
            query,
            limit=limit,
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

        needed = len(line)

        if lines:
            needed += 1

        if used_chars + needed > max_chars:
            # 继续检查其他较短记忆
            continue

        lines.append(line)
        used_chars += needed

    return "\n".join(lines)
