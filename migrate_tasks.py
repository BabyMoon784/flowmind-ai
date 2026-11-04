
import json
import shutil
from datetime import datetime
from pathlib import Path

from database import DB_FILE, get_connection, init_database


BASE_DIR = Path(__file__).resolve().parent
JSON_FILE = BASE_DIR / "tasks.json"
BACKUP_DIR = BASE_DIR / ".local_backups"


def load_and_validate():
    """读取并检查旧任务数据。"""
    if not JSON_FILE.exists():
        raise FileNotFoundError("找不到 tasks.json，停止迁移")

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象")

    tasks = data.get("tasks")
    next_id = data.get("next_id")

    if not isinstance(tasks, list):
        raise ValueError("tasks 必须是列表")

    if type(next_id) is not int or next_id < 1:
        raise ValueError("next_id 无效")

    used_ids = set()

    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("存在格式错误的任务")

        task_id = task.get("id")
        title = task.get("title")
        status = task.get("status")

        if type(task_id) is not int or task_id < 1:
            raise ValueError("任务 ID 无效")

        if task_id in used_ids:
            raise ValueError(f"发现重复任务 ID：{task_id}")

        if not isinstance(title, str):
            raise ValueError(f"任务 {task_id} 的标题无效")

        if status not in ("待完成", "已完成"):
            raise ValueError(f"任务 {task_id} 的状态无效")

        used_ids.add(task_id)

    if used_ids and next_id <= max(used_ids):
        raise ValueError("next_id 不大于现有最大任务 ID")

    return tasks, next_id


def migrate():
    tasks, next_id = load_and_validate()

    # 确保目标数据库和表存在
    init_database()

    conn = get_connection()

    try:
        # 不能覆盖已有数据库任务
        count = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        if count != 0:
            raise RuntimeError(
                "数据库已有任务，已停止迁移，避免覆盖或重复导入"
            )

    finally:
        conn.close()

    # 迁移之前备份原文件
    BACKUP_DIR.mkdir(exist_ok=True)

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    shutil.copy2(
        JSON_FILE,
        BACKUP_DIR / f"tasks_{stamp}.json"
    )

    if DB_FILE.exists():
        shutil.copy2(
            DB_FILE,
            BACKUP_DIR / f"flowmind_{stamp}.db"
        )

    print("原始数据备份成功")

    conn = get_connection()

    try:
        # 开始事务；失败时可以回滚
        conn.execute("BEGIN IMMEDIATE")

        count = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        if count != 0:
            raise RuntimeError("数据库已有任务，停止迁移")

        for task in tasks:
            conn.execute(
                """
                INSERT INTO tasks (id, title, status)
                VALUES (?, ?, ?)
                """,
                (
                    task["id"],
                    task["title"],
                    task["status"],
                ),
            )

        # 保留原来的 next_id 进度
        cursor = conn.execute(
            """
            UPDATE sqlite_sequence
            SET seq = MAX(seq, ?)
            WHERE name = 'tasks'
            """,
            (next_id - 1,),
        )

        if cursor.rowcount == 0:
            conn.execute(
                """
                INSERT INTO sqlite_sequence (name, seq)
                VALUES ('tasks', ?)
                """,
                (next_id - 1,),
            )

        # 提交前核对全部任务
        rows = conn.execute(
            "SELECT id, title, status FROM tasks"
        ).fetchall()

        expected = sorted(
            (t["id"], t["title"], t["status"])
            for t in tasks
        )

        actual = sorted(
            (r["id"], r["title"], r["status"])
            for r in rows
        )

        if actual != expected:
            raise RuntimeError("迁移数据校验失败")

        seq = conn.execute(
            """
            SELECT seq FROM sqlite_sequence
            WHERE name = 'tasks'
            """
        ).fetchone()

        if seq is None or seq["seq"] != next_id - 1:
            raise RuntimeError("下一个任务 ID 校验失败")

        conn.commit()

        print("SQLite 数据迁移成功！")
        print(f"迁移任务数量：{len(tasks)}")
        print(f"保留的下一个任务 ID：{next_id}")
        print("任务 ID、标题、状态均已核对")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        migrate()
    except Exception as error:
        print(f"迁移停止：{error}")
        raise SystemExit(1)
