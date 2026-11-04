
import pytest
from fastapi.testclient import TestClient

import task_service
from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 使用临时文件，不碰真实 tasks.json
    test_file = tmp_path / "tasks.json"

    monkeypatch.setattr(
        task_service,
        "DATA_FILE",
        test_file,
    )

    with TestClient(app) as test_client:
        yield test_client


def test_get_empty_tasks(client):
    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "tasks": [],
    }


def test_create_and_read_task(client):
    response = client.post(
        "/tasks",
        json={"title": "学习 FastAPI"},
    )

    assert response.status_code == 201

    task = response.json()

    assert task["id"] == 1
    assert task["status"] == "待完成"

    result = client.get("/tasks").json()

    assert result["total"] == 1
    assert result["tasks"][0]["title"] == "学习 FastAPI"


def test_update_task_status(client):
    task = client.post(
        "/tasks",
        json={"title": "完成项目"},
    ).json()

    response = client.patch(
        f"/tasks/{task['id']}",
        json={"status": "已完成"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "已完成"

    result = client.get("/tasks").json()
    assert result["tasks"][0]["status"] == "已完成"


def test_task_not_found(client):
    response = client.patch(
        "/tasks/99999",
        json={"status": "已完成"},
    )

    assert response.status_code == 404


def test_invalid_task_status(client):
    response = client.patch(
        "/tasks/1",
        json={"status": "正在摸鱼"},
    )

    assert response.status_code == 422


def test_blank_task_title(client):
    response = client.post(
        "/tasks",
        json={"title": "   "},
    )

    assert response.status_code == 422
