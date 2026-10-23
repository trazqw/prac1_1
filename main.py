"""Консольный эмулятор оболочки ОС, вариант 19, этапы 1–4."""

import argparse
import base64
import fnmatch
import json
import os
import shlex
import sys
from pathlib import Path, PurePosixPath

DEFAULT_VFS = Path("vfs/minimal.json")


class VFSError(Exception):
    """Ошибка загрузки или проверки виртуальной файловой системы."""


class CommandError(Exception):
    """Ошибка выполнения команды эмулятора."""


def load_vfs(path):
    """Загрузить и проверить JSON-представление VFS в память."""
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
    root = data.get("root")
    if not isinstance(root, dict) or root.get("type") != "directory":
        raise VFSError("поле 'root' должно описывать каталог")
    if not isinstance(root.get("children", {}), dict):
        raise VFSError("поле 'children' корневого каталога должно быть объектом")
    _validate_node(root, "/")
    return data


def _validate_node(node, path):
    if not isinstance(node, dict) or node.get("type") not in {"directory", "file"}:
        raise VFSError(f"неверное описание элемента VFS: {path}")
    if node["type"] == "directory":
        children = node.get("children", {})
        if not isinstance(children, dict):
            raise VFSError(f"поле 'children' должно быть объектом: {path}")
        for name, child in children.items():
            if not isinstance(name, str) or name in {"", ".", ".."} or "/" in name:
                raise VFSError(f"недопустимое имя элемента в каталоге {path}")
            _validate_node(child, str(PurePosixPath(path) / name))
    else:
        if not isinstance(node.get("content", ""), str):
            raise VFSError(f"содержимое файла должно быть строкой: {path}")
        if node.get("encoding", "utf-8") not in {"utf-8", "base64", "binary"}:
            raise VFSError(f"неподдерживаемая кодировка файла: {path}")


def parse_command(command_line):
    """Раскрыть переменные окружения и разделить строку на команду и аргументы."""
    expanded = os.path.expandvars(command_line)
    try:
        return shlex.split(expanded)
    except ValueError as error:
        raise ValueError(f"ошибка разбора команды: {error}") from error


