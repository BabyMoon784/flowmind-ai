
import sqlite3

import pytest
from fastapi.testclient import TestClient

import database
import agent_routes
from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 每个测试使用自己的临时 SQLite 数据库
    # 不会修改真实的 flowmind.db
    test_db = tmp_path / "test_agent_routes.db"

    monkeypatch.setattr(
        database,
        "DB_FILE",
        test_db,
    )

    with TestClient(app) as test_client:
        yield test_client


# ==========================================
# 1. 默认 Agent 存在
# ==========================================

def test_list_default_agent(client):
    response = client.get("/agents")

    assert response.status_code == 200

    agents = response.json()

    assert len(agents) == 1
    assert agents[0]["name"] == "My Agent"
    assert agents[0]["id"] == database.DEFAULT_AGENT_ID


# ==========================================
# 2. 创建和查询 Agent
# ==========================================

def test_create_and_get_agent(client):
    response = client.post(
        "/agents",
        json={
            "name": "Friday",
            "description": "编程助手",
            "personality": "professional",
            "response_style": "detailed",
            "custom_instructions": "请用中文解释代码。",
            "enabled_tools": [
                "list_tasks",
                "get_task_summary",
            ],
        },
    )

    assert response.status_code == 201

    created = response.json()

    assert created["id"]
    assert created["name"] == "Friday"
    assert created["response_style"] == "detailed"

    get_response = client.get(
        f"/agents/{created['id']}"
    )

    assert get_response.status_code == 200
    assert get_response.json() == created

    list_response = client.get("/agents")

    assert len(list_response.json()) == 2


# ==========================================
# 3. PATCH 只修改指定字段
# ==========================================

def test_patch_agent(client):
    created = client.post(
        "/agents",
        json={
            "name": "Original",
            "description": "原始描述",
            "personality": "professional",
        },
    ).json()

    response = client.patch(
        f"/agents/{created['id']}",
        json={
            "name": "Nova",
            "personality": "creative",
        },
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["name"] == "Nova"
    assert updated["personality"] == "creative"

    # 没有指定的字段应保持原样
    assert updated["description"] == "原始描述"
    assert updated["response_style"] == "balanced"


# ==========================================
# 4. 支持清空可选配置
# ==========================================

def test_clear_agent_settings(client):
    created = client.post(
        "/agents",
        json={
            "name": "Test",
            "custom_instructions": "保持简洁",
            "enabled_tools": ["list_tasks"],
        },
    ).json()

    response = client.patch(
        f"/agents/{created['id']}",
        json={
            "custom_instructions": "",
            "enabled_tools": [],
        },
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["custom_instructions"] == ""
    assert updated["enabled_tools"] == []


# ==========================================
# 5. 参数校验
# ==========================================

@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   "},
        {
            "name": "Test",
            "personality": "unknown",
        },
        {
            "name": "Test",
            "enabled_tools": ["delete_everything"],
        },
        {
            "name": "Test",
            "unknown_field": "unexpected",
        },
    ],
)
def test_invalid_create_agent(client, payload):
    response = client.post(
        "/agents",
        json=payload,
    )

    assert response.status_code == 422


# ==========================================
# 6. 不存在的 Agent 返回 404
# ==========================================

def test_agent_not_found(client):
    response = client.get(
        "/agents/not-exist"
    )

    assert response.status_code == 404

    response = client.patch(
        "/agents/not-exist",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


# ==========================================
# 7. 非法 PATCH 请求
# ==========================================

def test_invalid_patch(client):
    created = client.post(
        "/agents",
        json={"name": "Test"},
    ).json()

    response = client.patch(
        f"/agents/{created['id']}",
        json={"response_style": "unknown"},
    )

    assert response.status_code == 422

    empty_response = client.patch(
        f"/agents/{created['id']}",
        json={},
    )

    assert empty_response.status_code == 422


# ==========================================
# 8. 配置在不同客户端间持久化
# ==========================================

def test_agent_persistence(client):
    created = client.post(
        "/agents",
        json={"name": "Persistent Agent"},
    ).json()

    agent_id = created["id"]

    # 使用新的 HTTP 测试客户端访问同一数据库
    with TestClient(app) as another_client:
        response = another_client.get(
            f"/agents/{agent_id}"
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Persistent Agent"


# ==========================================
# 9. 原有接口仍然注册
# ==========================================

def test_existing_routes_preserved(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/chat" in paths
    assert "/tasks" in paths
    assert "/agents" in paths
    assert "/agents/{agent_id}" in paths


# ==========================================
# 10. 数据库异常不应暴露底层信息
# ==========================================

def test_database_error_returns_500(
    client,
    monkeypatch,
):
    def broken_create_agent(**kwargs):
        raise sqlite3.OperationalError(
            "sensitive database details"
        )

    monkeypatch.setattr(
        agent_routes.service,
        "create_agent",
        broken_create_agent,
    )

    response = client.post(
        "/agents",
        json={"name": "Test"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Agent 创建失败"
    )
    assert "sensitive database details" not in (
        response.text
    )
