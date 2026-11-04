
import json
from pathlib import Path


DATA_FILE = Path(__file__).resolve().parent / "tasks.json"


def read_data():
    """读取当前任务数据。"""
    if not DATA_FILE.exists():
        return {"next_id": 1, "tasks": []}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("tasks"), list)
        or type(data.get("next_id")) is not int
        or data["next_id"] < 1
    ):
        raise ValueError("任务数据文件格式不正确")

    return data


def write_data(data):
    """把任务数据写入 JSON 文件。"""
    temp_file = DATA_FILE.with_suffix(".json.tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    temp_file.replace(DATA_FILE)


def list_tasks():
    """获取所有任务。"""
    return read_data()["tasks"]


def create_task(title):
    """创建任务并自动生成 ID。"""
    title = title.strip()

    if not title or len(title) > 100:
        raise ValueError("任务名称必须是 1～100 个字符")

    data = read_data()

    new_task = {
        "id": data["next_id"],
        "title": title,
        "status": "待完成",
    }

    data["tasks"].append(new_task)
    data["next_id"] += 1

    write_data(data)
    return new_task


def update_task_status(task_id, status):
    """修改指定任务状态。"""
    if status not in ("待完成", "已完成"):
        raise ValueError("任务状态不合法")

    data = read_data()

    for task in data["tasks"]:
        if task["id"] == task_id:
            task["status"] = status
            write_data(data)
            return task

    raise LookupError(f"任务 {task_id} 不存在")


def get_task_summary():
    """统计当前任务状态。"""
    tasks = list_tasks()

    completed = sum(
        task["status"] == "已完成"
        for task in tasks
    )

    return {
        "total": len(tasks),
        "completed": completed,
        "pending": len(tasks) - completed,
    }
