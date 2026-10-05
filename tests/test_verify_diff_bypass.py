#!/usr/bin/env python3
"""Regression tests: the verify/check diff secret gate must not be bypassable via diff-format tricks."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

from verify_project import audit_git_diff, scan_file_content  # noqa: E402

KEY = "AKIA" + "ABCDEFGHIJKLMNOP"  # fake AWS key assembled at runtime


def git(root, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
                   cwd=str(root), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class DiffBypass(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        git(self.root, "init", "-q")
        (self.root / "f.txt").write_bytes(b"base\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        self._td.cleanup()

    def write(self, data):
        (self.root / "f.txt").write_bytes(data)

    def sev(self):
        return [i["severity"] for i in audit_git_diff(self.root)]

    def assertCaught(self, severity="CRITICAL"):
        issues = audit_git_diff(self.root)
        self.assertTrue(any(i["severity"] == severity for i in issues), issues)

    def test_plus_plus_line(self):
        # added line "++<key>" renders as "+++<key>"; old filter dropped any '+++' line
        self.write(b"base\n++" + KEY.encode() + b"\n")
        self.assertCaught()

    def test_unicode_line_separators(self):
        # old text.splitlines() split on these, leaving the key on a line without a '+' prefix
        for sep in (b"\x0b", b"\x0c", b"\x1c", "\x85".encode("utf-8")):
            with self.subTest(sep=sep):
                self.write(b"base\nx" + sep + KEY.encode() + b"\n")
                self.assertCaught()

    def test_nul_byte_binary(self):
        # git treats NUL files as binary: "Binary files differ", no '+' lines at all
        self.write(b"base\n\x00" + KEY.encode() + b"\n")
        self.assertCaught()

    def test_gitattributes_nodiff(self):
        (self.root / ".gitattributes").write_text("* -diff\n")
        git(self.root, "add", ".gitattributes")
        git(self.root, "commit", "-qm", "attr")
        self.write(b"base\n" + KEY.encode() + b"\n")
        self.assertCaught()

    def test_assume_unchanged(self):
        git(self.root, "update-index", "--assume-unchanged", "f.txt")
        self.write(b"base\n" + KEY.encode() + b"\n")
        issues = audit_git_diff(self.root)
        self.assertIn("INCOMPLETE", [i["severity"] for i in issues])
        self.assertIn("CRITICAL", [i["severity"] for i in issues])  # content scan still finds it

    def test_skip_worktree(self):
        git(self.root, "update-index", "--skip-worktree", "f.txt")
        self.write(b"base\n" + KEY.encode() + b"\n")
        self.assertIn("INCOMPLETE", self.sev())

    def test_textconv_and_extdiff(self):
        (self.root / ".gitattributes").write_text("*.txt diff=evil\n")
        git(self.root, "add", ".gitattributes")
        git(self.root, "commit", "-qm", "attr")
        git(self.root, "config", "diff.evil.textconv", "true")  # output empty -> hides content
        git(self.root, "config", "diff.external", "true")
        self.write(b"base\n" + KEY.encode() + b"\n")
        self.assertCaught()

    def test_clean_repo_passes(self):
        self.assertEqual(audit_git_diff(self.root), [])

    def test_scan_time_budget_fails_closed(self):
        self.write(b"base\n" + b"x\n" * 10)
        issues = []
        scan_file_content(self.root / "f.txt", "f.txt", os.path.realpath(str(self.root)), issues,
                          time_budget=-1.0)
        self.assertEqual([i["severity"] for i in issues], ["INCOMPLETE"])

    def test_merge_marker_with_odd_separator(self):
        self.write(b"base\n<<<<<<< HEAD\n=======\n>>>>>>> x\n")
        self.assertCaught()


class CheckSharesGate(unittest.TestCase):
    def test_check_reports_non_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git(root, "init", "-q")
            (root / "f.txt").write_text("base\n")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "i")
            (root / "f.txt").write_bytes(b"base\n\x00" + KEY.encode() + b"\n")
            r = subprocess.run([sys.executable, str(CAPSULE_ROOT / "scripts" / "check_project.py"),
                                str(root), "--skip-tests"], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
