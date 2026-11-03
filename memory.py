
import json
from pathlib import Path


MEMORY_FILE = (
    Path(__file__).resolve().parent / "chat_history.json"
)


def load_history():
    if not MEMORY_FILE.exists():
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        if not isinstance(history, list):
            raise ValueError("聊天记录格式错误")

        for message in history:
            if (
                not isinstance(message, dict)
                or message.get("role") not in ("user", "assistant")
                or not isinstance(message.get("content"), str)
            ):
                raise ValueError("聊天消息格式错误")

        return history

    except (OSError, ValueError) as e:
        raise RuntimeError(
            f"读取聊天记录失败：{e}。"
            "请先备份并检查 chat_history.json。"
        ) from e


def save_history(history):
    temp_file = MEMORY_FILE.with_suffix(".json.tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            history,
            f,
            ensure_ascii=False,
            indent=2
        )

    temp_file.replace(MEMORY_FILE)


def clear_history():
    save_history([])
