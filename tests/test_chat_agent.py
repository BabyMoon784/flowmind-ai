
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import agent_service
import ai_service
import chat_routes
import database
import session_store
from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database,
        "DB_FILE",
        tmp_path / "test_agents.db",
    )

    monkeypatch.setattr(
        session_store,
        "DB_FILE",
        tmp_path / "test_sessions.db",
    )

    with TestClient(app) as test_client:
        yield test_client


def fake_llm_client():
    message = SimpleNamespace(
        tool_calls=[],
        content="测试回复",
    )

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=message)
        ],
    )

    fake_client = MagicMock()

    fake_client.chat.completions.create.return_value = (
        response
    )

    return fake_client


def test_select_agent(client, monkeypatch):
    agent = agent_service.create_agent(
        "CodeMate",
        response_style="detailed",
    )

    captured = {}

    def fake_chat(
        history,
        task_summary_func,
        long_term_memory="",
        agent_config=None,
    ):
        captured["agent"] = agent_config
        return "你好，我是 CodeMate"

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
    assert captured["agent"]["id"] == agent["id"]
    assert response.json()["reply"] == (
        "你好，我是 CodeMate"
    )


def test_old_chat_request(client, monkeypatch):
    def old_fake_chat(
        history,
        task_summary_func,
        long_term_memory="",
    ):
        return "旧版接口正常"

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        old_fake_chat,
    )

    response = client.post(
        "/chat",
        json={"message": "你好"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == (
        "旧版接口正常"
    )


def test_unknown_agent(client):
    response = client.post(
        "/chat",
        json={
            "message": "你好",
            "agent_id": (
                "550e8400-e29b-41d4-a716-446655440000"
            ),
        },
    )

    assert response.status_code == 404


def test_invalid_agent_id(client):
    response = client.post(
        "/chat",
        json={
            "message": "你好",
            "agent_id": "invalid-id",
        },
    )

    assert response.status_code == 422


def test_dynamic_prompt_sent_to_llm(monkeypatch):
    fake_client = fake_llm_client()

    monkeypatch.setattr(
        ai_service,
        "client",
        fake_client,
    )

    config = {
        "name": "Nova",
        "description": "高效编程助手",
        "personality": "efficient",
        "response_style": "concise",
        "custom_instructions": (
            "优先给出 Python 示例。"
        ),
    }

    answer = ai_service.chat_with_tools(
        history=[
            {
                "role": "user",
                "content": "你好",
            }
        ],
        task_summary_func=lambda: {},
        agent_config=config,
    )

    assert answer == "测试回复"

    kwargs = (
        fake_client.chat.completions.create
        .call_args.kwargs
    )

    prompt = kwargs["messages"][0]["content"]

    assert "Nova" in prompt
    assert "高效编程助手" in prompt
    assert "回复简洁" in prompt
    assert "Python 示例" in prompt


def test_default_agent_from_database(
    client,
    monkeypatch,
):
    agent_service.update_agent(
        agent_service.DEFAULT_AGENT_ID,
        name="Customized Default",
        response_style="detailed",
    )

    fake_client = fake_llm_client()

    monkeypatch.setattr(
        ai_service,
        "client",
        fake_client,
    )

    answer = ai_service.chat_with_tools(
        history=[
            {
                "role": "user",
                "content": "你好",
            }
        ],
        task_summary_func=lambda: {},
    )

    assert answer == "测试回复"

    kwargs = (
        fake_client.chat.completions.create
        .call_args.kwargs
    )

    prompt = kwargs["messages"][0]["content"]

    assert "Customized Default" in prompt
    assert "详细的解释" in prompt
