
import pytest

import agent_service
import database
import memory_store


@pytest.fixture
def db_path(tmp_path):
    """每个测试使用独立 SQLite 数据库。"""

    path = tmp_path / "test_flowmind.db"

    database.init_database(path)

    return path


@pytest.fixture
def agent_pair(db_path):
    """准备两个相互独立的 Agent。"""

    agent_a = database.DEFAULT_AGENT_ID

    agent_b = agent_service.create_agent(
        "Test Agent B",
        db_path=db_path,
    )["id"]

    return agent_a, agent_b


# ==========================================
# 测试 1：创建并持久化记忆
# ==========================================

def test_create_and_get_memory(db_path):
    agent_id = database.DEFAULT_AGENT_ID

    memory = memory_store.create_memory(
        agent_id,
        "学习方向",
        "正在学习 Python 和 C++",
        memory_type="preference",
        importance=5,
        db_path=db_path,
    )

    assert memory["agent_id"] == agent_id
    assert memory["memory_key"] == "学习方向"
    assert memory["content"] == "正在学习 Python 和 C++"
    assert memory["memory_type"] == "preference"
    assert memory["importance"] == 5

    loaded = memory_store.get_memory(
        memory["id"],
        agent_id,
        db_path=db_path,
    )

    assert loaded == memory


# ==========================================
# 测试 2：同一 Agent 不能创建同名记忆
# ==========================================

def test_duplicate_memory_key(db_path):
    agent_id = database.DEFAULT_AGENT_ID

    memory_store.create_memory(
        agent_id,
        "回答语言",
        "中文",
        db_path=db_path,
    )

    with pytest.raises(ValueError):
        memory_store.create_memory(
            agent_id,
            "回答语言",
            "英文",
            db_path=db_path,
        )


# ==========================================
# 测试 3：不同 Agent 可以有相同名称
# ==========================================

def test_same_key_allowed_for_different_agents(
    db_path,
    agent_pair,
):
    agent_a, agent_b = agent_pair

    first = memory_store.create_memory(
        agent_a,
        "回答风格",
        "详细",
        db_path=db_path,
    )

    second = memory_store.create_memory(
        agent_b,
        "回答风格",
        "简洁",
        db_path=db_path,
    )

    assert first["memory_key"] == second["memory_key"]
    assert first["agent_id"] != second["agent_id"]


# ==========================================
# 测试 4：Agent 记忆隔离
# ==========================================

def test_list_memories_isolated(
    db_path,
    agent_pair,
):
    agent_a, agent_b = agent_pair

    memory_store.create_memory(
        agent_a,
        "项目",
        "FlowMind AI",
        memory_type="project",
        db_path=db_path,
    )

    memory_store.create_memory(
        agent_b,
        "偏好",
        "简洁回答",
        memory_type="preference",
        db_path=db_path,
    )

    memories_a = memory_store.list_memories(
        agent_a,
        db_path=db_path,
    )

    memories_b = memory_store.list_memories(
        agent_b,
        db_path=db_path,
    )

    assert len(memories_a) == 1
    assert len(memories_b) == 1

    assert memories_a[0]["content"] == "FlowMind AI"
    assert memories_b[0]["content"] == "简洁回答"


# ==========================================
# 测试 5：记忆类型筛选和分页
# ==========================================

def test_memory_filter_and_pagination(db_path):
    agent_id = database.DEFAULT_AGENT_ID

    memory_store.create_memory(
        agent_id,
        "项目一",
        "FlowMind",
        memory_type="project",
        db_path=db_path,
    )

    memory_store.create_memory(
        agent_id,
        "项目二",
        "其他项目",
        memory_type="project",
        db_path=db_path,
    )

    memory_store.create_memory(
        agent_id,
        "语言偏好",
        "中文",
        memory_type="preference",
        db_path=db_path,
    )

    projects = memory_store.list_memories(
        agent_id,
        memory_type="project",
        limit=1,
        offset=0,
        db_path=db_path,
    )

    assert len(projects) == 1
    assert projects[0]["memory_type"] == "project"

    next_page = memory_store.list_memories(
        agent_id,
        memory_type="project",
        limit=1,
        offset=1,
        db_path=db_path,
    )

    assert len(next_page) == 1
    assert next_page[0]["id"] != projects[0]["id"]


# ==========================================
# 测试 6：更新记忆
# ==========================================

def test_update_memory(db_path):
    agent_id = database.DEFAULT_AGENT_ID

    memory = memory_store.create_memory(
        agent_id,
        "学习方向",
        "Python",
        db_path=db_path,
    )

    updated = memory_store.update_memory(
        memory["id"],
        agent_id,
        content="Python 和 C++",
        importance=5,
        db_path=db_path,
    )

    assert updated["content"] == "Python 和 C++"
    assert updated["importance"] == 5
    assert updated["memory_key"] == "学习方向"


# ==========================================
# 测试 7：不能跨 Agent 读取或修改记忆
# ==========================================

def test_memory_cannot_be_accessed_by_other_agent(
    db_path,
    agent_pair,
):
    agent_a, agent_b = agent_pair

    memory = memory_store.create_memory(
        agent_a,
        "私人记忆",
        "这是 Agent A 的记忆",
        db_path=db_path,
    )

    result = memory_store.get_memory(
        memory["id"],
        agent_b,
        db_path=db_path,
    )

    assert result is None

    with pytest.raises(LookupError):
        memory_store.update_memory(
            memory["id"],
            agent_b,
            content="尝试修改",
            db_path=db_path,
        )

    assert memory_store.delete_memory(
        memory["id"],
        agent_b,
        db_path=db_path,
    ) is False

    original = memory_store.get_memory(
        memory["id"],
        agent_a,
        db_path=db_path,
    )

    assert original["content"] == "这是 Agent A 的记忆"


# ==========================================
# 测试 8：删除记忆
# ==========================================

def test_delete_memory(db_path):
    agent_id = database.DEFAULT_AGENT_ID

    memory = memory_store.create_memory(
        agent_id,
        "临时记忆",
        "准备删除",
        db_path=db_path,
    )

    result = memory_store.delete_memory(
        memory["id"],
        agent_id,
        db_path=db_path,
    )

    assert result is True

    assert memory_store.get_memory(
        memory["id"],
        agent_id,
        db_path=db_path,
    ) is None

    assert memory_store.delete_memory(
        memory["id"],
        agent_id,
        db_path=db_path,
    ) is False


# ==========================================
# 测试 9：参数校验
# ==========================================

@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "memory_key": " ",
            "content": "有效内容",
        },
        {
            "memory_key": "有效名称",
            "content": " ",
        },
        {
            "memory_key": "有效名称",
            "content": "有效内容",
            "memory_type": "unknown",
        },
        {
            "memory_key": "有效名称",
            "content": "有效内容",
            "importance": 6,
        },
    ],
)
def test_invalid_memory_data(db_path, kwargs):
    agent_id = database.DEFAULT_AGENT_ID

    with pytest.raises(ValueError):
        memory_store.create_memory(
            agent_id,
            db_path=db_path,
            **kwargs,
        )


# ==========================================
# 测试 10：不存在的 Agent 不能保存记忆
# ==========================================

def test_unknown_agent_rejected(db_path):
    with pytest.raises(LookupError):
        memory_store.create_memory(
            "unknown-agent-id",
            "测试",
            "不应该保存",
            db_path=db_path,
        )
