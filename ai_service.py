
import os
import json
import logging

from dotenv import load_dotenv
from openai import OpenAI

import agent_service

from prompt_builder import build_system_prompt
from tool_registry import build_task_registry


load_dotenv()

logger = logging.getLogger(__name__)

api_key = os.getenv("DEEPSEEK_API_KEY")

client = (
    OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=30.0,
    )
    if api_key
    else None
)

MAX_TOOL_ROUNDS = 3
MAX_TOOL_EXECUTIONS = 8

# 保留旧变量名称，降低兼容性风险
SYSTEM_PROMPT = build_system_prompt()
TASK_TOOLS = build_task_registry().schemas()


def resolve_agent_config(agent_config=None):
    """
    显式传入配置：使用指定 Agent。

    不传配置：读取 SQLite 中的默认 Agent。
    这样修改默认 Agent 后，旧版聊天接口
    也能自动使用修改后的配置。
    """

    if agent_config is not None:
        return agent_config

    return agent_service.get_agent(
        agent_service.DEFAULT_AGENT_ID
    )


def chat_with_ai(
    history: list[dict[str, str]],
    agent_config=None,
) -> str:

    if client is None:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    config = resolve_agent_config(agent_config)

    system_prompt = build_system_prompt(config)

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        *history,
    ]

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
    )

    return (
        response.choices[0].message.content
        or "模型未返回内容。"
    )


def chat_with_tools(
    history: list[dict],
    task_summary_func,
    long_term_memory: str = "",
    agent_config=None,
) -> str:
    """
    带工具调用的 Agent 聊天。

    保留原来的前三个参数。
    新增 agent_config 作为可选参数。
    """

    if client is None:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    # 1. 加载 Agent 配置
    config = resolve_agent_config(agent_config)

    # 2. 构建动态 Prompt
    system_prompt = build_system_prompt(
        agent_config=config,
        long_term_memory=long_term_memory,
    )

    # 3. 初始化 Tool Registry
    registry = build_task_registry(
        task_summary_func=task_summary_func
    )

    # Day 3 保持原有工具行为。
    # Day 4 再接入 agent_config["enabled_tools"]。
    allowed_tools = {
        "get_task_summary",
        "list_tasks",
        "create_task",
        "update_task_status",
    }

    tool_schemas = registry.schemas(
        allowed_names=allowed_tools
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        *history,
    ]

    total_executions = 0

    # 4. 模型与工具的循环调用
    for _ in range(MAX_TOOL_ROUNDS):

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # 不需要工具：直接回复
        if not message.tool_calls:
            return (
                message.content
                or "模型未返回内容。"
            )

        # 记录模型请求的工具调用
        messages.append(
            message.model_dump(exclude_none=True)
        )

        for call in message.tool_calls:

            total_executions += 1

            name = call.function.name
            arguments = call.function.arguments

            if total_executions > MAX_TOOL_EXECUTIONS:
                result = {
                    "ok": False,
                    "error": "工具调用次数已达上限",
                }
            else:
                result = registry.execute(
                    name=name,
                    raw_arguments=arguments,
                    allowed_names=allowed_tools,
                )

            logger.info(
                "Agent tool call: %s, success=%s",
                name,
                result.get("ok"),
            )

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                ),
            })

    return (
        "工具调用轮数达到上限。"
        "部分操作可能已经执行，"
        "请先查询任务状态，避免重复提交。"
    )
