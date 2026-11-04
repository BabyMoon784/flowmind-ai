
import json
from pathlib import Path
from ai_service import chat_with_tools
from openai import OpenAIError
from memory import load_history, save_history, clear_history
import task_service as service

from long_term_memory import (
    load_memories,
    remember,
    forget,
    clear_memories,
    format_memories,
)


MAX_HISTORY_MESSAGES = 10

DATA_FILE = Path(__file__).resolve().parent / "tasks.json"
tasks = []
next_id = 1


def ai_chat():
    try:
        history = load_history()
    except RuntimeError as e:
        print(f"加载聊天记录失败：{e}")
        return

    print("\n===== FlowMind AI 智能助手 =====")
    print("输入 exit 退出，clear 清空，history 查看记录。")
    print(f"已恢复 {len(history) // 2} 轮历史对话。")

    while True:
        question = input("\n你：").strip()


        # Memory v2：长期记忆管理命令
        if question.startswith("/remember "):
            parts = question.split(maxsplit=2)

            if len(parts) != 3:
                print("用法：/remember 记忆名称 记忆内容")
                continue

            try:
                remember(parts[1], parts[2])
                print(f"长期记忆已保存：{parts[1]}")
            except (ValueError, OSError, RuntimeError) as e:
                print(f"保存失败：{e}")

            continue

        if question == "/memories":
            try:
                memories = load_memories()

                if not memories:
                    print("目前没有长期记忆。")
                else:
                    print("\n===== 长期记忆 =====")
                    for key, value in memories.items():
                        print(f"{key}: {value}")

            except RuntimeError as e:
                print(f"读取失败：{e}")

            continue

        if question.startswith("/forget "):
            key = question[len("/forget "):].strip()

            try:
                if forget(key):
                    print(f"已删除记忆：{key}")
                else:
                    print("没有找到这条记忆。")
            except (OSError, RuntimeError) as e:
                print(f"删除失败：{e}")

            continue

        if question == "/clear-memory":
            confirm = input("确定清空全部长期记忆？输入 YES：")

            if confirm == "YES":
                try:
                    clear_memories()
                    print("全部长期记忆已清空。")
                except OSError as e:
                    print(f"清空失败：{e}")
            else:
                print("已取消。")

            continue


        if question.lower() == "exit":
            print("已退出 AI 对话。")
            break

        if question.lower() == "clear":
            try:
                clear_history()
            except OSError as e:
                print(f"清空聊天记录失败：{e}")
                continue

            history.clear()
            print("聊天记录已清空。")
            continue

        if question.lower() == "history":
            if not history:
                print("当前没有聊天记录。")
            else:
                for message in history:
                    role = (
                        "你" if message["role"] == "user"
                        else "AI"
                    )
                    print(f"{role}：{message['content']}")
            continue

        if not question:
            print("输入不能为空。")
            continue

        request_history = [
            *history[-MAX_HISTORY_MESSAGES:],
            {"role": "user", "content": question},
        ]

        print("AI 正在思考...")

        try:
            
            answer = chat_with_tools(
            request_history,
            get_task_summary,
            long_term_memory=format_memories()  )

        except (OpenAIError, RuntimeError) as e:
            print(f"AI 请求失败：{type(e).__name__}: {e}")
            continue

        print(f"\nAI：{answer}")

        history.append({
            "role": "user",
            "content": question,
        })

        history.append({
            "role": "assistant",
            "content": answer,
        })

        try:
            save_history(history)
        except OSError as e:
            print(f"保存聊天记录失败：{e}")


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
    title = input("请输入任务名称：").strip()

    try:
        task = service.create_task(title)
        print(f"任务创建成功！ID: {task['id']}")

    except ValueError as e:
        print(f"输入错误：{e}")

    except (OSError, KeyError, TypeError) as e:
        print(f"创建任务失败：{e}")




def show_tasks():
    try:
        tasks = service.list_tasks()
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"读取任务失败：{e}")
        return

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

    try:
        service.update_task_status(task_id, "已完成")
        print("任务已完成！")

    except LookupError:
        print("没有找到该任务。")

    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"更新任务失败：{e}")




def get_task_summary():
    return service.get_task_summary()




def main():
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
