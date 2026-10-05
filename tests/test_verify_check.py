#!/usr/bin/env python3
"""Regression tests for check/verify hardening (config parsing, skip flags, git audit, badges)."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import _config
import verify_project
from check_project import run_project_checks, format_check_report, detect_lint_command, detect_typecheck_command
from verify_project import NotAGitRepository, audit_git_diff, detect_test_command, load_project_config

PASS = "%s -c 'import sys; sys.exit(0)'" % sys.executable


def git_init(root):
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)


def check(res, name):
    return next(c for c in res["checks"] if c["name"] == name)


class TestTomlConfig(unittest.TestCase):
    SAMPLE = (
        '[tool.capsule]\n'
        'test = "echo hi"  # trailing comment\n'
        'grill = false\n'
        'lint = "echo \'#notcomment\'"\n'
    )

    def _check_parsed(self, cfg):
        self.assertEqual(cfg["test"], "echo hi")
        self.assertIs(cfg["grill"], False)
        self.assertEqual(cfg["lint"], "echo '#notcomment'")

    def test_fallback_parser(self):
        self._check_parsed(_config.parse_toml_fallback(self.SAMPLE)["tool"]["capsule"])

    def test_load_project_config_pyproject(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pyproject.toml").write_text(self.SAMPLE, encoding="utf-8")
            self._check_parsed(load_project_config(Path(d)))

    def test_load_project_config_without_tomllib(self):
        with tempfile.TemporaryDirectory() as d, patch.object(_config, "_tomllib", None):
            (Path(d) / "pyproject.toml").write_text(self.SAMPLE, encoding="utf-8")
            self._check_parsed(load_project_config(Path(d)))

    def test_grill_false_does_not_run_grill(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pyproject.toml").write_text(
                '[tool.capsule]\ntest = "true"\ngrill = false\n', encoding="utf-8")
            res = run_project_checks(root, skip_secrets=True)
            self.assertFalse([c for c in res["checks"] if c["name"] == "Beerus Inquisition"])

    def test_bad_quoting_reports_configuration_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "capsule.json").write_text(json.dumps({"test": "echo 'unterminated"}), encoding="utf-8")
            res = run_project_checks(root, skip_secrets=True)
            self.assertEqual(res["verdict"], "FAIL")
            self.assertEqual(check(res, "Configuration")["status"], "FAILED")

    def test_non_string_command_reports_configuration_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "capsule.json").write_text(json.dumps({"test": 5, "lint": True}), encoding="utf-8")
            res = run_project_checks(root, skip_secrets=True)
            self.assertEqual(res["verdict"], "FAIL")
            self.assertTrue([c for c in res["checks"] if c["name"] == "Configuration"])

    def test_detect_test_command_raises_valueerror_on_bad_config(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "capsule.json").write_text(json.dumps({"test": "a 'b"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                detect_test_command(Path(d))


class TestSkipAndTimeout(unittest.TestCase):
    def test_skip_tests_skips_tests_not_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_init(root)
            (root / "capsule.json").write_text(json.dumps({"test": "false"}), encoding="utf-8")
            res = run_project_checks(root, skip_tests=True)
            self.assertEqual(check(res, "Tests")["status"], "SKIPPED")
            self.assertEqual(check(res, "Secrets & Diff")["status"], "PASSED")
            self.assertEqual(res["verdict"], "PASS")

    def test_timeout_is_honored(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cmd = "%s -c 'import time; time.sleep(5)'" % sys.executable
            res = run_project_checks(root, test_cmd_override=cmd, skip_secrets=True, timeout=1)
            t = check(res, "Tests")
            self.assertEqual(t["status"], "FAILED")
            self.assertIn("Timed out after 1s", t["output"])

    def test_verify_cli_skip_tests_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_init(root)
            (root / "capsule.json").write_text(json.dumps({"test": "false"}), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(CAPSULE_ROOT / "scripts" / "verify_project.py"), str(root), "--skip-tests", "--json"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout)["verdict"], "PASS")


class TestGitAudit(unittest.TestCase):
    def test_non_git_dir_is_skipped_with_hint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(NotAGitRepository):
                audit_git_diff(root)
            res = run_project_checks(root, test_cmd_override=PASS)
            sec = check(res, "Secrets & Diff")
            self.assertEqual(sec["status"], "SKIPPED")
            self.assertIn("--skip-secrets", sec["summary"])
            self.assertEqual(res["verdict"], "PASS")

    def test_issue_output_includes_filename(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_init(root)
            (root / "leak.py").write_text("v = 'sk-%s'\n" % ("a" * 24), encoding="utf-8")
            issues = audit_git_diff(root)
            self.assertEqual(issues[0]["file"], "leak.py")
            res = run_project_checks(root, test_cmd_override=PASS)
            self.assertIn("- leak.py:", check(res, "Secrets & Diff")["output"])

    def test_broken_symlink_and_oversize_tolerated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_init(root)
            try:
                (root / "dangling").symlink_to(root / "missing")
            except (OSError, NotImplementedError):
                pass
            # Intentional behavior change (gate hardening): oversize files are scanned in
            # overlapping chunks, so a secret past the old 1MB cap is now found.
            (root / "big.txt").write_text(
                "x" * (verify_project.MAX_UNTRACKED_READ_BYTES + 10) + "\nsk-" + "a" * 24, encoding="utf-8")
            issues = audit_git_diff(root)
            self.assertEqual([i["file"] for i in issues], ["big.txt"])

    def test_rst_underline_not_flagged_but_real_conflict_is(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_init(root)
            (root / "doc.rst").write_text("Title\n=======\n\nBody\n", encoding="utf-8")
            (root / "indented.md").write_text("Head\n  =======\n", encoding="utf-8")
            self.assertEqual(audit_git_diff(root), [])
            (root / "conflict.txt").write_text("<<<<<<< HEAD\na\n=======\nb\n>>>>>>> other\n", encoding="utf-8")
            issues = audit_git_diff(root)
            self.assertEqual({i["file"] for i in issues}, {"conflict.txt"})
            self.assertEqual(len(issues), 3)

    def test_check_does_not_create_capsule_dir(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_init(root)
            run_project_checks(root, test_cmd_override=PASS)
            self.assertFalse((root / ".capsule").exists())


class TestBadgesAndCrashes(unittest.TestCase):
    def test_warning_badge_in_check_report(self):
        report = {"target_name": "x", "verdict": "PASS", "checks": [
            {"name": "Agent Alignment", "status": "WARNING", "summary": "w", "output": ""}]}
        self.assertIn("[WARN]", format_check_report(report))

    def test_warning_badge_in_verify_cli(self):
        with tempfile.TemporaryDirectory() as d:
            fake = {"verdict": "PASS", "checks": [
                {"name": "Beerus Inquisition", "status": "WARNING", "summary": "w", "output": ""}]}
            import check_project as cp
            with patch("sys.argv", ["verify", d]), \
                    patch.object(cp, "run_project_checks", return_value=fake):
                buf = io.StringIO()
                with redirect_stdout(buf), self.assertRaises(SystemExit):
                    verify_project.main()
            self.assertIn("[WARN]", buf.getvalue())

    def test_grill_crash_is_warning_not_skipped(self):
        import grill_code
        with tempfile.TemporaryDirectory() as d:
            with patch.object(grill_code, "run_grill_audit", side_effect=RuntimeError("boom")):
                res = run_project_checks(Path(d), test_cmd_override=PASS, skip_secrets=True, check_grill=True)
            c = check(res, "Beerus Inquisition")
            self.assertEqual(c["status"], "WARNING")
            self.assertIn("boom", c["summary"])


class TestDetection(unittest.TestCase):
    def test_ruff_via_pyproject(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
            with patch("shutil.which", side_effect=lambda n: "/bin/" + n if n == "ruff" else None):
                self.assertEqual(detect_lint_command(root), ["/bin/ruff", "check", "."])

    def test_flake8_and_mypy_via_setup_cfg(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "setup.cfg").write_text("[flake8]\nmax-line-length=100\n[mypy]\nstrict=True\n", encoding="utf-8")
            with patch("shutil.which", side_effect=lambda n: "/bin/" + n):
                self.assertEqual(detect_lint_command(root)[0], "/bin/flake8")
                self.assertEqual(detect_typecheck_command(root)[0], "/bin/mypy")

    def test_mypy_via_pyproject(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n", encoding="utf-8")
            with patch("shutil.which", side_effect=lambda n: "/bin/" + n):
                self.assertEqual(detect_typecheck_command(root), ["/bin/mypy", "."])

    def test_npm_resolved_via_which(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}), encoding="utf-8")
            with patch("shutil.which", side_effect=lambda n: "C:\\npm.cmd" if n == "npm" else None):
                self.assertEqual(detect_test_command(root), ["C:\\npm.cmd", "test"])

    def test_pytest_probed_via_interpreter(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            with patch.object(verify_project, "_has_pytest", return_value=True):
                self.assertEqual(detect_test_command(root), [sys.executable, "-m", "pytest", "-v"])
            with patch.object(verify_project, "_has_pytest", return_value=False):
                self.assertEqual(detect_test_command(root)[:3], [sys.executable, "-m", "unittest"])


if __name__ == "__main__":
    unittest.main()
