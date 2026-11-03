
import os

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

