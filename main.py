
tasks = []
next_id = 1


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


def complete_task():
    try:
        task_id = int(input("请输入要完成的任务 ID："))
    except ValueError:
        print("请输入有效的数字！")
        return

    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "已完成"
            print("任务已完成！")
            return

    print("没有找到该任务。")


def main():
    while True:
        print("\n========== FlowMind AI ==========")
        print("1. 创建任务")
        print("2. 查看任务")
        print("3. 完成任务")
        print("4. 退出程序")

        choice = input("请选择操作：").strip()

        if choice == "1":
            create_task()
        elif choice == "2":
            show_tasks()
        elif choice == "3":
            complete_task()
        elif choice == "4":
            print("再见！")
            break
        else:
            print("无效操作，请重新选择。")


if __name__ == "__main__":
    main()
