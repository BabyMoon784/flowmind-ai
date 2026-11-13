
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import ai_service
import task_service
from tool_registry import build_task_registry


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        task_service,
        "DB_FILE",
        tmp_path / "test_agent_tools.db",
    )

    return build_task_registry()


def test_tool_schemas(registry):
    """工具描述包含全部四个任务工具。"""

    schemas = registry.schemas()

    names = {
        item["function"]["name"]
        for item in schemas
    }

    assert names == {
        "get_task_summary",
        "list_tasks",
        "create_task",
        "update_task_status",
    }


def test_summary_tool():
    """验证任务统计函数可以注入。"""

    fake_summary = lambda: {
        "total": 3,
        "completed": 1,
        "pending": 2,
    }

    registry = build_task_registry(fake_summary)

    result = registry.execute(
        "get_task_summary",
        "{}",
    )

    assert result["ok"] is True
    assert result["data"]["pending"] == 2


def test_task_lifecycle(registry):
    """通过工具完成创建、查询、更新任务。"""

    created = registry.execute(
        "create_task",
        json.dumps(
            {"title": "学习 FastAPI"},
            ensure_ascii=False,
        ),
    )

    assert created["ok"] is True

    task_id = created["data"]["id"]

    listed = registry.execute(
        "list_tasks",
        "{}",
    )

    assert listed["ok"] is True
    assert len(listed["data"]) == 1
    assert listed["data"][0]["id"] == task_id

    updated = registry.execute(
        "update_task_status",
        json.dumps({
            "task_id": task_id,
            "status": "已完成",
        }, ensure_ascii=False),
    )

    assert updated["ok"] is True
    assert updated["data"]["status"] == "已完成"


def test_invalid_json(registry):
    """拒绝不合法的 JSON 参数。"""

    result = registry.execute(
        "create_task",
        "{invalid-json}",
    )

    assert result["ok"] is False


def test_invalid_arguments(registry):
    """拒绝空任务名和多余参数。"""

    blank = registry.execute(
        "create_task",
        '{"title": "   "}',
    )

    assert blank["ok"] is False

    extra = registry.execute(
        "create_task",
        '{"title": "学习", "unexpected": 1}',
    )

    assert extra["ok"] is False


def test_unknown_or_forbidden_tool(registry):
    """不执行未注册或未授权的工具。"""

    unknown = registry.execute(
        "delete_everything",
        "{}",
    )

    assert unknown["ok"] is False

    forbidden = registry.execute(
        "create_task",
        '{"title": "测试"}',
        allowed_names={"get_task_summary"},
    )

    assert forbidden["ok"] is False

    tasks = registry.execute(
        "list_tasks",
        "{}",
    )

    assert tasks["data"] == []


def test_missing_task(registry):
    """修改不存在的任务应该返回错误。"""

    result = registry.execute(
        "update_task_status",
        '{"task_id": 99999, "status": "已完成"}',
    )

    assert result["ok"] is False


def test_agent_calls_real_tool(
    tmp_path,
    monkeypatch,
):
    """模拟大模型请求工具，验证完整调用链。"""

    monkeypatch.setattr(
        task_service,
        "DB_FILE",
        tmp_path / "test_llm_tool.db",
    )

    tool_call = SimpleNamespace(
        id="call_test_001",
        function=SimpleNamespace(
            name="create_task",
            arguments='{"title": "学习 Agent"}',
        ),
    )

    # 第一次模型响应：请求调用工具
    first = MagicMock()

    first.choices[0].message.tool_calls = [
        tool_call
    ]

    first.choices[0].message.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_test_001",
                "type": "function",
                "function": {
                    "name": "create_task",
                    "arguments": (
                        '{"title": "学习 Agent"}'
                    ),
                },
            }
        ],
    }

    # 第二次模型响应：给用户最终回答
    second = MagicMock()

    second.choices[0].message.tool_calls = []
    second.choices[0].message.content = "任务创建成功"

    fake_client = MagicMock()

    fake_client.chat.completions.create.side_effect = [
        first,
        second,
    ]

    monkeypatch.setattr(
        ai_service,
        "client",
        fake_client,
    )

    answer = ai_service.chat_with_tools(
        history=[
            {
                "role": "user",
                "content": "创建一个学习 Agent 的任务",
            }
        ],
        task_summary_func=task_service.get_task_summary,
    )

    assert answer == "任务创建成功"

    # 确认模型确实调用了两次
    assert (
        fake_client.chat.completions.create.call_count
        == 2
    )

    # 确认第二次请求包含真实工具结果
    second_request = (
        fake_client.chat.completions.create
        .call_args_list[1]
        .kwargs
    )

    tool_message = second_request["messages"][-1]

    assert tool_message["role"] == "tool"

    tool_result = json.loads(
        tool_message["content"]
    )

    assert tool_result["ok"] is True

    # 最关键的验证：任务真的写入了 SQLite
    tasks = task_service.list_tasks()

    assert len(tasks) == 1
    assert tasks[0]["title"] == "学习 Agent"
