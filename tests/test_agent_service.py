
import sqlite3

import pytest

import agent_service
import database
import task_service


@pytest.fixture
def test_db(tmp_path):
    return tmp_path / "test_agents.db"


# ==========================================
# 1. 默认 Agent 初始化
# ==========================================

def test_default_agent_created_once(test_db):
    database.init_database(test_db)
    database.init_database(test_db)

    agents = agent_service.list_agents(
        db_path=test_db
    )

    assert len(agents) == 1

    default = agent_service.get_agent(
        database.DEFAULT_AGENT_ID,
        db_path=test_db,
    )

    assert default["name"] == "My Agent"
    assert default["personality"] == "professional"
    assert default["response_style"] == "balanced"
    assert isinstance(default["enabled_tools"], list)


# ==========================================
# 2. 原有任务表不受影响
# ==========================================

def test_existing_tasks_preserved(test_db):
    database.init_database(test_db)

    with database.get_connection(test_db) as conn:
        conn.execute(
            """
            INSERT INTO tasks (title, status)
            VALUES (?, ?)
            """,
            ("学习 FastAPI", "待完成"),
        )

    database.init_database(test_db)

    with database.get_connection(test_db) as conn:
        task = conn.execute(
            "SELECT title, status FROM tasks"
        ).fetchone()

        agents_table = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table'
              AND name = 'agents'
            """
        ).fetchone()

    assert task["title"] == "学习 FastAPI"
    assert task["status"] == "待完成"
    assert agents_table is not None


# ==========================================
# 3. 创建 Agent 并持久化
# ==========================================

def test_create_agent_persistence(test_db):
    created = agent_service.create_agent(
        "Friday",
        description="编程学习助手",
        personality="professional",
        response_style="detailed",
        custom_instructions="请使用中文解释代码。",
        enabled_tools=[
            "get_task_summary",
            "list_tasks",
        ],
        db_path=test_db,
    )

    assert created["id"]
    assert created["name"] == "Friday"
    assert created["personality"] == "professional"

    loaded = agent_service.get_agent(
        created["id"],
        db_path=test_db,
    )

    assert loaded == created
    assert loaded["response_style"] == "detailed"
    assert loaded["enabled_tools"] == [
        "get_task_summary",
        "list_tasks",
    ]

    agents = agent_service.list_agents(
        db_path=test_db
    )

    assert len(agents) == 2


# ==========================================
# 4. 更新配置
# ==========================================

def test_update_agent(test_db):
    agent = agent_service.create_agent(
        "Original",
        db_path=test_db,
    )

    updated = agent_service.update_agent(
        agent["id"],
        name="Nova",
        personality="creative",
        response_style="concise",
        custom_instructions="优先给出示例。",
        enabled_tools=["list_tasks"],
        db_path=test_db,
    )

    assert updated["name"] == "Nova"
    assert updated["personality"] == "creative"
    assert updated["response_style"] == "concise"
    assert updated["enabled_tools"] == ["list_tasks"]

    loaded = agent_service.get_agent(
        agent["id"],
        db_path=test_db,
    )

    assert loaded["name"] == "Nova"
    assert loaded["custom_instructions"] == "优先给出示例。"


# ==========================================
# 5. 清空可选配置
# ==========================================

def test_clear_optional_settings(test_db):
    agent = agent_service.create_agent(
        "Test",
        description="测试助手",
        custom_instructions="保持简洁",
        db_path=test_db,
    )

    updated = agent_service.update_agent(
        agent["id"],
        description="",
        custom_instructions="",
        enabled_tools=[],
        db_path=test_db,
    )

    assert updated["description"] == ""
    assert updated["custom_instructions"] == ""
    assert updated["enabled_tools"] == []


# ==========================================
# 6. 多个 Agent 配置相互独立
# ==========================================

def test_agents_are_independent(test_db):
    first = agent_service.create_agent(
        "CodeMate",
        personality="professional",
        db_path=test_db,
    )

    second = agent_service.create_agent(
        "Study",
        personality="companion",
        db_path=test_db,
    )

    agent_service.update_agent(
        first["id"],
        personality="efficient",
        db_path=test_db,
    )

    first_loaded = agent_service.get_agent(
        first["id"],
        db_path=test_db,
    )

    second_loaded = agent_service.get_agent(
        second["id"],
        db_path=test_db,
    )

    assert first_loaded["personality"] == "efficient"
    assert second_loaded["personality"] == "companion"


# ==========================================
# 7. 非法配置必须被拒绝
# ==========================================

def test_invalid_agent_config(test_db):
    with pytest.raises(ValueError):
        agent_service.create_agent(
            "   ",
            db_path=test_db,
        )

    with pytest.raises(ValueError):
        agent_service.create_agent(
            "Test",
            personality="unknown",
            db_path=test_db,
        )

    with pytest.raises(ValueError):
        agent_service.create_agent(
            "Test",
            response_style="unknown",
            db_path=test_db,
        )

    with pytest.raises(ValueError):
        agent_service.create_agent(
            "Test",
            enabled_tools=["delete_everything"],
            db_path=test_db,
        )

    with pytest.raises(ValueError):
        agent_service.create_agent(
            "Test",
            enabled_tools="list_tasks",
            db_path=test_db,
        )


# ==========================================
# 8. 不存在的 Agent
# ==========================================

def test_unknown_agent(test_db):
    with pytest.raises(LookupError):
        agent_service.get_agent(
            "not-exist",
            db_path=test_db,
        )

    with pytest.raises(LookupError):
        agent_service.update_agent(
            "not-exist",
            name="New Name",
            db_path=test_db,
        )


# ==========================================
# 9. 原有 Task Service 保持兼容
# ==========================================

def test_task_service_compatibility(
    test_db,
    monkeypatch,
):
    monkeypatch.setattr(
        task_service,
        "DB_FILE",
        test_db,
    )

    created = task_service.create_task(
        "完成 Agent 配置开发"
    )

    tasks = task_service.list_tasks()

    assert len(tasks) == 1
    assert tasks[0]["id"] == created["id"]

    summary = task_service.get_task_summary()

    assert summary["total"] == 1
    assert summary["pending"] == 1

    # 同一数据库中默认 Agent 仍然可用
    default = agent_service.get_agent(
        database.DEFAULT_AGENT_ID,
        db_path=test_db,
    )

    assert default["name"] == "My Agent"
