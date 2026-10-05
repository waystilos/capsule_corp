#!/usr/bin/env python3
"""Regression tests: `capsule spy` must fail closed and not be evaded (temp repos only)."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import spy_watchdog  # noqa: E402
from room import clock_in  # noqa: E402
from spy_watchdog import audit_agent_drift  # noqa: E402


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
                   cwd=str(cwd), check=True, capture_output=True)


def make_repo(root, files=("seed.txt",)):
    git(root, "init", "-q")
    for f in files:
        (root / f).write_text("x", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")


def run_main(root):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spy_watchdog.main([str(root)])
    return code, out.getvalue()


def types(report):
    return [i["type"] for i in report["issues"]]


class TestFailClosed(unittest.TestCase):
    def test_non_git_dir_is_incomplete_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            clock_in(root, agent="goku", task="t", files=["a.py"])
            (root / "rogue.py").write_text("x", encoding="utf-8")
            report = audit_agent_drift(root)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertIn("INCOMPLETE", types(report))
            code, out = run_main(root)
            self.assertEqual(code, 2)
            self.assertNotIn("PERFECTLY ALIGNED", out)

    def test_bad_git_dir_env_is_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            clock_in(root, agent="goku", task="t", files=["a.py"])
            (root / "rogue.py").write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {"GIT_DIR": "/nonexistent/gitdir"}):
                self.assertEqual(audit_agent_drift(root)["status"], "INCOMPLETE")
                self.assertEqual(run_main(root)[0], 2)


class TestHiddenFiles(unittest.TestCase):
    def test_assume_unchanged_edit_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, ("seed.txt", "secret.py"))
            clock_in(root, agent="goku", task="t", files=["seed.txt"])
            git(root, "update-index", "--assume-unchanged", "secret.py")
            (root / "secret.py").write_text("rogue edit", encoding="utf-8")
            report = audit_agent_drift(root)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertTrue(any("secret.py" in f for i in report["issues"] for f in i.get("files", [])))
            self.assertEqual(run_main(root)[0], 2)

    def test_skip_worktree_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, ("seed.txt", "secret.py"))
            clock_in(root, agent="goku", task="t", files=["seed.txt"])
            git(root, "update-index", "--skip-worktree", "secret.py")
            self.assertEqual(audit_agent_drift(root)["status"], "INCOMPLETE")

    def test_info_exclude_hides_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            clock_in(root, agent="goku", task="t", files=["seed.txt"])
            (root / ".git" / "info" / "exclude").write_text("rogue.py\n", encoding="utf-8")
            (root / "rogue.py").write_text("x", encoding="utf-8")
            report = audit_agent_drift(root)
            self.assertIn("rogue.py", report["dirty_files"])
            self.assertIn("rogue.py", report["unclaimed_files"])
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("HIDDEN_BY_EXCLUDE", types(report))

    def test_default_info_exclude_comments_only_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            clock_in(root, agent="goku", task="t", files=["seed.txt"])
            self.assertEqual(audit_agent_drift(root)["status"], "ALIGNED")


class TestDependencyAndClaims(unittest.TestCase):
    def test_lookalike_claim_does_not_suppress_dependency_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, ("package.json", "mypackage_notes.txt"))
            clock_in(root, agent="goku", task="t", files=["mypackage_notes.txt", "deps_dir"])
            (root / "package.json").write_text("{}", encoding="utf-8")
            self.assertIn("DEPENDENCY_TAMPERING", types(audit_agent_drift(root)))

    def test_lookalike_filename_is_not_a_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, ("notpackage.json",))
            clock_in(root, agent="goku", task="t", files=["notpackage.json"])
            (root / "notpackage.json").write_text("{}", encoding="utf-8")
            self.assertNotIn("DEPENDENCY_TAMPERING", types(audit_agent_drift(root)))

    def test_explicit_manifest_claim_authorizes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root, ("package.json",))
            clock_in(root, agent="goku", task="t", files=["package.json"])
            (root / "package.json").write_text("{}", encoding="utf-8")
            self.assertNotIn("DEPENDENCY_TAMPERING", types(audit_agent_drift(root)))

    def test_dot_claim_flagged_overbroad(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            clock_in(root, agent="goku", task="t", files=["."])
            (root / "anything.py").write_text("x", encoding="utf-8")
            report = audit_agent_drift(root)
            self.assertIn("OVERBROAD_CLAIM", types(report))
            self.assertEqual(report["verdict"], "FAIL")

    def test_overbroad_detector_variants(self):
        for raw in (".", "./", "*", "**", "/"):
            self.assertTrue(spy_watchdog.is_overbroad_claim(raw, raw.rstrip("/") or "/" if raw != "./" else "."), raw)
        self.assertFalse(spy_watchdog.is_overbroad_claim("src", "src"))
        self.assertFalse(spy_watchdog.is_overbroad_claim(".github", ".github"))


if __name__ == "__main__":
    unittest.main()
