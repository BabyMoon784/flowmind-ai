
import uuid

import pytest
from fastapi.testclient import TestClient

import agent_service
import database
import memory_store
import task_service

from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """使用独立 SQLite 数据库测试 API。"""

    test_db = tmp_path / "test_memory_api.db"

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

    # 兼容 memory_store 中可能存在的 DB_FILE 常量
    if hasattr(memory_store, "DB_FILE"):
        monkeypatch.setattr(
            memory_store,
            "DB_FILE",
            test_db,
        )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def agent_id(client):
    """创建测试专用 Agent。"""

    agent = agent_service.create_agent(
        "Memory API Test Agent",
        enabled_tools=[],
    )

    return agent["id"]


def post_memory(
    client,
    agent_id,
    memory_key="user_name",
    content="BabyMoon",
    memory_type="profile",
):
    return client.post(
        "/memories",
        json={
            "agent_id": agent_id,
            "memory_key": memory_key,
            "content": content,
            "memory_type": memory_type,
            "source": "manual",
            "importance": 3,
        },
    )


# ==========================================
# 1. 创建记忆
# ==========================================

def test_create_memory(client, agent_id):

    response = post_memory(
        client,
        agent_id,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["agent_id"] == agent_id
    assert data["memory_key"] == "user_name"
    assert data["content"] == "BabyMoon"
    assert data["memory_type"] == "profile"
    assert data["importance"] == 3

    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


# ==========================================
# 2. 重复记忆返回 409
# ==========================================

def test_duplicate_memory(client, agent_id):

    first = post_memory(
        client,
        agent_id,
    )

    second = post_memory(
        client,
        agent_id,
    )

    assert first.status_code == 201
    assert second.status_code == 409


# ==========================================
# 3. 获取记忆列表
# ==========================================

def test_list_memories(client, agent_id):

    post_memory(
        client,
        agent_id,
        "user_name",
        "BabyMoon",
        "profile",
    )

    post_memory(
        client,
        agent_id,
        "language",
        "中文",
        "preference",
    )

    response = client.get(
        "/memories",
        params={
            "agent_id": agent_id,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 2
    assert len(data["memories"]) == 2


# ==========================================
# 4. 按类型筛选记忆
# ==========================================

def test_filter_memories(client, agent_id):

    post_memory(
        client,
        agent_id,
        "user_name",
        "BabyMoon",
        "profile",
    )

    post_memory(
        client,
        agent_id,
        "language",
        "中文",
        "preference",
    )

    response = client.get(
        "/memories",
        params={
            "agent_id": agent_id,
            "memory_type": "preference",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1

    assert (
        data["memories"][0]["memory_type"]
        == "preference"
    )


# ==========================================
# 5. 获取单条记忆
# ==========================================

def test_get_memory(client, agent_id):

    created = post_memory(
        client,
        agent_id,
    ).json()

    response = client.get(
        f"/memories/{created['id']}",
        params={
            "agent_id": agent_id,
        },
    )

    assert response.status_code == 200

    assert response.json()["id"] == created["id"]


# ==========================================
# 6. 更新记忆
# ==========================================

def test_update_memory(client, agent_id):

    created = post_memory(
        client,
        agent_id,
    ).json()

    response = client.patch(
        f"/memories/{created['id']}",
        params={
            "agent_id": agent_id,
        },
        json={
            "content": "正在学习 AI Agent 开发",
            "importance": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["content"] == "正在学习 AI Agent 开发"
    assert data["importance"] == 5


# ==========================================
# 7. 更新时发生名称冲突
# ==========================================

def test_update_duplicate_memory_key(client, agent_id):

    first = post_memory(
        client,
        agent_id,
        "first",
        "内容一",
    ).json()

    post_memory(
        client,
        agent_id,
        "second",
        "内容二",
    )

    response = client.patch(
        f"/memories/{first['id']}",
        params={
            "agent_id": agent_id,
        },
        json={
            "memory_key": "second",
        },
    )

    assert response.status_code == 409


# ==========================================
# 8. 删除记忆
# ==========================================

def test_delete_memory(client, agent_id):

    created = post_memory(
        client,
        agent_id,
    ).json()

    response = client.delete(
        f"/memories/{created['id']}",
        params={
            "agent_id": agent_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["deleted"] is True

    # 再次读取应该不存在
    result = client.get(
        f"/memories/{created['id']}",
        params={
            "agent_id": agent_id,
        },
    )

    assert result.status_code == 404


# ==========================================
# 9. 不存在的 Agent
# ==========================================

def test_agent_not_found(client):

    fake_agent_id = str(uuid.uuid4())

    response = client.get(
        "/memories",
        params={
            "agent_id": fake_agent_id,
        },
    )

    assert response.status_code == 404


# ==========================================
# 10. Agent 之间的记忆隔离
# ==========================================

def test_memory_isolation(client):

    agent_a = agent_service.create_agent(
        "Agent A",
        enabled_tools=[],
    )

    agent_b = agent_service.create_agent(
        "Agent B",
        enabled_tools=[],
    )

    memory = post_memory(
        client,
        agent_a["id"],
    ).json()

    memory_id = memory["id"]

    # Agent B 不能读取 Agent A 的记忆
    response = client.get(
        f"/memories/{memory_id}",
        params={
            "agent_id": agent_b["id"],
        },
    )

    assert response.status_code == 404

    # Agent B 不能修改 Agent A 的记忆
    response = client.patch(
        f"/memories/{memory_id}",
        params={
            "agent_id": agent_b["id"],
        },
        json={
            "content": "非法修改",
        },
    )

    assert response.status_code == 404

    # Agent B 不能删除 Agent A 的记忆
    response = client.delete(
        f"/memories/{memory_id}",
        params={
            "agent_id": agent_b["id"],
        },
    )

    assert response.status_code == 404


# ==========================================
# 11. 参数校验
# ==========================================

def test_invalid_memory_data(client, agent_id):

    # 空白名称
    response = post_memory(
        client,
        agent_id,
        "   ",
        "测试内容",
    )

    assert response.status_code == 422

    # importance 超出范围
    response = client.post(
        "/memories",
        json={
            "agent_id": agent_id,
            "memory_key": "test",
            "content": "测试内容",
            "importance": 6,
        },
    )

    assert response.status_code == 422


# ==========================================
# 12. 空更新请求
# ==========================================

def test_empty_memory_update(client, agent_id):

    created = post_memory(
        client,
        agent_id,
    ).json()

    response = client.patch(
        f"/memories/{created['id']}",
        params={
            "agent_id": agent_id,
        },
        json={},
    )

    assert response.status_code == 422
