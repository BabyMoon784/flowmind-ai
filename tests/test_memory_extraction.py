
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import agent_service
import chat_routes
import database
import memory_extraction
import memory_routes
import memory_store
import session_store
import task_service

from api import app


DEFAULT_AGENT_ID = database.DEFAULT_AGENT_ID


@pytest.fixture
def client(tmp_path, monkeypatch):
    """每个测试使用独立的 SQLite 数据库。"""

    data_db = tmp_path / "flowmind_test.db"
    chat_db = tmp_path / "sessions_test.db"

    monkeypatch.setattr(
        database,
        "DB_FILE",
        data_db,
    )

    monkeypatch.setattr(
        task_service,
        "DB_FILE",
        data_db,
    )

    monkeypatch.setattr(
        session_store,
        "DB_FILE",
        chat_db,
    )

    with TestClient(app) as test_client:
        yield test_client


def sample_candidate():
    return {
        "memory_key": "programming_language",
        "content": "用户主要使用 C++",
        "memory_type": "profile",
        "importance": 4,
        "source": "conversation",
    }


# ==========================================
# 1. JSON 解析、校验与去重
# ==========================================

def test_parse_candidates_filters_duplicates():

    payload = {
        "memories": [
            {
                "memory_key": "programming_language",
                "content": "主要使用 C++",
                "memory_type": "profile",
                "importance": 4,
            },
            {
                "memory_key": "programming_language",
                "content": "重复的信息",
                "memory_type": "profile",
                "importance": 3,
            },
            {
                "memory_key": "bad",
                "content": "非法重要程度",
                "memory_type": "fact",
                "importance": 9,
            },
        ]
    }

    results = (
        memory_extraction.parse_memory_candidates(
            json.dumps(
                payload,
                ensure_ascii=False,
            )
        )
    )

    assert len(results) == 1
    assert results[0]["content"] == "主要使用 C++"
    assert results[0]["source"] == "conversation"


# ==========================================
# 2. 无效 JSON 不被接受
# ==========================================

@pytest.mark.parametrize(
    "raw_text",
    [
        "",
        "这不是 JSON",
    ],
)
def test_parse_invalid_json(raw_text):

    with pytest.raises(
        memory_extraction.MemoryExtractionError
    ):
        memory_extraction.parse_memory_candidates(
            raw_text
        )


# ==========================================
# 3. DeepSeek 使用 JSON 模式
# ==========================================

def test_deepseek_json_output(monkeypatch):

    captured = {}

    class FakeCompletions:

        def create(self, **kwargs):

            captured.update(kwargs)

            content = json.dumps(
                {
                    "memories": [
                        {
                            "memory_key": "career_goal",
                            "content": "希望从事 AI 应用开发",
                            "memory_type": "goal",
                            "importance": 5,
                        }
                    ]
                },
                ensure_ascii=False,
            )

            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=content
                        ),
                    )
                ]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions()
        )
    )

    monkeypatch.setattr(
        memory_extraction.ai_service,
        "client",
        fake_client,
    )

    results = (
        memory_extraction.extract_memory_candidates(
            "我希望从事 AI 应用开发"
        )
    )

    assert captured["model"] == "deepseek-chat"

    assert captured["response_format"] == {
        "type": "json_object"
    }

    assert len(results) == 1
    assert results[0]["memory_key"] == "career_goal"


# ==========================================
# 4. 提取只返回预览，不自动保存
# ==========================================