class VirtualShell:
    """Командный интерпретатор, работающий только с объектами VFS в памяти."""

    def __init__(self, vfs):
        self.vfs = vfs
        self.cwd = []

    @property
    def prompt(self):
        current = "/" + "/".join(self.cwd) if self.cwd else "/"
        return f"{self.vfs['name']}:{current}$ "

    def _resolve_parts(self, path):
        if not path:
            path = "/"
        parts = [] if path.startswith("/") else list(self.cwd)
        for part in path.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        return parts

    def _get_node(self, path):
        parts = self._resolve_parts(path)
        node = self.vfs["root"]
        for part in parts:
            if node.get("type") != "directory":
                raise CommandError(f"'{part}' находится не в каталоге")
            children = node.get("children", {})
            if part not in children:
                raise CommandError(f"путь не найден: {path}")
            node = children[part]
        return node, parts

    @staticmethod
    def _display_path(parts):
        return "/" + "/".join(parts) if parts else "/"

    def _ls(self, args):
        if len(args) > 1:
            raise CommandError("использование: ls [путь]")
        path = args[0] if args else "."
        node, _ = self._get_node(path)
        if node["type"] == "file":
            print(PurePosixPath(path).name or path)
            return
        children = node.get("children", {})
        if not children:
            print("(пустой каталог)")
            return
        for name in sorted(children):
            item = children[name]
            print(name + ("/" if item.get("type") == "directory" else ""))

    def _cd(self, args):
        if len(args) > 1:
            raise CommandError("использование: cd [каталог]")
        path = args[0] if args else "/"
        node, parts = self._get_node(path)
        if node.get("type") != "directory":
            raise CommandError(f"не является каталогом: {path}")
        self.cwd = parts

    def _rev(self, args):
        if len(args) != 1:
            raise CommandError("использование: rev <файл>")
        node, _ = self._get_node(args[0])
        if node.get("type") != "file":
            raise CommandError(f"не является файлом: {args[0]}")
        encoding = node.get("encoding", "utf-8")
        content = node.get("content", "")
        if encoding in {"base64", "binary"}:
            try:
                content = base64.b64decode(content, validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as error:
                raise CommandError("невозможно выполнить rev для двоичного файла") from error
        for line in content.splitlines():
            print(line[::-1])
        if content and not content.endswith(("\n", "\r")) and "\n" not in content:
            return

    def _find(self, args):
        path = "."
        pattern = "*"
        if args:
            if args[0] == "-name":
                if len(args) != 2:
                    raise CommandError("использование: find [путь] [-name шаблон]")
                pattern = args[1]
            else:
                path = args[0]
                if len(args) == 2:
                    pattern = args[1]
                elif len(args) == 3 and args[1] == "-name":
                    pattern = args[2]
                elif len(args) > 1:
                    raise CommandError("использование: find [путь] [-name шаблон]")
        start_node, start_parts = self._get_node(path)
        start_path = self._display_path(start_parts)
        if fnmatch.fnmatch(PurePosixPath(start_path).name or "/", pattern):
            print(start_path)
        if start_node.get("type") == "directory":
            self._walk_find(start_node, start_parts, pattern)

    def _walk_find(self, directory, parent_parts, pattern):
        for name in sorted(directory.get("children", {})):
            node = directory["children"][name]
            parts = parent_parts + [name]
            path = self._display_path(parts)
            if fnmatch.fnmatch(name, pattern):
                print(path)
            if node.get("type") == "directory":
                self._walk_find(node, parts, pattern)

    def execute(self, command_line):
        try:
            parts = parse_command(command_line)
        except ValueError as error:
            print(f"Ошибка: {error}")
            return False
        if not parts:
            return True

        command, *args = parts
        try:
            if command == "exit":
                if args:
                    raise CommandError("использование: exit")
                raise SystemExit
            if command == "ls":
                self._ls(args)
            elif command == "cd":
                self._cd(args)
            elif command == "pwd":
                if args:
                    raise CommandError("использование: pwd")
                print(self._display_path(self.cwd))
            elif command == "rev":
                self._rev(args)
            elif command == "find":
                self._find(args)
            else:
                raise CommandError(f"неизвестная команда '{command}'")
            return True
        except CommandError as error:
            print(f"Ошибка: {error}")
            return False


def execute_command(command_line):
    """Совместимость с интерфейсом этапа 1 для запуска команды-заглушки."""
    try:
        vfs = load_vfs(DEFAULT_VFS)
    except VFSError:
        vfs = {"name": "MyVFS", "root": {"type": "directory", "children": {}}}
    return VirtualShell(vfs).execute(command_line)


def run_startup_script(script_path, prompt=None, shell=None):
    """Выполнить команды из скрипта; после ошибки продолжить следующие строки."""
    path = Path(script_path)
    try:
        with path.open("r", encoding="utf-8") as file:
            lines = file.readlines()
    except OSError as error:
        print(f"Ошибка стартового скрипта '{path}': {error}")
        return False

    if shell is None:
        try:
            shell = VirtualShell(load_vfs(DEFAULT_VFS))
        except VFSError:
            shell = VirtualShell({"name": "MyVFS", "root": {"type": "directory", "children": {}}})
    prompt = prompt or shell.prompt
    had_errors = False
    for line_number, raw_line in enumerate(lines, start=1):
        command_line = raw_line.strip()
        if not command_line or command_line.startswith("#"):
            continue
        print(f"{shell.prompt if shell else prompt}{command_line}")
        try:
            success = shell.execute(command_line)
        except SystemExit:
            print("Работа завершена.")
            break
        if not success:
            had_errors = True
            print(f"Ошибка выполнения стартового скрипта: строка {line_number}")
    return not had_errors


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Консольный эмулятор оболочки ОС (вариант 19)")
    parser.add_argument("--vfs", default=str(DEFAULT_VFS), help="путь к JSON-файлу VFS")
    parser.add_argument("--script", help="путь к стартовому скрипту")
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

    shell = VirtualShell(vfs)
    if args.script:
        run_startup_script(args.script, shell=shell)
    print("Командный интерпретатор запущен.")
    print("Доступные команды: ls, cd, rev, pwd, find, exit.")
    while True:
        try:
            command_line = input(shell.prompt)
            shell.execute(command_line)
        except EOFError:
            print("\nЗавершение работы.")
            break
        except KeyboardInterrupt:
            print("\nДля выхода введите exit.")
        except SystemExit:
            print("Работа завершена.")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
