import argparse
import json
import os
import shlex
import sys
from pathlib import Path

DEFAULT_VFS = Path("vfs/minimal.json")
DEFAULT_VFS_NAME = "MyVFS"


class VFSError(Exception):

def load_vfs(path):
    vfs_path = Path(path)
    try:
        with vfs_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as error:
        raise VFSError(f"файл VFS не найден: {vfs_path}") from error
    except json.JSONDecodeError as error:
        raise VFSError(
            f"неверный формат JSON в файле VFS: строка {error.lineno}, "
            f"столбец {error.colno}"
        ) from error
    except OSError as error:
        raise VFSError(f"не удалось прочитать VFS: {error}") from error

    if not isinstance(data, dict):
        raise VFSError("корень JSON должен быть объектом")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise VFSError("в VFS должно быть непустое строковое поле 'name'")
    if not isinstance(data.get("root"), dict):
        raise VFSError("в VFS должно быть объектное поле 'root'")
    if data["root"].get("type") != "directory":
        raise VFSError("поле 'root' должно описывать каталог")
    if not isinstance(data["root"].get("children", {}), dict):
        raise VFSError("поле 'children' корневого каталога должно быть объектом")
    return data


def parse_command(command_line):
    expanded = os.path.expandvars(command_line)
    try:
        parts = shlex.split(expanded)
    except ValueError as error:
        raise ValueError(f"ошибка разбора команды: {error}") from error
    return parts


def execute_command(command_line):
    try:
        parts = parse_command(command_line)
    except ValueError as error:
        print(f"Ошибка: {error}")
        return False

    if not parts:
        return True

    command, *args = parts
    if command == "exit":
        if args:
            print("Ошибка: команда exit не принимает аргументы")
            return False
        raise SystemExit

    if command in {"ls", "cd"}:
        print(f"Команда: {command}")
        print("Аргументы:", args)
        return True

    print(f"Ошибка: неизвестная команда '{command}'")
    return False


def run_startup_script(script_path, prompt):
    path = Path(script_path)
    try:
        with path.open("r", encoding="utf-8") as file:
            lines = file.readlines()
    except OSError as error:
        print(f"Ошибка стартового скрипта '{path}': {error}")
        return False

    had_errors = False
    for line_number, raw_line in enumerate(lines, start=1):
        command_line = raw_line.strip()
        if not command_line:
            continue
        print(f"{prompt}{command_line}")
        try:
            success = execute_command(command_line)
        except SystemExit:
            print("Работа завершена.")
            break
        if not success:
            had_errors = True
            print(f"Ошибка выполнения стартового скрипта: строка {line_number}")
    return not had_errors


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Консольный эмулятор оболочки ОС (вариант 19)"
    )
    parser.add_argument(
        "--vfs",
        default=str(DEFAULT_VFS),
        help="путь к JSON-файлу виртуальной файловой системы",
    )
    parser.add_argument(
        "--script",
        help="путь к стартовому скрипту с командами эмулятора",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    print("Параметры запуска:")
    print(f"  VFS: {args.vfs}")
    print(f"  Стартовый скрипт: {args.script if args.script else 'не задан'}")

    try:
        vfs = load_vfs(args.vfs)
    except VFSError as error:
        print(f"Ошибка загрузки VFS: {error}")
        return 1

    prompt = f"{vfs['name']}> "
    if args.script:
        run_startup_script(args.script, prompt)

    print("Командный интерпретатор запущен.")
    print("Для выхода введите exit.")
    while True:
        try:
            command_line = input(prompt)
            execute_command(command_line)
        except EOFError:
            print("\nЗавершение работы.")
            break
        except KeyboardInterrupt:
            print("\nДля выхода введите exit.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit as error:
        if error.code in (None, 0):
            print("Работа завершена.")
        elif isinstance(error.code, int):
            sys.exit(error.code)
