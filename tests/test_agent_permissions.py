
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import ai_service
import agent_service
import task_service


def make_config(tools):
    return {
        "name": "Permission Test Agent",
        "description": "权限测试助手",
        "personality": "professional",
        "response_style": "balanced",
        "custom_instructions": "",
        "enabled_tools": tools,
    }


def make_fake_client(reply="测试成功"):
    message = SimpleNamespace(
        tool_calls=[],
        content=reply,
    )

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=message)
        ],
    )

    fake = MagicMock()

    fake.chat.completions.create.return_value = (
        response
    )

    return fake


def run_chat(config):
    return ai_service.chat_with_tools(
        history=[
            {
                "role": "user",
                "content": "你好",
            }
        ],
        task_summary_func=lambda: {},
        agent_config=config,
    )


# ==========================================
# 1. 只读 Agent 只暴露两个工具
# ==========================================

def test_readonly_agent_tools(monkeypatch):
    fake = make_fake_client()

    monkeypatch.setattr(
        ai_service,
        "client",
        fake,
    )

    answer = run_chat(
        make_config([
            "get_task_summary",
            "list_tasks",
        ])
    )

    assert answer == "测试成功"

    kwargs = (
        fake.chat.completions.create.call_args.kwargs
    )

    exposed = {
        item["function"]["name"]
        for item in kwargs["tools"]
    }

    assert exposed == {
        "get_task_summary",
        "list_tasks",
    }

    assert "create_task" not in exposed
    assert "update_task_status" not in exposed

    prompt = kwargs["messages"][0]["content"]

    assert "未授权的任务操作" in prompt
    assert "创建任务" in prompt


# ==========================================
# 2. 空权限 Agent 仍可以聊天
# ==========================================

def test_no_tools_agent(monkeypatch):
    fake = make_fake_client("你好，我可以聊天。")

    monkeypatch.setattr(
        ai_service,
        "client",
        fake,
    )

    answer = run_chat(
        make_config([])
    )

    assert answer == "你好，我可以聊天。"

    kwargs = (
        fake.chat.completions.create.call_args.kwargs
    )

    # 不能传 tools=[] 或 tool_choice
    assert "tools" not in kwargs
    assert "tool_choice" not in kwargs

    prompt = kwargs["messages"][0]["content"]

    assert "未授权的任务操作" in prompt


# ==========================================
# 3. 全权限 Agent 可以使用四个工具
# ==========================================

def test_full_permission_agent(monkeypatch):
    fake = make_fake_client()

    monkeypatch.setattr(
        ai_service,
        "client",
        fake,
    )

    run_chat(make_config([
        "get_task_summary",
        "list_tasks",
        "create_task",
        "update_task_status",
    ]))

    kwargs = (
        fake.chat.completions.create.call_args.kwargs
    )

    exposed = {
        item["function"]["name"]
        for item in kwargs["tools"]
    }

    assert exposed == {
        "get_task_summary",
        "list_tasks",
        "create_task",
        "update_task_status",
    }


# ==========================================
# 4. 非法权限配置必须拒绝
# ==========================================

@pytest.mark.parametrize(
    "tools",
    [
        ["delete_everything"],
        "list_tasks",
        None,
        [123],
    ],
)
def test_invalid_permissions(
    tools,
    monkeypatch,
):
    fake = make_fake_client()

    monkeypatch.setattr(
        ai_service,
        "client",
        fake,
    )

    with pytest.raises(ValueError):
        run_chat(make_config(tools))

    # 配置非法时，不能调用模型
    fake.chat.completions.create.assert_not_called()


# ==========================================
# 5. 模型越权调用时，必须阻止执行
# ==========================================

def test_forbidden_tool_is_not_executed(
    monkeypatch,
):
    called = []

    def forbidden_create(title):
        called.append(title)

        raise AssertionError(
            "未授权工具不应该被执行"
        )

    monkeypatch.setattr(
        task_service,
        "create_task",
        forbidden_create,
    )

    tool_call = SimpleNamespace(
        id="call_forbidden_001",
        function=SimpleNamespace(
            name="create_task",
            arguments='{"title": "不应该创建的任务"}',
        ),
    )

    # 模拟模型错误地请求 create_task
    first = MagicMock()

    first.choices[0].message.tool_calls = [
        tool_call
    ]

    first.choices[0].message.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_forbidden_001",
                "type": "function",
                "function": {
                    "name": "create_task",
                    "arguments": (
                        '{"title": "不应该创建的任务"}'
                    ),
                },
            }
        ],
    }

    # 模拟模型收到工具拒绝结果后的回复
    second = MagicMock()

    second.choices[0].message.tool_calls = []
    second.choices[0].message.content = (
        "当前 Agent 无权创建任务。"
    )

    fake = MagicMock()

    fake.chat.completions.create.side_effect = [
        first,
        second,
    ]

    monkeypatch.setattr(
        ai_service,
        "client",
        fake,
    )

    answer = run_chat(
        make_config([
            "get_task_summary",
            "list_tasks",
        ])
    )

    assert "无权" in answer

    # 最重要的断言：
    # 真正的创建任务函数一次也没有执行。
    assert called == []

    second_request = (
        fake.chat.completions.create
        .call_args_list[1].kwargs
    )

    tool_message = (
        second_request["messages"][-1]
    )

    result = json.loads(
        tool_message["content"]
    )

    assert result["ok"] is False
    assert "无权" in result["error"]


# ==========================================
# 6. 空权限时意外返回工具调用也不执行
# ==========================================

def test_no_permissions_blocks_unexpected_call(
    monkeypatch,
):
    fake = make_fake_client()

    fake.chat.completions.create.return_value = (
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="unexpected"
                            )
                        ],
                    )
                )
            ]
        )
    )

    monkeypatch.setattr(
        ai_service,
        "client",
        fake,
    )

    answer = run_chat(
        make_config([])
    )

    assert "没有工具调用权限" in answer
    assert (
        fake.chat.completions.create.call_count
        == 1
    )


# ==========================================
# 7. 数据库修改后权限应随配置变化
# ==========================================

def test_database_permission_update(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "test_permissions.db"

    agent = agent_service.create_agent(
        "ReadOnly Agent",
        enabled_tools=["list_tasks"],
        db_path=db_path,
    )

    fake = make_fake_client()

    monkeypatch.setattr(
        ai_service,
        "client",
        fake,
    )

    run_chat(agent)

    first_kwargs = (
        fake.chat.completions.create.call_args.kwargs
    )

    first_names = {
        item["function"]["name"]
        for item in first_kwargs["tools"]
    }

    assert first_names == {"list_tasks"}

    # 修改持久化配置
    updated = agent_service.update_agent(
        agent["id"],
        enabled_tools=[
            "list_tasks",
            "create_task",
        ],
        db_path=db_path,
    )

    fake.reset_mock()

    run_chat(updated)

    second_kwargs = (
        fake.chat.completions.create.call_args.kwargs
    )

    second_names = {
        item["function"]["name"]
        for item in second_kwargs["tools"]
    }

    assert second_names == {
        "list_tasks",
        "create_task",
    }
