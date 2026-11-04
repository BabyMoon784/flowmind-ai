
import sqlite3

from database import init_database


def test_database_initialization(tmp_path):
    db_path = tmp_path / "test_flowmind.db"

    init_database(db_path)

    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        result = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='tasks'"
        ).fetchone()

    assert result is not None


def test_database_insert_and_select(tmp_path):
    db_path = tmp_path / "test_flowmind.db"

    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO tasks (title) VALUES (?)",
            ("学习 SQLite",)
        )

        result = conn.execute(
            "SELECT id, title, status FROM tasks"
        ).fetchone()

    assert result[0] == 1
    assert result[1] == "学习 SQLite"
    assert result[2] == "待完成"


def test_database_update(tmp_path):
    db_path = tmp_path / "test_flowmind.db"

    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO tasks (title) VALUES (?)",
            ("完成数据库开发",)
        )

        conn.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            ("已完成", 1)
        )

        status = conn.execute(
            "SELECT status FROM tasks WHERE id = ?",
            (1,)
        ).fetchone()[0]

    assert status == "已完成"
