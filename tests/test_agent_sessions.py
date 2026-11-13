
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import agent_service
import chat_routes
import database
import session_store

from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Agent 配置和聊天历史使用临时数据库。
    # 不修改真实用户数据。
    monkeypatch.setattr(
        database,
        "DB_FILE",
        tmp_path / "agents.db",
    )

    monkeypatch.setattr(
        session_store,
        "DB_FILE",
        tmp_path / "chat_sessions.db",
    )

    with TestClient(app) as test_client:
        yield test_client


def create_test_agent(name):
    return agent_service.create_agent(
        name,
        enabled_tools=["list_tasks"],
    )


def test_new_session_binds_agent(
    client,
    monkeypatch,
):
    """新建会话应保存指定 Agent 的 ID。"""

    agent = create_test_agent("CodeMate")

    def fake_chat(
        history,
        task_func,
        long_term_memory="",
        agent_config=None,
    ):
        return "你好，我是 CodeMate。"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat,
    )

    response = client.post(
        "/chat",
        json={
            "message": "你好",
            "agent_id": agent["id"],
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["agent_id"] == agent["id"]

    session = session_store.get_session(
        result["session_id"]
    )

    assert session["agent_id"] == agent["id"]


def test_continue_uses_bound_agent(
    client,
    monkeypatch,
):
    """不传 agent_id 时自动恢复绑定。"""

    agent = create_test_agent("CodeMate")

    captured = []

    def fake_chat(
        history,
        task_func,
        long_term_memory="",
        agent_config=None,
    ):
        captured.append({
            "agent": agent_config,
            "history": history,
        })

        return "收到"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat,
    )

    first = client.post(
        "/chat",
        json={
            "message": "我正在学习 Python",
            "agent_id": agent["id"],
        },
    ).json()

    second = client.post(
        "/chat",
        json={
            "message": "我正在学什么？",
            "session_id": first["session_id"],
        },
    )

    assert second.status_code == 200

    assert second.json()["agent_id"] == agent["id"]

    assert captured[1]["agent"]["id"] == agent["id"]

    assert (
        captured[1]["history"][0]["content"]
        == "我正在学习 Python"
    )


def test_cross_agent_switch_returns_409(
    client,
    monkeypatch,
):
    """同一会话不能切换到其他 Agent。"""

    agent_a = create_test_agent("CodeMate")
    agent_b = create_test_agent("Nova")

    calls = []

    def fake_chat(
        history,
        task_func,
        long_term_memory="",
        agent_config=None,
    ):
        calls.append(agent_config["id"])
        return "正常回复"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat,
    )

    first = client.post(
        "/chat",
        json={
            "message": "你好",
            "agent_id": agent_a["id"],
        },
    ).json()

    before = session_store.load_history(
        first["session_id"]
    )

    response = client.post(
        "/chat",
        json={
            "message": "切换到 Nova",
            "session_id": first["session_id"],
            "agent_id": agent_b["id"],
        },
    )

    assert response.status_code == 409

    # 越权切换在调用 AI 前就已经被拒绝
    assert calls == [agent_a["id"]]

    # 历史消息不能发生变化
    after = session_store.load_history(
        first["session_id"]
    )

    assert after == before


def test_default_agent_backward_compatible(
    client,
    monkeypatch,
):
    """旧版聊天请求不需要 agent_config 参数。"""

    def old_fake_chat(
        history,
        task_func,
        long_term_memory="",
    ):
        return "旧接口正常"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        old_fake_chat,
    )

    first = client.post(
        "/chat",
        json={"message": "你好"},
    )

    assert first.status_code == 200

    result = first.json()

    assert result["agent_id"] == (
        database.DEFAULT_AGENT_ID
    )

    second = client.post(
        "/chat",
        json={
            "message": "继续聊天",
            "session_id": result["session_id"],
        },
    )

    assert second.status_code == 200
    assert second.json()["reply"] == "旧接口正常"


def test_session_api_exposes_agent_id(
    client,
    monkeypatch,
):
    """会话列表和历史接口应返回绑定关系。"""

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        lambda history, task_func,
        long_term_memory="": "测试回复",
    )

    created = client.post(
        "/chat",
        json={"message": "测试会话"},
    ).json()

    sessions = client.get(
        "/chat/sessions"
    ).json()

    assert sessions[0]["agent_id"] == (
        database.DEFAULT_AGENT_ID
    )

    history = client.get(
        f"/chat/sessions/{created['session_id']}"
    )

    assert history.status_code == 200

    assert history.json()["agent_id"] == (
        database.DEFAULT_AGENT_ID
    )

    assert len(history.json()["messages"]) == 2


def test_legacy_database_migration(
    client,
):
    """
    模拟旧版数据库：
    sessions 表没有 agent_id。
    验证迁移不删除聊天历史。
    """

    session_id = str(uuid4())

    # 手工创建旧格式的 SQLite 数据库
    conn = sqlite3.connect(
        session_store.DB_FILE
    )

    try:
        with conn:
            conn.execute("""
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            """)

            conn.execute(
                "INSERT INTO sessions (id) VALUES (?)",
                (session_id,),
            )

            conn.execute(
                """
                INSERT INTO messages (
                    session_id, role, content
                )
                VALUES (?, ?, ?)
                """,
                (
                    session_id,
                    "user",
                    "这是一条旧消息",
                ),
            )

    finally:
        conn.close()

    # 迁移执行两次也不能丢失数据
    session_store.init_database()
    session_store.init_database()

    session = session_store.get_session(
        session_id
    )

    assert session["agent_id"] == (
        database.DEFAULT_AGENT_ID
    )

    history = session_store.load_history(
        session_id
    )

    assert len(history) == 1
    assert history[0]["content"] == (
        "这是一条旧消息"
    )


def test_save_turn_rechecks_binding(
    client,
):
    """数据层也必须阻止跨 Agent 写入。"""

    session_store.init_database()

    session_id = str(uuid4())

    agent_a = create_test_agent("Agent A")
    agent_b = create_test_agent("Agent B")

    session_store.save_turn(
        session_id,
        "第一条消息",
        "第一条回复",
        new_session=True,
        agent_id=agent_a["id"],
    )

    with pytest.raises(
        session_store.SessionAgentMismatchError
    ):
        session_store.save_turn(
            session_id,
            "不应保存的消息",
            "不应保存的回复",
            agent_id=agent_b["id"],
        )

    history = session_store.load_history(
        session_id
    )

    assert len(history) == 2
    assert history[0]["content"] == "第一条消息"


def test_unknown_session_returns_404(
    client,
):
    """不存在的聊天会话应返回 404。"""

    response = client.post(
        "/chat",
        json={
            "message": "继续聊天",
            "session_id": str(uuid4()),
        },
    )

    assert response.status_code == 404


def test_unknown_agent_returns_404(
    client,
):
    """不存在的 Agent 不能创建聊天会话。"""

    response = client.post(
        "/chat",
        json={
            "message": "你好",
            "agent_id": str(uuid4()),
        },
    )

    assert response.status_code == 404

    # 未成功创建的聊天不能留下空会话
    assert client.get("/chat/sessions").json() == []
