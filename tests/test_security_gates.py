#!/usr/bin/env python3
"""Regression tests for security_audit.py and red_team.py scanning gates.

Fake secrets are built at runtime so this file never trips the repo scanner.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import red_team
import security_audit


def fake_key():
    return "sk" + "-" + "A1b2C3d4E5" * 3


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_main(argv, dep_result):
    out = io.StringIO()
    with patch.object(sys, "argv", ["security_audit.py"] + argv), \
            patch.object(security_audit, "run_dependency_audit", return_value=dep_result), \
            contextlib.redirect_stdout(out):
        try:
            security_audit.main()
        except SystemExit as exc:
            return exc.code, out.getvalue()
    return 0, out.getvalue()


class ParentDirIgnoreTests(unittest.TestCase):
    PARENTS = ["build", "dist", "test", "tests", "venv", ".cache", ".next"]

    def test_secret_under_ignored_named_parent_is_flagged(self):
        for parent in self.PARENTS:
            with self.subTest(parent=parent), tempfile.TemporaryDirectory() as tmp:
                proj = Path(tmp).resolve() / parent / "proj"
                write(proj / "app.py", 'KEY = "%s"\n' % fake_key())
                self.assertEqual(len(security_audit.scan_for_secrets(proj)), 1)

    def test_code_vuln_under_test_named_parent_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve() / "tests" / "proj"
            write(proj / "app.py", "x = eval(user_input)\n")
            self.assertTrue(security_audit.scan_code_vulnerabilities(proj))

    def test_ignored_dir_inside_project_still_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "node_modules" / "x.py", 'K = "%s"\n' % fake_key())
            self.assertEqual(security_audit.scan_for_secrets(proj), [])

    def test_red_team_flags_under_ignored_named_parent(self):
        for parent in self.PARENTS:
            with self.subTest(parent=parent), tempfile.TemporaryDirectory() as tmp:
                proj = Path(tmp).resolve() / parent / "proj"
                write(proj / "app.py", "import requests\nrequests.get(url, verify=False)\n")
                audit = red_team.run_red_team_audit(proj)
                self.assertEqual(audit["verdict"], "VULNERABLE")

    def test_red_team_main_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve() / "build" / "proj"
            write(proj / "app.py", "import requests\nrequests.get(u, verify=False)\n")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(red_team.main([str(proj)]), 1)

    def test_red_team_exemption_scoped_to_own_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "red_team.py", "import requests\nrequests.get(u, verify=False)\n")
            self.assertEqual(red_team.run_red_team_audit(proj)["verdict"], "VULNERABLE")
        self.assertEqual(
            red_team.audit_file_for_attack_vectors(
                CAPSULE_ROOT / "scripts" / "red_team.py", CAPSULE_ROOT), [])


class SecretReportingTests(unittest.TestCase):
    def test_snippet_is_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            key = fake_key()
            write(proj / "a.py", 'KEY = "%s"\n' % key)
            findings = security_audit.scan_for_secrets(proj)
            self.assertEqual(len(findings), 1)
            self.assertNotIn(key, findings[0]["snippet"])
            self.assertNotIn(key[8:], findings[0]["snippet"])
            self.assertIn(key[:4] + "***", findings[0]["snippet"])

    def test_word_boundary_avoids_embedded_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            tail = "A1b2C3d4E5" * 3
            write(proj / "a.py", 'x = "di%s"\ny = "ta%s"\n' % ("sk-" + tail, "sk-" + tail))
            self.assertEqual(security_audit.scan_for_secrets(proj), [])


class ExitCodeTests(unittest.TestCase):
    def test_incomplete_exit_code_is_2_in_json_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            for argv in ([tmp, "--json"], [tmp]):
                code, _ = run_main(argv, (2, "INCOMPLETE"))
                self.assertEqual(code, 2, argv)

    def test_json_fail_still_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / "a.py", 'K = "%s"\n' % fake_key())
            code, out = run_main([tmp, "--json"], (0, "ok"))
            self.assertEqual(code, 1)
            self.assertNotIn(fake_key(), out)


if __name__ == "__main__":
    unittest.main()
