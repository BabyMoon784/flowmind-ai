
import json

import pytest
from fastapi.testclient import TestClient

import agent_service
import chat_routes
import database
import long_term_memory
import memory_store
import session_store
import task_service

from agent_memory_context import format_agent_memories
from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """让每项测试使用独立数据库。"""

    test_db = tmp_path / "flowmind_test.db"
    session_db = tmp_path / "sessions_test.db"

    monkeypatch.setattr(
        database,
        "DB_FILE",
        test_db,
    )

    monkeypatch.setattr(
        task_service,
        "DB_FILE",
        test_db,
    )

    monkeypatch.setattr(
        session_store,
        "DB_FILE",
        session_db,
    )

    database.init_database()
    session_store.init_database()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_ai(monkeypatch):
    """模拟 DeepSeek，记录传入的记忆。"""

    received_memories = []

    def fake_chat(
        history,
        task_summary_func,
        **kwargs,
    ):
        received_memories.append(
            kwargs.get("long_term_memory", "")
        )

        return "这是测试回复"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat,
    )

    return received_memories


def make_agent(name):
    return agent_service.create_agent(
        name,
        enabled_tools=[],
    )["id"]


# ==========================================
# 测试 1：不同 Agent 的记忆完全隔离
# ==========================================

def test_agent_memory_context_isolated(client):

    agent_a = make_agent("CodeMate Test")
    agent_b = make_agent("Friday Test")

    memory_store.create_memory(
        agent_a,
        "programming",
        "主要使用 C++",
        db_path=database.DB_FILE,
    )

    memory_store.create_memory(
        agent_b,
        "style",
        "优先简洁回答",
        db_path=database.DB_FILE,
    )

    context_a = format_agent_memories(agent_a)
    context_b = format_agent_memories(agent_b)

    assert "主要使用 C++" in context_a
    assert "优先简洁回答" not in context_a

    assert "优先简洁回答" in context_b
    assert "主要使用 C++" not in context_b


# ==========================================
# 测试 2：聊天使用当前 Agent 的记忆
# ==========================================

def test_chat_loads_agent_memory(
    client,
    fake_ai,
):

    agent_id = make_agent("Memory Chat Agent")

    memory_store.create_memory(
        agent_id,
        "language",
        "优先使用中文",
        memory_type="preference",
    )

    response = client.post(
        "/chat",
        json={
            "message": "你记得我的语言偏好吗？",
            "agent_id": agent_id,
            "use_long_term_memory": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["agent_id"] == agent_id

    assert len(fake_ai) == 1
    assert "优先使用中文" in fake_ai[0]


# ==========================================
# 测试 3：旧会话沿用原来的 Agent 和记忆
# ==========================================

def test_existing_session_keeps_agent_memory(
    client,
    fake_ai,
):

    agent_a = make_agent("Bound Agent A")
    agent_b = make_agent("Other Agent B")

    memory_store.create_memory(
        agent_a,
        "private_a",
        "只属于 Agent A 的记忆",
    )

    memory_store.create_memory(
        agent_b,
        "private_b",
        "只属于 Agent B 的记忆",
    )

    first = client.post(
        "/chat",
        json={
            "message": "你好",
            "agent_id": agent_a,
            "use_long_term_memory": True,
        },
    )

    assert first.status_code == 200

    session_id = first.json()["session_id"]

    # 第二轮不传 agent_id，
    # 应该自动使用会话绑定的 Agent A。
    second = client.post(
        "/chat",
        json={
            "message": "继续刚才的话题",
            "session_id": session_id,
            "use_long_term_memory": True,
        },
    )

    assert second.status_code == 200
    assert second.json()["agent_id"] == agent_a

    assert "只属于 Agent A" in fake_ai[-1]
    assert "只属于 Agent B" not in fake_ai[-1]

    # 尝试把同一会话切换到 B
    conflict = client.post(
        "/chat",
        json={
            "message": "切换 Agent",
            "session_id": session_id,
            "agent_id": agent_b,
            "use_long_term_memory": True,
        },
    )

    assert conflict.status_code == 409


# ==========================================
# 测试 4：长期记忆开关关闭
# ==========================================

def test_memory_disabled(
    client,
    fake_ai,
):

    agent_id = make_agent("Memory Disabled Agent")

    memory_store.create_memory(
        agent_id,
        "secret",
        "开关关闭时不应该传递",
    )

    response = client.post(
        "/chat",
        json={
            "message": "你好",
            "agent_id": agent_id,
            "use_long_term_memory": False,
        },
    )

    assert response.status_code == 200

    assert fake_ai[-1] == ""


# ==========================================
# 测试 5：不自动读取旧版 JSON
# ==========================================

def test_legacy_json_not_loaded_automatically(
    client,
    fake_ai,
    monkeypatch,
    tmp_path,
):

    legacy_path = tmp_path / "legacy_memory.json"

    legacy_path.write_text(
        json.dumps(
            {
                "old_secret": "旧版 JSON 中的私人内容",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        long_term_memory,
        "MEMORY_FILE",
        legacy_path,
    )

    response = client.post(
        "/chat",
        json={
            "message": "你好",
            "use_long_term_memory": True,
        },
    )

    assert response.status_code == 200

    # 默认 Agent 的 SQLite 中没有记忆，
    # 不应自动读取全局旧版 JSON。
    assert fake_ai[-1] == ""

    # 旧文件本身仍然存在。
    assert legacy_path.exists()
