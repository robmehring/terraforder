import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from terraforder.cli import main

UNSORTED = 'variable "b" {}\nvariable "a" {}\n'
SORTED = 'variable "a" {}\n\nvariable "b" {}\n'


class CliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        cwd = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, cwd)

    def write(self, name: str, content: str) -> Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode())
        return path

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(list(args))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_single_file_prints_to_stdout(self):
        path = self.write("main.tf", UNSORTED)
        code, out, _ = self.run_cli(str(path))
        self.assertEqual((code, out), (0, SORTED))
        self.assertEqual(path.read_text(), UNSORTED)

    def test_write_directory_recursively(self):
        a = self.write("main.tf", UNSORTED)
        b = self.write("sub/vars.tfvars", "b = 1\na = 2\n")
        hidden = self.write(".terraform/mod.tf", UNSORTED)
        other = self.write("notes.txt", UNSORTED)
        code, _, _ = self.run_cli("--write", ".")
        self.assertEqual(code, 0)
        self.assertEqual(a.read_text(), SORTED)
        self.assertEqual(b.read_text(), "a = 2\nb = 1\n")
        self.assertEqual(hidden.read_text(), UNSORTED)
        self.assertEqual(other.read_text(), UNSORTED)

    def test_backup(self):
        path = self.write("main.tf", UNSORTED)
        self.run_cli("--write", "--backup", str(path))
        self.assertEqual(path.read_text(), SORTED)
        self.assertEqual((self.dir / "main.tf.bak").read_text(), UNSORTED)

    def test_backup_requires_write(self):
        path = self.write("main.tf", UNSORTED)
        code, _, err = self.run_cli("--backup", str(path))
        self.assertEqual(code, 2)
        self.assertIn("--backup requires --write", err)

    def test_dry_run_shows_diff_and_fails(self):
        path = self.write("main.tf", UNSORTED)
        code, out, _ = self.run_cli("--dry-run", ".")
        self.assertEqual(code, 1)
        self.assertIn("--- a/main.tf", out)
        self.assertIn('+variable "a" {}', out)
        self.assertEqual(path.read_text(), UNSORTED)

    def test_check_passes_when_sorted(self):
        self.write("main.tf", SORTED)
        code, out, _ = self.run_cli("--check", ".")
        self.assertEqual((code, out), (0, ""))

    def test_multiple_files_need_a_mode(self):
        self.write("a.tf", UNSORTED)
        self.write("b.tf", UNSORTED)
        code, _, err = self.run_cli(".")
        self.assertEqual(code, 2)
        self.assertIn("--write or --dry-run", err)

    def test_parse_error_skips_file_and_continues(self):
        bad = self.write("bad.tf", 'variable "a" {\n')
        good = self.write("good.tf", UNSORTED)
        code, _, err = self.run_cli("--write", ".")
        self.assertEqual(code, 2)
        self.assertIn("bad.tf:1:1: unclosed '{'", err)
        self.assertEqual(bad.read_text(), 'variable "a" {\n')
        self.assertEqual(good.read_text(), SORTED)

    def test_missing_path(self):
        code, _, err = self.run_cli("nope.tf")
        self.assertEqual(code, 2)
        self.assertIn("no such file", err)

    def test_verbose_lists_new_order(self):
        path = self.write("main.tf", UNSORTED)
        _, _, err = self.run_cli("--write", "-v", str(path))
        self.assertIn("reordered:", err)
        self.assertLess(err.index("variable.a"), err.index("variable.b"))

    def test_config_file(self):
        self.write("main.tf", 'variable "v" {}\noutput "o" {}\n')
        self.write(".terraforder.toml", 'order = ["output", "variable"]\n')
        _, out, _ = self.run_cli("main.tf")
        self.assertTrue(out.startswith('output "o"'))

    def test_invalid_config(self):
        self.write("main.tf", UNSORTED)
        cfg = self.write("cfg.toml", "order = 3\n")
        code, _, err = self.run_cli("--config", str(cfg), "main.tf")
        self.assertEqual(code, 2)
        self.assertIn("must be a list", err)

    def test_preserves_bom_and_crlf(self):
        path = self.write("main.tf", "")
        path.write_bytes(b'\xef\xbb\xbfvariable "b" {}\r\nvariable "a" {}\r\n')
        self.run_cli("--write", str(path))
        self.assertEqual(path.read_bytes(), b'\xef\xbb\xbfvariable "a" {}\r\n\r\nvariable "b" {}\r\n')


if __name__ == "__main__":
    unittest.main()
