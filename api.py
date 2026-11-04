
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="FlowMind AI",
    description="鱼鱼的 AI Agent 后端服务",
    version="0.2.0"
)

DATA_FILE = Path(__file__).resolve().parent / "tasks.json"


# 定义客户端创建任务时需要提交的数据
class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class TaskUpdate(BaseModel):
    status: Literal["待完成", "已完成"]


# 从 JSON 文件读取任务数据
def read_task_data():
    if not DATA_FILE.exists():
        return {
            "next_id": 1,
            "tasks": []
        }

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("任务文件格式错误")

        tasks = data["tasks"]
        next_id = data["next_id"]

        if not isinstance(tasks, list):
            raise ValueError("tasks 必须是列表")

        if type(next_id) is not int or next_id < 1:
            raise ValueError("next_id 无效")

        return data

    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="任务数据读取失败"
        )


# 将任务数据保存到 JSON 文件
def write_task_data(data):
    temp_file = DATA_FILE.with_suffix(".json.tmp")

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        temp_file.replace(DATA_FILE)

    except OSError:
        raise HTTPException(
            status_code=500,
            detail="任务数据保存失败"
        )


@app.get("/")
def home():
    return {
        "message": "Welcome to FlowMind AI!",
        "assistant": "鱼鱼",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks():
    data = read_task_data()

    return {
        "total": len(data["tasks"]),
        "tasks": data["tasks"]
    }


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    title = task.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="任务名称不能为空"
        )

    data = read_task_data()

    new_task = {
        "id": data["next_id"],
        "title": title,
        "status": "待完成"
    }

    data["tasks"].append(new_task)
    data["next_id"] += 1

    write_task_data(data)

    return new_task


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
    data = read_task_data()

    for task in data["tasks"]:
        if task["id"] == task_id:
            task["status"] = update.status

            write_task_data(data)

            return task

    raise HTTPException(
        status_code=404,
        detail=f"任务 ID {task_id} 不存在"
    )
