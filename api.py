
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import task_service as service
import sqlite3


app = FastAPI(
    title="FlowMind AI",
    description="鱼鱼的 AI Agent 后端服务",
    version="0.3.0",
)

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class TaskUpdate(BaseModel):
    status: Literal["待完成", "已完成"]


@app.get("/")
def home():
    return {
        "message": "Welcome to FlowMind AI!",
        "assistant": "鱼鱼",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks():
    try:
        tasks = service.list_tasks()
    except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="任务数据读取失败",
        )

    return {"total": len(tasks), "tasks": tasks}


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    title = task.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="任务名称不能为空",
        )

    try:
        return service.create_task(title)
    except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="创建任务失败",
        )


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
    try:
        return service.update_task_status(
            task_id,
            update.status,
        )

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"任务 ID {task_id} 不存在",
        )

    except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="更新任务失败",
        )

