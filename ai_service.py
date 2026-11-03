
import os
import json

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")

SYSTEM_PROMPT = (
    "你是 FlowMind AI，一个智能任务助手。"
    "请使用简洁、清晰的中文回答用户。"
    "如果无法确定答案，请明确说明。"
)

client = (
    OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=30.0,
    )
    if api_key
    else None
)


def chat_with_ai(history: list[dict[str, str]]) -> str:
    if client is None:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
    ]

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
    )

    return response.choices[0].message.content or "模型未返回内容。"

TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_task_summary",
            "description": (
                "获取当前任务的总数、已完成数量、"
                "未完成数量。当用户询问任务统计时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    }
]


def chat_with_tools(
    history: list[dict],
    task_summary_func
) -> str:
    if client is None:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history
    ]

    # 最多允许 3 轮工具调用
    for _ in range(3):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TASK_TOOLS,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # 模型不需要调用工具，直接返回回答
        if not message.tool_calls:
            return message.content or "模型未返回内容。"

        # 保留模型发起的工具调用消息
        messages.append(message.model_dump(
            exclude_none=True
        ))

        for call in message.tool_calls:
            if call.function.name == "get_task_summary":
                result = task_summary_func()
            else:
                result = {"error": "不支持的工具"}

            print(f"[工具调用] {call.function.name}")
            print(f"[工具结果] {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False
                )
            })

    return "工具调用次数达到上限，请简化任务后重试。"
