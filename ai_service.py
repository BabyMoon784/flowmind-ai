
import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")


def chat_with_ai(question: str) -> str:
    if not api_key:
        return "错误：未配置 DEEPSEEK_API_KEY"

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 FlowMind AI，一个智能任务助手。"
                        "请用简洁、清晰的中文回答用户。"
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.7
        )

        return response.choices[0].message.content or "模型未返回内容。"

    except Exception as e:
        return f"AI 请求失败：{type(e).__name__}: {e}"
