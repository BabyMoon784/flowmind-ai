

import pytest
from fastapi.testclient import TestClient

import chat_routes
import session_store
from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_chat_sessions.db"

    monkeypatch.setattr(
        session_store,
        "DB_FILE",
        test_db
    )

    with TestClient(app) as test_client:
        yield test_client


def fake_chat(history, task_func, long_term_memory=""):
    return "你好，我是鱼鱼！"


def test_create_session(client, monkeypatch):
    monkeypatch.setattr(
        chat_routes, "chat_with_tools", fake_chat
    )

    response = client.post(
        "/chat",
        json={"message": "你好"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"]
    assert data["reply"] == "你好，我是鱼鱼！"
    assert len(data["history"]) == 2


def test_continue_session(client, monkeypatch):
    captured = []

    def record_chat(history, task_func, long_term_memory=""):
        captured.append(history)
        return "收到"

    monkeypatch.setattr(
        chat_routes, "chat_with_tools", record_chat
    )

    first = client.post(
        "/chat",
        json={"message": "我在学习 SQLite"}
    ).json()

    second = client.post(
        "/chat",
        json={
            "message": "我在学什么？",
            "session_id": first["session_id"]
        }
    )

    assert second.status_code == 200
    assert len(captured[1]) == 3
    assert captured[1][0]["content"] == "我在学习 SQLite"
    assert len(second.json()["history"]) == 4



def test_session_persistence(client, monkeypatch):
    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat
    )

    first = client.post(
        "/chat",
        json={"message": "测试持久化"}
    ).json()

    response = client.get(
        f"/chat/sessions/{first['session_id']}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["messages"][0]["content"] == "测试持久化"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["id"] > 0
    assert data["has_more"] is False



def test_unknown_session(client):
    response = client.get(
        "/chat/sessions/550e8400-e29b-41d4-a716-446655440000"
    )
    assert response.status_code == 404


def test_chat_empty_message(client):
    response = client.post(
        "/chat", json={"message": "   "}
    )
    assert response.status_code == 422


def test_chat_missing_message(client):
    response = client.post(
        "/chat", json={}
    )
    assert response.status_code == 422


def test_chat_memory_and_tool(client, monkeypatch):
    captured = {}

    def record_chat(history, task_func, long_term_memory=""):
        captured["summary_func"] = task_func
        captured["memory"] = long_term_memory
        return "测试成功"

    monkeypatch.setattr(
        chat_routes, "chat_with_tools", record_chat
    )
    monkeypatch.setattr(
    chat_routes,
    "format_agent_memories",
    lambda agent_id: "assistant_name: 鱼鱼"
)

    response = client.post(
        "/chat",
        json={
            "message": "查询任务",
            "use_long_term_memory": True
        }
    )

    assert response.status_code == 200
    assert captured["memory"] == "assistant_name: 鱼鱼"
    assert (
        captured["summary_func"]
        is chat_routes.service.get_task_summary
    )


def test_list_sessions(client, monkeypatch):
    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat
    )

    client.post(
        "/chat",
        json={"message": "学习 FastAPI"}
    )

    client.post(
        "/chat",
        json={"message": "学习 SQLite"}
    )

    response = client.get("/chat/sessions")

    assert response.status_code == 200

    sessions = response.json()

    assert len(sessions) == 2

    titles = {s["title"] for s in sessions}

    assert "学习 FastAPI" in titles
    assert "学习 SQLite" in titles


def test_delete_session(client, monkeypatch):
    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat
    )

    created = client.post(
        "/chat",
        json={"message": "待删除的测试对话"}
    ).json()

    session_id = created["session_id"]

    response = client.delete(
        f"/chat/sessions/{session_id}"
    )

    assert response.status_code == 200
    assert response.json()["deleted"] is True

    history = client.get(
        f"/chat/sessions/{session_id}"
    )

    assert history.status_code == 404


def test_delete_missing_session(client):
    response = client.delete(
        "/chat/sessions/"
        "550e8400-e29b-41d4-a716-446655440000"
    )

    assert response.status_code == 404



def test_chat_history_pagination(client, monkeypatch):
    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_chat
    )

    # 创建第一轮对话
    first = client.post(
        "/chat",
        json={"message": "第1轮用户消息"}
    ).json()

    session_id = first["session_id"]

    # 继续创建两轮对话
    for i in range(2, 4):
        response = client.post(
            "/chat",
            json={
                "message": f"第{i}轮用户消息",
                "session_id": session_id
            }
        )
        assert response.status_code == 200

    url = f"/chat/sessions/{session_id}"

    # 第一页：最新两条
    page1 = client.get(
        url,
        params={"limit": 2, "offset": 0}
    )

    assert page1.status_code == 200

    data1 = page1.json()

    assert len(data1["messages"]) == 2
    assert data1["messages"][0]["content"] == "第3轮用户消息"
    assert data1["has_more"] is True

    # 第二页：再往前两条
    page2 = client.get(
        url,
        params={"limit": 2, "offset": 2}
    )

    data2 = page2.json()

    assert len(data2["messages"]) == 2
    assert data2["messages"][0]["content"] == "第2轮用户消息"
    assert data2["has_more"] is True

    # 第三页：最早两条
    page3 = client.get(
        url,
        params={"limit": 2, "offset": 4}
    )

    data3 = page3.json()

    assert len(data3["messages"]) == 2
    assert data3["messages"][0]["content"] == "第1轮用户消息"
    assert data3["has_more"] is False

    # 确认消息 ID 没有重复
    all_ids = [
        m["id"]
        for page in (data1, data2, data3)
        for m in page["messages"]
    ]

    assert len(all_ids) == len(set(all_ids))



def test_chat_history_invalid_pagination(client):
    session_id = "550e8400-e29b-41d4-a716-446655440000"

    response = client.get(
        f"/chat/sessions/{session_id}",
        params={"limit": 0}
    )

    assert response.status_code == 422

    response = client.get(
        f"/chat/sessions/{session_id}",
        params={"limit": 101}
    )

    assert response.status_code == 422
