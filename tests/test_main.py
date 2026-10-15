import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.main import VFSError, load_vfs, parse_command, run_startup_script


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


if __name__ == "__main__":
    unittest.main()
