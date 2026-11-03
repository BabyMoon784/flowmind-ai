
import json
from pathlib import Path
from ai_service import chat_with_ai

DATA_FILE = Path(__file__).resolve().parent / "tasks.json"
tasks = []
next_id = 1


def ai_chat():
    print("\n===== FlowMind AI 智能助手 =====")
    print("输入 exit 退出 AI 对话。")

    while True:
        question = input("\n你：").strip()

        if question.lower() == "exit":
            print("已退出 AI 对话。")
            break

        if not question:
            continue

        print("AI 正在思考...")

        answer = chat_with_ai(question)

        print(f"\nAI：{answer}")


def save_tasks():
    data = {
        "next_id": next_id,
        "tasks": tasks
    }

    temp_file = DATA_FILE.with_suffix(".json.tmp")

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        temp_file.replace(DATA_FILE)

    except OSError as e:
        print(f"保存任务失败：{e}")

def create_task():
    global next_id

    title = input("请输入任务名称：").strip()

    if not title:
        print("任务名称不能为空！")
        return

    task = {
        "id": next_id,
        "title": title,
        "status": "待完成"
    }

    tasks.append(task)
    next_id += 1
    save_tasks()

    print(f"任务创建成功！ID: {task['id']}")


def show_tasks():
    if not tasks:
        print("当前没有任务。")
        return

    print("\n===== 任务列表 =====")

    for task in tasks:
        print(
            f"[{task['id']}] "
            f"{task['title']} | {task['status']}"
        )

def load_tasks():
    global tasks, next_id

    if not DATA_FILE.exists():
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        loaded_tasks = data["tasks"]
        loaded_next_id = data["next_id"]

        if not isinstance(loaded_tasks, list):
            raise ValueError("tasks 必须是列表")

        if not isinstance(loaded_next_id, int) or loaded_next_id < 1:
            raise ValueError("next_id 无效")

        tasks = loaded_tasks
        next_id = loaded_next_id

        print(f"已加载 {len(tasks)} 个历史任务。")

    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"加载任务失败：{e}")
        print("本次不会覆盖原有数据，请检查 tasks.json。")
        raise SystemExit(1)

def complete_task():
    try:
        task_id = int(input("请输入要完成的任务 ID："))
    except ValueError:
        print("请输入有效的数字！")
        return

    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "已完成"
            save_tasks()
            print("任务已完成！")
            return

    print("没有找到该任务。")


def main():
    load_tasks()
    while True:
        print("\n========== FlowMind AI ==========")
        print("1. 创建任务")
        print("2. 查看任务")
        print("3. 完成任务")
        print("4. AI 智能助手")
        print("5. 退出程序")

        choice = input("请选择操作：").strip()

        if choice == "1":
            create_task()
        elif choice == "2":
            show_tasks()
        elif choice == "3":
            complete_task()
        elif choice == "4":
            ai_chat()
        elif choice == "5":
            print("再见！")
            break
        else:
            print("无效操作，请重新选择。")


if __name__ == "__main__":
    main()
