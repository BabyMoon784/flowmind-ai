
import pytest

import agent_service
import database
import memory_store

from memory_retrieval import (
    tokenize,
    search_relevant_memories,
)
from agent_memory_context import (
    format_agent_memories,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "retrieval_test.db"
    database.init_database(path)
    return path


@pytest.fixture
def agent_id():
    return database.DEFAULT_AGENT_ID


# 1. Python 相关记忆优先
def test_python_relevance(db_path, agent_id):
    relevant = memory_store.create_memory(
        agent_id,
        "python_study",
        "正在学习 Python 后端开发",
        memory_type="project",
        db_path=db_path,
    )

    memory_store.create_memory(
        agent_id,
        "clothing",
        "喜欢黑白灰配色",
        memory_type="preference",
        db_path=db_path,
    )

    results = search_relevant_memories(
        agent_id,
        "Python 应该怎么学？",
        db_path=db_path,
    )

    assert len(results) == 1
    assert results[0]["id"] == relevant["id"]
    assert results[0]["relevance_score"] > 0


# 2. 支持英文 key 与中文问题对应
def test_language_alias(db_path, agent_id):
    memory_store.create_memory(
        agent_id,
        "language",
        "优先使用中文",
        memory_type="preference",
        db_path=db_path,
    )

    context = format_agent_memories(
        agent_id,
        query="我的语言偏好是什么？",
        db_path=db_path,
    )

    assert "优先使用中文" in context


# 3. 没有命中时不注入无关记忆
def test_no_irrelevant_memory(db_path, agent_id):
    memory_store.create_memory(
        agent_id,
        "python",
        "正在学习 Python",
        db_path=db_path,
    )

    results = search_relevant_memories(
        agent_id,
        "周末天气",
        db_path=db_path,
    )

    assert results == []

    context = format_agent_memories(
        agent_id,
        query="周末天气",
        db_path=db_path,
    )

    assert context == ""


# 4. 不同 Agent 的检索空间隔离
def test_agent_isolation(db_path, agent_id):
    other_agent = agent_service.create_agent(
        "Other Agent",
        enabled_tools=[],
        db_path=db_path,
    )["id"]

    memory_store.create_memory(
        agent_id,
        "python",
        "My Agent 的 Python 学习计划",
        db_path=db_path,
    )

    memory_store.create_memory(
        other_agent,
        "python",
        "Other Agent 的 Python 项目",
        db_path=db_path,
    )

    results = search_relevant_memories(
        other_agent,
        "Python",
        db_path=db_path,
    )

    assert len(results) == 1
    assert results[0]["agent_id"] == other_agent
    assert "Other Agent" in results[0]["content"]


# 5. 相关性相同时，重要记忆排前面
def test_importance_tiebreak(db_path, agent_id):
    memory_store.create_memory(
        agent_id,
        "backend_low",
        "Python",
        importance=1,
        db_path=db_path,
    )

    high = memory_store.create_memory(
        agent_id,
        "backend_high",
        "Python",
        importance=5,
        db_path=db_path,
    )

    results = search_relevant_memories(
        agent_id,
        "Python",
        db_path=db_path,
    )

    assert len(results) == 2
    assert results[0]["id"] == high["id"]


# 6. 中文词项匹配
def test_chinese_token_matching(db_path, agent_id):
    memory_store.create_memory(
        agent_id,
        "算法项目",
        "正在学习动态规划",
        memory_type="project",
        db_path=db_path,
    )

    context = format_agent_memories(
        agent_id,
        query="我想继续学习动态规划",
        db_path=db_path,
    )

    assert "动态规划" in context
    assert "python" in tokenize("学习 Python")


# 7. 无 query 时兼容 Day 3
def test_day3_compatibility(db_path, agent_id):
    memory_store.create_memory(
        agent_id,
        "language",
        "喜欢中文",
        db_path=db_path,
    )

    context = format_agent_memories(
        agent_id,
        db_path=db_path,
    )

    assert "喜欢中文" in context


# 8. 限制上下文长度
def test_context_char_budget(db_path, agent_id):
    memory_store.create_memory(
        agent_id,
        "python",
        "Python 是当前主要学习语言",
        db_path=db_path,
    )

    context = format_agent_memories(
        agent_id,
        query="Python",
        max_chars=40,
        db_path=db_path,
    )

    assert len(context) <= 40


# 9. 检索参数校验
def test_search_validation(db_path, agent_id):
    with pytest.raises(ValueError):
        search_relevant_memories(
            agent_id,
            "Python",
            limit=0,
            db_path=db_path,
        )

    with pytest.raises(ValueError):
        search_relevant_memories(
            agent_id,
            None,
            db_path=db_path,
        )

    assert search_relevant_memories(
        agent_id,
        "",
        db_path=db_path,
    ) == []
