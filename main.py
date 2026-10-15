import os
import shlex


VFS_NAME = "MyVFS"


def execute_command(command_line):

    command_line = os.path.expandvars(command_line)

    try:
        parts = shlex.split(command_line)
    except ValueError as error:
        print(f"Ошибка разбора команды: {error}")
        return

    if not parts:
        return

    command = parts[0]
    args = parts[1:]

    if command == "exit":
        raise SystemExit

    elif command == "ls":
        print("Команда: ls")
        print("Аргументы:", args)

    elif command == "cd":
        print("Команда: cd")
        print("Аргументы:", args)

    else:
        print(f"Ошибка: неизвестная команда '{command}'")


def main():

    print("Командный интерпретатор запущен.")
    print("Для выхода введите exit.")

    while True:
        try:
            command_line = input(f"{VFS_NAME}> ")
            execute_command(command_line)

        except EOFError:
            print("\nЗавершение работы.")
            break

        except KeyboardInterrupt:
            print("\nДля выхода введите exit.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        print("Работа завершена.")

