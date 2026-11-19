
import pytest
from fastapi.testclient import TestClient

import chat_routes
import session_store

from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):

    monkeypatch.setattr(
        session_store,
        "DB_FILE",
        tmp_path / "attachment_sessions.db",
    )

    with TestClient(app) as test_client:
        yield test_client


def test_attachment_reaches_ai(client, monkeypatch):

    captured = {}

    def fake_ai(
        history,
        task_func,
        long_term_memory="",
        **kwargs,
    ):
        captured["history"] = history
        return "我已经阅读附件。"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_ai,
    )

    response = client.post(
        "/chat",
        json={
            "message": "请总结这份文件",
            "attachment": {
                "filename": "algorithm.txt",
                "text": "这份文档讲解并查集和路径压缩。",
            },
            "use_long_term_memory": False,
        },
    )

    assert response.status_code == 200

    # 确认附件正文确实发送给 AI
    model_input = captured["history"][-1]["content"]

    assert "并查集和路径压缩" in model_input
    assert "请总结这份文件" in model_input

    data = response.json()

    # 数据库保存附件名称，不保存正文
    saved_user_message = data["history"][0]["content"]

    assert "algorithm.txt" in saved_user_message
    assert "并查集和路径压缩" not in saved_user_message


def test_normal_chat_still_works(client, monkeypatch):

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        lambda *args, **kwargs: "普通对话成功",
    )

    response = client.post(
        "/chat",
        json={
            "message": "你好",
        },
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "普通对话成功"


def test_unsupported_attachment_type(client):

    response = client.post(
        "/chat",
        json={
            "message": "读取图片",
            "attachment": {
                "filename": "test.exe",
                "text": "假装是图片文本",
            },
        },
    )

    assert response.status_code == 422


def test_attachment_too_long(client):

    response = client.post(
        "/chat",
        json={
            "message": "总结",
            "attachment": {
                "filename": "notes.txt",
                "text": "a" * 16001,
            },
        },
    )

    assert response.status_code == 422


def test_attachment_not_reused_in_next_turn(
    client,
    monkeypatch,
):

    captured = []

    def fake_ai(
        history,
        task_func,
        long_term_memory="",
        **kwargs,
    ):
        captured.append(history)
        return "收到"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        fake_ai,
    )

    first = client.post(
        "/chat",
        json={
            "message": "阅读文件",
            "attachment": {
                "filename": "notes.txt",
                "text": "秘密测试内容ABC123",
            },
        },
    )

    assert first.status_code == 200

    second = client.post(
        "/chat",
        json={
            "message": "继续聊天",
            "session_id": first.json()["session_id"],
        },
    )

    assert second.status_code == 200

    # 下一轮不会自动重新注入附件正文
    second_history = str(captured[-1])

    assert "秘密测试内容ABC123" not in second_history
    assert "notes.txt" in second_history
