
import json
import task_service
import main
import memory
import long_term_memory


# 测试 1：没有任务时的统计

def test_empty_tasks(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.json"
    monkeypatch.setattr(
        task_service, "DATA_FILE", test_file
    )

    result = main.get_task_summary()

    assert result == {
        "total": 0,
        "completed": 0,
        "pending": 0,
    }


def test_task_summary(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.json"
    monkeypatch.setattr(
        task_service, "DATA_FILE", test_file
    )

    task_service.create_task("学习 Python")
    second = task_service.create_task("学习 Agent")
    task_service.create_task("学习 FastAPI")

    task_service.update_task_status(
        second["id"], "已完成"
    )

    result = main.get_task_summary()

    assert result == {
        "total": 3,
        "completed": 1,
        "pending": 2,
    }



# 测试 3：聊天历史保存与恢复
def test_chat_history(tmp_path, monkeypatch):
    test_file = tmp_path / "chat_history.json"

    monkeypatch.setattr(memory, "MEMORY_FILE", test_file)

    history = [
        {"role": "user", "content": "你好，鱼鱼"},
        {"role": "assistant", "content": "你好呀！"},
    ]

    memory.save_history(history)

    loaded = memory.load_history()

    assert loaded == history
    assert test_file.exists()


# 测试 4：长期记忆保存与查询
def test_long_term_memory(tmp_path, monkeypatch):
    test_file = tmp_path / "long_term_memory.json"

    monkeypatch.setattr(
        long_term_memory,
        "MEMORY_FILE",
        test_file,
    )

    long_term_memory.remember("assistant_name", "鱼鱼")
    long_term_memory.remember("user_name", "BabyMoon")

    memories = long_term_memory.load_memories()

    assert memories["assistant_name"] == "鱼鱼"
    assert memories["user_name"] == "BabyMoon"


# 测试 5：删除长期记忆
def test_forget_memory(tmp_path, monkeypatch):
    test_file = tmp_path / "long_term_memory.json"

    monkeypatch.setattr(
        long_term_memory,
        "MEMORY_FILE",
        test_file,
    )

    long_term_memory.remember("assistant_name", "鱼鱼")

    result = long_term_memory.forget("assistant_name")

    assert result is True
    assert "assistant_name" not in (
        long_term_memory.load_memories()
    )
