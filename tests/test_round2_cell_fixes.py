#!/usr/bin/env python3
"""Round-2 Cell fixes: exclude-source hiding (spy, verify) and security routing."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

from room import clock_in  # noqa: E402
from spy_watchdog import audit_agent_drift  # noqa: E402
from verify_project import audit_git_diff  # noqa: E402

KEY = "AKIA" + "ABCDEFGHIJKLMNOP"  # fake AWS key assembled at runtime


def git(root, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
                   cwd=str(root), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_repo(root):
    git(root, "init", "-q")
    (root / "seed.txt").write_text("x", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")


class ExcludesFileHiding(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name) / "repo"
        self.root.mkdir()
        self.ex = Path(self._td.name) / "ex.txt"
        make_repo(self.root)

    def tearDown(self):
        self._td.cleanup()

    def hide_via_excludes_file(self):
        self.ex.write_text("rogue.py\n", encoding="utf-8")
        git(self.root, "config", "core.excludesFile", str(self.ex))
        (self.root / "rogue.py").write_text("x = '%s'\n" % KEY, encoding="utf-8")

    def test_spy_flags_core_excludesfile_hidden_file(self):
        clock_in(self.root, agent="goku", task="t", files=["seed.txt"])
        self.hide_via_excludes_file()
        report = audit_agent_drift(self.root)
        self.assertIn("rogue.py", report["dirty_files"])
        self.assertEqual(report["verdict"], "FAIL")
        self.assertIn("HIDDEN_BY_EXCLUDE", [i["type"] for i in report["issues"]])

    def test_spy_gitignore_ignored_stays_clean(self):
        clock_in(self.root, agent="goku", task="t", files=["seed.txt", ".gitignore"])
        (self.root / ".gitignore").write_text("build.log\n", encoding="utf-8")
        (self.root / "build.log").write_text("x", encoding="utf-8")
        report = audit_agent_drift(self.root)
        self.assertNotIn("build.log", report["dirty_files"])
        self.assertNotIn("HIDDEN_BY_EXCLUDE", [i["type"] for i in report["issues"]])

    def test_verify_scans_core_excludesfile_hidden_secret(self):
        self.hide_via_excludes_file()
        self.assertTrue(any(i["severity"] == "CRITICAL" for i in audit_git_diff(self.root)))

    def test_verify_scans_info_exclude_hidden_secret(self):
        (self.root / ".git" / "info" / "exclude").write_text("rogue.py\n", encoding="utf-8")
        (self.root / "rogue.py").write_text("x = '%s'\n" % KEY, encoding="utf-8")
        self.assertTrue(any(i["severity"] == "CRITICAL" for i in audit_git_diff(self.root)))

    def test_verify_gitignored_secret_skipped(self):
        (self.root / ".gitignore").write_text(".env\n", encoding="utf-8")
        (self.root / ".env").write_text("K=%s\n" % KEY, encoding="utf-8")
        self.assertFalse(any(i["severity"] == "CRITICAL" for i in audit_git_diff(self.root)))


def route(text):
    p = subprocess.run([sys.executable, str(CAPSULE_ROOT / "scripts" / "route_request.py"), "--json", text],
                       capture_output=True, text=True, env=dict(os.environ))
    return json.loads(p.stdout)


class SecurityRouting(unittest.TestCase):
    def test_offensive_to_cell(self):
        for q in ["pen test the login endpoint", "pentest", "penetration test the api", "ssrf",
                  "prompt injection", "fuzz the parser"]:
            r = route(q)
            self.assertEqual((r["status"], r["owner"]), ("routed", "cell"), q)

    def test_credentials_to_android17(self):
        for q in ["rotate exposed credentials", "rotate exposed secrets", "leaked key in repo"]:
            r = route(q)
            self.assertEqual((r["status"], r["owner"]), ("routed", "android-17"), q)

    def test_no_security_request_to_goku_or_whis(self):
        for q in ["pen test the login endpoint", "rotate exposed credentials", "pentest", "leaked key"]:
            self.assertNotIn(route(q)["owner"], ("goku", "whis"), q)


if __name__ == "__main__":
    unittest.main()
