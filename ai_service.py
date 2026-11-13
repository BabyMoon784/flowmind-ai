
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

# 保留旧变量，兼容之前的代码
SYSTEM_PROMPT = build_system_prompt()
TASK_TOOLS = build_task_registry().schemas()


# ==========================================
# 1. 读取 Agent 配置
# ==========================================

def resolve_agent_config(agent_config=None):
    """
    显式传入配置：使用该配置。
    未传入配置：加载默认 Agent。
    """

    if agent_config is not None:
        return agent_config

    return agent_service.get_agent(
        agent_service.DEFAULT_AGENT_ID
    )


# ==========================================
# 2. 解析工具权限
# ==========================================

def resolve_allowed_tools(config, registry):
    """
    从 Agent 配置读取 enabled_tools。

    检查：
    - 必须是 list
    - 元素必须是字符串
    - 工具必须存在于注册表

    空列表表示不允许调用任何工具。
    """

    registered_tools = {
        item["function"]["name"]
        for item in registry.schemas()
    }

    # 兼容早期测试中未提供 enabled_tools
    # 的临时配置字典。
    # 正式数据库中的 Agent 均有该字段。
    raw_tools = config.get(
        "enabled_tools",
        sorted(registered_tools),
    )

    if not isinstance(raw_tools, list):
        raise ValueError(
            "Agent 的 enabled_tools 必须是列表"
        )

    if not all(
        isinstance(name, str)
        for name in raw_tools
    ):
        raise ValueError(
            "enabled_tools 中的工具名称必须是字符串"
        )

    unknown_tools = (
        set(raw_tools) - registered_tools
    )

    if unknown_tools:
        raise ValueError(
            "Agent 配置了未知工具："
            + ", ".join(sorted(unknown_tools))
        )

    return set(raw_tools)


# ==========================================
# 3. 为模型生成权限说明
# ==========================================

def build_permission_context(
    allowed_tools,
    registered_tools,
):
    """
    告知模型当前允许的操作。

    注意：这只是行为提示。
    真正的权限检查发生在 registry.execute。
    """

    tool_labels = {
        "get_task_summary": "统计任务数量",
        "list_tasks": "查询任务列表",
        "create_task": "创建任务",
        "update_task_status": "修改任务状态",
    }

    def describe(names):
        if not names:
            return "无"

        return "、".join(
            tool_labels.get(name, name)
            for name in sorted(names)
        )

    denied_tools = (
        registered_tools - allowed_tools
    )

    return "\n".join([
        "",
        "# 当前 Agent 的工具权限",
        "这是服务端授予的实际工具权限。",
        f"允许执行的任务操作：{describe(allowed_tools)}。",
        f"未授权的任务操作：{describe(denied_tools)}。",
        "不能执行未授权操作。",
        "不得声称已经执行未成功的操作。",
        "介绍自身能力时，只能描述实际获得授权的工具。",
        "用户要求未授权操作时，应如实说明无法执行。",
    ])


# ==========================================
# 4. 普通 AI 对话
# ==========================================

def chat_with_ai(
    history: list[dict[str, str]],
    agent_config=None,
) -> str:

    if client is None:
        raise RuntimeError(
            "未配置 DEEPSEEK_API_KEY"
        )

    config = resolve_agent_config(
        agent_config
    )

    system_prompt = build_system_prompt(
        config
    )

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


# ==========================================
# 5. Agent + Tool Registry
# ==========================================

def chat_with_tools(
    history: list[dict],
    task_summary_func,
    long_term_memory: str = "",
    agent_config=None,
) -> str:
    """
    Agent 工具调用主流程。

    兼容旧调用签名。
    按 enabled_tools 控制模型工具列表和实际执行权限。
    """

    if client is None:
        raise RuntimeError(
            "未配置 DEEPSEEK_API_KEY"
        )

    # 第一阶段：读取 Agent 配置
    config = resolve_agent_config(
        agent_config
    )

    # 第二阶段：创建工具注册表
    registry = build_task_registry(
        task_summary_func=task_summary_func
    )

    registered_tools = {
        item["function"]["name"]
        for item in registry.schemas()
    }

    # 第三阶段：解析 Agent 授权
    allowed_tools = resolve_allowed_tools(
        config,
        registry,
    )

    # 第四阶段：构建模型可见的工具列表
    tool_schemas = registry.schemas(
        allowed_names=allowed_tools
    )

    # 第五阶段：构建动态 Prompt
    system_prompt = build_system_prompt(
        agent_config=config,
        long_term_memory=long_term_memory,
    )

    system_prompt += "\n" + build_permission_context(
        allowed_tools,
        registered_tools,
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        *history,
    ]

    # ======================================
    # 情况 A：Agent 没有任何工具权限
    # ======================================

    if not tool_schemas:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
        )

        message = response.choices[0].message

        # 不执行任何模型意外返回的工具调用
        if getattr(message, "tool_calls", None):
            logger.warning(
                "无工具权限的 Agent 返回了工具调用请求"
            )

            return (
                "当前 Agent 没有工具调用权限，"
                "无法执行该操作。"
            )

        return (
            message.content
            or "模型未返回内容。"
        )

    # ======================================
    # 情况 B：Agent 拥有部分或全部工具
    # ======================================

    total_executions = 0

    for _ in range(MAX_TOOL_ROUNDS):

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # 不需要工具：直接返回回答
        if not message.tool_calls:
            return (
                message.content
                or "模型未返回内容。"
            )

        # 记录模型的工具调用请求
        messages.append(
            message.model_dump(
                exclude_none=True
            )
        )

        for call in message.tool_calls:

            total_executions += 1

            name = call.function.name
            arguments = call.function.arguments

            if total_executions > MAX_TOOL_EXECUTIONS:
                result = {
                    "ok": False,
                    "error": "本次对话工具调用数量已达上限",
                }

            else:
                # 关键：执行时再次检查权限。
                # 即使模型返回未授权工具，也不能执行。
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
