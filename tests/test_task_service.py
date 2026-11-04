
import pytest

import task_service


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "tasks.db"

    monkeypatch.setattr(
        task_service,
        "DB_FILE",
        db_file,
    )

    return db_file


def test_task_persistence(isolated_db):
    task = task_service.create_task("测试持久化")

    tasks = task_service.list_tasks()

    assert len(tasks) == 1
    assert tasks[0] == task
    assert isolated_db.exists()


def test_task_ids_increment(isolated_db):
    first = task_service.create_task("任务 A")
    second = task_service.create_task("任务 B")

    assert second["id"] > first["id"]


def test_update_missing_task(isolated_db):
    with pytest.raises(LookupError):
        task_service.update_task_status(
            99999, "已完成"
        )


def test_invalid_task_title(isolated_db):
    with pytest.raises(ValueError):
        task_service.create_task("   ")