def test_preview_requires_confirmation(
    client,
    monkeypatch,
):

    monkeypatch.setattr(
        memory_routes,
        "extract_memory_candidates",
        lambda text: [sample_candidate()],
    )

    response = client.post(
        "/memories/extract",
        json={
            "agent_id": DEFAULT_AGENT_ID,
            "text": "我主要使用 C++",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["count"] == 1
    assert result["saved"] is False
    assert result["requires_confirmation"] is True

    # 尚未确认，数据库必须为空
    before = client.get(
        "/memories",
        params={
            "agent_id": DEFAULT_AGENT_ID,
        },
    )

    assert before.status_code == 200
    assert before.json()["count"] == 0

    # 模拟用户确认：
    # 通过现有 POST /memories 显式保存
    confirmed = client.post(
        "/memories",
        json={
            "agent_id": DEFAULT_AGENT_ID,
            **result["candidates"][0],
        },
    )

    assert confirmed.status_code == 201

    assert (
        confirmed.json()["source"]
        == "conversation"
    )

    # 确认以后才应出现数据库记录
    after = client.get(
        "/memories",
        params={
            "agent_id": DEFAULT_AGENT_ID,
        },
    )

    assert after.json()["count"] == 1


# ==========================================
# 5. 从已有聊天会话提取
# ==========================================

def test_extract_from_existing_session(
    client,
    monkeypatch,
):

    captured = {}

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        lambda *args, **kwargs: "模拟 AI 回复",
    )

    def fake_extract(text):
        captured["source_text"] = text
        return []

    monkeypatch.setattr(
        memory_routes,
        "extract_memory_candidates",
        fake_extract,
    )

    first = client.post(
        "/chat",
        json={
            "message": "我正在学习 Python",
            "agent_id": DEFAULT_AGENT_ID,
        },
    )

    assert first.status_code == 200

    session_id = first.json()["session_id"]

    second = client.post(
        "/chat",
        json={
            "message": "我希望从事 AI 应用开发",
            "session_id": session_id,
        },
    )

    assert second.status_code == 200

    response = client.post(
        "/memories/extract",
        json={
            "agent_id": DEFAULT_AGENT_ID,
            "session_id": session_id,
        },
    )

    assert response.status_code == 200

    text = captured["source_text"]

    assert "我正在学习 Python" in text
    assert "我希望从事 AI 应用开发" in text

    # 不能把 AI 自己的回答当成用户事实
    assert "模拟 AI 回复" not in text


# ==========================================
# 6. 不允许提取其他 Agent 的聊天会话
# ==========================================

def test_wrong_agent_session_conflict(
    client,
    monkeypatch,
):

    monkeypatch.setattr(
        chat_routes,
        "chat_with_tools",
        lambda *args, **kwargs: "模拟回答",
    )

    other_agent = agent_service.create_agent(
        "Memory Other Agent",
        enabled_tools=[],
    )["id"]

    first = client.post(
        "/chat",
        json={
            "message": "我在学习 C++",
            "agent_id": DEFAULT_AGENT_ID,
        },
    )

    assert first.status_code == 200

    response = client.post(
        "/memories/extract",
        json={
            "agent_id": other_agent,
            "session_id": first.json()["session_id"],
        },
    )

    assert response.status_code == 409


# ==========================================
# 7. 无效请求返回 422
# ==========================================

@pytest.mark.parametrize(
    "body",
    [
        {
            "agent_id": DEFAULT_AGENT_ID,
        },
        {
            "agent_id": DEFAULT_AGENT_ID,
            "text": "你好",
            "session_id": str(uuid4()),
        },
        {
            "agent_id": DEFAULT_AGENT_ID,
            "text": "   ",
        },
    ],
)
def test_invalid_extract_request(
    client,
    body,
):

    response = client.post(
        "/memories/extract",
        json=body,
    )

    assert response.status_code == 422


# ==========================================
# 8. 不存在的 Agent 返回 404
# ==========================================

def test_unknown_agent(client):

    response = client.post(
        "/memories/extract",
        json={
            "agent_id": str(uuid4()),
            "text": "我正在学习 Python",
        },
    )

    assert response.status_code == 404


# ==========================================
# 9. 不存在的会话返回 404
# ==========================================

def test_unknown_session(client):

    response = client.post(
        "/memories/extract",
        json={
            "agent_id": DEFAULT_AGENT_ID,
            "session_id": str(uuid4()),
        },
    )

    assert response.status_code == 404


# ==========================================
# 10. 模型输出异常返回 502
# ==========================================

def test_invalid_model_output(
    client,
    monkeypatch,
):

    def broken_extract(text):
        raise memory_extraction.MemoryExtractionError(
            "模型返回了空内容"
        )

    monkeypatch.setattr(
        memory_routes,
        "extract_memory_candidates",
        broken_extract,
    )

    response = client.post(
        "/memories/extract",
        json={
            "agent_id": DEFAULT_AGENT_ID,
            "text": "我正在学习 Python",
        },
    )

    assert response.status_code == 502


# ==========================================
# 11. 缺少 API Key 返回 503
# ==========================================

def test_missing_api_key(
    client,
    monkeypatch,
):

    monkeypatch.setattr(
        memory_extraction.ai_service,
        "client",
        None,
    )

    response = client.post(
        "/memories/extract",
        json={
            "agent_id": DEFAULT_AGENT_ID,
            "text": "我正在学习 Python",
        },
    )

    assert response.status_code == 503
