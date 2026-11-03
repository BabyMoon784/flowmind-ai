
import json
from pathlib import Path


MEMORY_FILE = (
    Path(__file__).resolve().parent / "long_term_memory.json"
)


def load_memories():
    """读取全部长期记忆。"""
    if not MEMORY_FILE.exists():
        return {}

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memories = json.load(f)

        if not isinstance(memories, dict):
            raise ValueError("记忆文件必须是 JSON 对象")

        for key, value in memories.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("记忆的键和值必须是字符串")

        return memories

    except (OSError, ValueError) as e:
        raise RuntimeError(
            f"长期记忆读取失败：{e}。"
            "请检查 long_term_memory.json。"
        ) from e


def save_memories(memories):
    """安全写入长期记忆文件。"""
    temp_file = MEMORY_FILE.with_suffix(".json.tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            memories,
            f,
            ensure_ascii=False,
            indent=2
        )

    temp_file.replace(MEMORY_FILE)


def remember(key, value):
    """保存或更新一条记忆。"""
    key = key.strip()
    value = value.strip()

    if not key or not value:
        raise ValueError("记忆名称和内容不能为空")

    if len(key) > 50 or len(value) > 500:
        raise ValueError("记忆名称或内容过长")

    memories = load_memories()
    memories[key] = value

    save_memories(memories)


def forget(key):
    """删除指定长期记忆。"""
    memories = load_memories()

    if key not in memories:
        return False

    del memories[key]
    save_memories(memories)
    return True


def clear_memories():
    """清空所有长期记忆。"""
    save_memories({})


def format_memories():
    """将长期记忆转换为可传给模型的文本。"""
    memories = load_memories()

    if not memories:
        return ""

    return "\n".join(
        f"{key}: {value}"
        for key, value in memories.items()
    )
