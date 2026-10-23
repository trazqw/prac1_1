"""Минимальные автоматические тесты для этапов 2–3."""

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.main import VFSError, VirtualShell, load_vfs, parse_command, run_startup_script


class Variant19Tests(unittest.TestCase):
    def test_environment_variable_expansion(self):
        with patch.dict(os.environ, {"V19_TEST": "hello world"}):
            self.assertEqual(parse_command('cd "$V19_TEST"'), ["cd", "hello world"])

    def test_load_valid_vfs(self):
        path = Path("vfs/minimal.json")
        data = load_vfs(path)
        self.assertEqual(data["name"], "MyVFS")

    def test_missing_vfs(self):
        with self.assertRaises(VFSError):
            load_vfs("vfs/does_not_exist.json")

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(VFSError):
                load_vfs(path)

    def test_startup_script_skips_bad_command(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "commands.txt"
            path.write_text("ls\nnot_a_command\ncd folder\n", encoding="utf-8")
            self.assertFalse(run_startup_script(path, "MyVFS> "))

    def test_ls_cd_pwd_and_rev(self):
        vfs = load_vfs("vfs/multiple_files.json")
        shell = VirtualShell(vfs)
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(shell.execute("ls"))
            self.assertTrue(shell.execute("cd docs"))
            self.assertTrue(shell.execute("pwd"))
            self.assertTrue(shell.execute("rev guide.txt"))
        result = output.getvalue()
        self.assertIn("docs/", result)
        self.assertIn("/docs", result)
        self.assertIn("ediuG", result)

    def test_find_by_name(self):
        shell = VirtualShell(load_vfs("vfs/multiple_files.json"))
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(shell.execute('find / -name "*.txt"'))
        self.assertIn("/readme.txt", output.getvalue())
        self.assertIn("/docs/guide.txt", output.getvalue())

    def test_invalid_path_returns_error(self):
        shell = VirtualShell(load_vfs("vfs/minimal.json"))
        output = StringIO()
        with redirect_stdout(output):
            self.assertFalse(shell.execute("cd no_such_directory"))
        self.assertIn("Ошибка:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
