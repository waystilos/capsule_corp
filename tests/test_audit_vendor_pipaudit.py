#!/usr/bin/env python3
"""Epic 3 / slice B: pip-audit must never build the audited project (F-043)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import security_audit


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_audit(proj):
    calls = []

    def fake_run(command, **kw):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="No known vulnerabilities found", stderr="")

    with patch("security_audit.shutil.which", return_value="/usr/bin/pip-audit"), \
            patch("security_audit.subprocess.run", side_effect=fake_run):
        code, out = security_audit.run_dependency_audit(proj)
    return code, out, calls


class PipAuditSafetyTests(unittest.TestCase):
    def test_requirements_use_no_deps_disable_pip_and_no_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "requirements.txt", "a==1\n")
            write(proj / "requirements-dev.txt", "b==2\n")
            write(proj / "pyproject.toml", "[project]\nname='x'\n")
            code, _, calls = run_audit(proj)
            self.assertEqual(code, 0)
            self.assertEqual(len(calls), 2)
            for argv in calls:
                self.assertEqual(argv[0], "pip-audit")
                self.assertIn("--no-deps", argv)
                self.assertIn("--disable-pip", argv)
                self.assertEqual(argv[1], "-r")
                self.assertNotIn(str(proj), argv)
                self.assertNotIn(str(proj) + "/", argv)

    def test_pyproject_only_is_incomplete_and_never_runs_pip_audit(self):
        for name in ("pyproject.toml", "setup.py"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                proj = Path(tmp).resolve()
                write(proj / name, "x\n")
                code, out, calls = run_audit(proj)
                self.assertEqual(code, 2)
                self.assertEqual(calls, [])
                self.assertIn("INCOMPLETE", out)
                self.assertIn("build", out)

    def test_no_argv_ever_contains_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "requirements.txt", "a==1\n")
            write(proj / "setup.py", "x\n")
            _, _, calls = run_audit(proj)
            for argv in calls:
                for arg in argv[1:]:
                    self.assertFalse(Path(arg).is_dir(), arg)


if __name__ == "__main__":
    unittest.main()
