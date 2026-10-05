#!/usr/bin/env python3
"""Regression tests for the hardened security/attack/verify/check gates (Epic 2, slice A).

All fixtures live in temp dirs; fake secrets are assembled at runtime so the
repository itself never contains anything secret-shaped.
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import check_project
import red_team
import secret_patterns
import security_audit
import verify_project

AWS = "AK" + "IA" + "ABCDEFGHIJKLMNOP"            # 20 chars
PROJ = "sk" + "-" + "proj" + "-" + "AbCd1234_EfGh5678-IjKl9012mnop"
STRIPE = "sk" + "_live_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
GOOGLE = "AI" + "za" + "A" * 35


def write(path, text, mode="w", encoding="utf-8"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if "b" in mode:
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)


def git_init(root, commit=False):
    for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@example.com"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=str(root), check=True, stdout=subprocess.DEVNULL)
    if commit:
        subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=str(root), check=True, stdout=subprocess.DEVNULL)


def run_security(proj, dep=(0, "ok")):
    """Run security_audit.main with the dependency audit stubbed; return exit code."""
    out = io.StringIO()
    with patch.object(sys, "argv", ["security_audit.py", str(proj)]), \
            patch.object(security_audit, "run_dependency_audit", return_value=dep), \
            contextlib.redirect_stdout(out):
        try:
            security_audit.main()
        except SystemExit as exc:
            return exc.code, out.getvalue()
    return 0, out.getvalue()


def secrets(proj):
    return [f for f in security_audit.scan_for_secrets(proj) if f["type"] == "SECRET_LEAK"]


class SecretGateBypassTests(unittest.TestCase):
    def test_secret_in_build_dist_cache_dirs_flagged(self):
        for d in ("build", "dist", ".cache", ".next", "pkg/build"):
            with self.subTest(d=d), tempfile.TemporaryDirectory() as tmp:
                proj = Path(tmp).resolve()
                write(proj / d / "cfg.txt", 'k = "%s"\n' % AWS)
                self.assertEqual(len(secrets(proj)), 1)
                self.assertEqual(run_security(proj)[0], 1)

    def test_tracked_file_in_vendor_dir_scanned_in_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            git_init(proj)
            write(proj / "node_modules" / "x.js", 'k = "%s"\n' % AWS)
            subprocess.run(["git", "add", "-f", "node_modules/x.js"], cwd=str(proj), check=True)
            self.assertEqual(len(secrets(proj)), 1)

    def test_untracked_vendor_dir_skipped_in_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            git_init(proj)
            write(proj / "node_modules" / "x.js", 'k = "%s"\n' % AWS)
            self.assertEqual(secrets(proj), [])

    def test_gitignored_files_not_in_universe(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            git_init(proj)
            write(proj / ".gitignore", "local.txt\n")
            write(proj / "local.txt", AWS)
            write(proj / "seen.txt", AWS)
            self.assertEqual([f["file"] for f in secrets(proj)], ["seen.txt"])

    def test_secret_in_pdf_and_unknown_suffix_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "secrets.pdf", b"%PDF-1.4\n\x00\x01 " + AWS.encode() + b"\n", mode="wb")
            write(proj / "blob.weird", b"\xff\xfe\x00" + PROJ.encode(), mode="wb")
            self.assertEqual({f["file"] for f in secrets(proj)}, {"secrets.pdf", "blob.weird"})

    def test_utf16_files_decoded(self):
        for codec in ("utf-16", "utf-16-le", "utf-16-be"):
            with self.subTest(codec=codec), tempfile.TemporaryDirectory() as tmp:
                proj = Path(tmp).resolve()
                write(proj / "env.txt", ('API_KEY="%s"\n' % AWS).encode(codec), mode="wb")
                self.assertEqual(len(secrets(proj)), 1)
                self.assertEqual(run_security(proj)[0], 1)

    def test_sk_proj_key_with_hyphen_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", 'K = "%s"\n' % PROJ)
            found = secrets(proj)
            self.assertEqual(len(found), 1)
            self.assertNotIn(PROJ[8:], found[0]["snippet"])
            self.assertEqual(run_security(proj)[0], 1)

    def test_secrets_never_exempt_in_test_dirs_but_code_vulns_are(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "tests" / "t.py", 'K = "%s"\nx = eval(a)\n' % AWS)
            self.assertEqual(len(secrets(proj)), 1)
            self.assertEqual(security_audit.scan_code_vulnerabilities(proj), [])

    def test_test_exemption_only_top_level_conventional_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "src" / "test_helper.py", "x = eval(a)\n")
            write(proj / "src" / "tests" / "app.py", "x = eval(a)\n")
            files = {f["file"] for f in security_audit.scan_code_vulnerabilities(proj)}
            self.assertEqual(files, {os.path.join("src", "test_helper.py"), os.path.join("src", "tests", "app.py")})

    def test_symlink_outside_root_not_followed_and_reported_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            proj = Path(tmp).resolve()
            target = Path(outside) / "secret.txt"
            write(target, AWS)
            try:
                (proj / "link.txt").symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            write(proj / "ok.py", "x = 1\n")
            findings = security_audit.scan_for_secrets(proj)
            self.assertEqual([f["type"] for f in findings], ["SCAN_INCOMPLETE"])
            code, _ = run_security(proj)
            self.assertEqual(code, 2)

    def test_big_file_secret_past_chunk_boundary_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "big.log", ("x" * 99 + "\n") * 30000 + "tail " + AWS + "\n")  # ~3MB
            found = secrets(proj)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["line"], 30001)

    def test_secret_straddling_chunk_boundary_in_single_long_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            pad = secret_patterns.CHUNK_BYTES - 7
            write(proj / "min.js", "y" * pad + " " + AWS + " tail")
            self.assertEqual(len(secrets(proj)), 1)

    def test_clean_repo_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "x = 1\n")
            self.assertEqual(run_security(proj)[0], 0)


class DiffGateTests(unittest.TestCase):
    def test_shared_patterns_cover_aws_stripe_google_sk_proj(self):
        for key in (AWS, STRIPE, GOOGLE, PROJ):
            with self.subTest(key=key[:6]), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                git_init(root)
                write(root / "leak.py", 'K = "%s"\n' % key)
                issues = verify_project.audit_git_diff(root)
                self.assertEqual([i["file"] for i in issues], ["leak.py"])
                self.assertNotIn(key[8:], issues[0]["snippet"])

    def test_tracked_modification_scanned_via_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            write(root / "a.py", "x = 1\n")
            git_init(root, commit=True)
            write(root / "a.py", 'x = "%s"\n' % AWS)
            issues = verify_project.audit_git_diff(root)
            self.assertEqual(len(issues), 1)
            self.assertIn("AWS", issues[0]["description"])

    def test_removed_secret_line_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            write(root / "a.py", 'x = "%s"\n' % AWS)
            git_init(root, commit=True)
            write(root / "a.py", "x = 1\n")
            self.assertEqual(verify_project.audit_git_diff(root), [])

    def test_oversize_untracked_file_scanned_in_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            git_init(root)
            write(root / "big.txt", "x" * (verify_project.MAX_UNTRACKED_READ_BYTES + 50) + "\n" + AWS + "\n")
            issues = verify_project.audit_git_diff(root)
            self.assertEqual([i["severity"] for i in issues], ["CRITICAL"])

    def test_cap_hit_fails_closed_as_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            git_init(root)
            write(root / "big.txt", "x\n" * 5000)
            with patch.object(secret_patterns, "MAX_FILE_BYTES", 1000), \
                    patch.object(verify_project, "MAX_UNTRACKED_READ_BYTES", 256):
                issues = verify_project.audit_git_diff(root)
            self.assertEqual([i["severity"] for i in issues], ["INCOMPLETE"])

    def test_check_verdict_incomplete_not_pass_when_scan_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp).resolve()
            git_init(root)
            target = Path(outside) / "t.txt"
            write(target, "hello")
            try:
                (root / "link").symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            write(root / "capsule.json", '{"test": "%s -c pass"}' % sys.executable)
            res = check_project.run_project_checks(root)
            sec = [c for c in res["checks"] if c["name"] == "Secrets & Diff"][0]
            self.assertEqual(sec["status"], "INCOMPLETE")
            self.assertEqual(res["verdict"], "INCOMPLETE")

    def test_symlink_inside_repo_and_dangling_tolerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            git_init(root)
            write(root / "real.txt", "hi")
            try:
                (root / "in_link").symlink_to(root / "real.txt")
                (root / "dangling").symlink_to(root / "missing")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            self.assertEqual(verify_project.audit_git_diff(root), [])

    def test_utf16_untracked_file_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            git_init(root)
            write(root / "env.txt", ('K=%s\n' % AWS).encode("utf-16"), mode="wb")
            self.assertEqual(len(verify_project.audit_git_diff(root)), 1)


class ElixirTests(unittest.TestCase):
    EX = (
        'defmodule App do\n'
        '  def a(s), do: Code.eval_string(s)\n'
        '  def b(d), do: :erlang.binary_to_term(d)\n'
        '  def c(d), do: :erlang.binary_to_term(d, [:safe])\n'
        '  def d(s), do: String.to_atom(s)\n'
        '  def e, do: [ssl: [verify: :verify_none]]\n'
        '  def f(id), do: Ecto.Adapters.SQL.query(Repo, "SELECT * FROM t WHERE id = #{id}")\n'
        '  def g(c), do: System.cmd("sh", ["-c", c])\n'
        'end\n'
    )

    def test_elixir_rules_flag_each_vuln_and_safe_binary_to_term_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "mix.exs", "defmodule M do\nend\n")
            write(proj / "lib" / "app.ex", self.EX)
            by_line = {f["line"] for f in security_audit.scan_code_vulnerabilities(proj)}
            self.assertEqual(by_line, {2, 3, 5, 6, 7, 8})  # line 4 ([:safe]) is clean

    def test_exs_and_other_suffixes_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "script.exs", "Code.eval_string(x)\n")
            write(proj / "run.sh", "eval(x)\n")
            files = {f["file"] for f in security_audit.scan_code_vulnerabilities(proj)}
            self.assertEqual(files, {"script.exs", "run.sh"})

    def test_red_team_scans_elixir(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "lib" / "a.ex", "def a, do: [ssl: [verify: :verify_none]]\n")
            audit = red_team.run_red_team_audit(proj)
            self.assertEqual(audit["verdict"], "VULNERABLE")
            self.assertEqual(audit["summary"]["files_scanned"], 1)

    def test_mix_exs_unaudited_when_mix_missing_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "mix.exs", "defmodule M do\nend\n")
            with patch("security_audit.shutil.which", return_value=None):
                code, out = security_audit.run_dependency_audit(proj)
            self.assertEqual(code, 2)
            self.assertIn("mix", out)

    def test_mix_hex_audit_runs_with_argv_list_and_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "mix.exs", "defmodule M do\nend\n")
            calls = []

            def fake_run(command, **kw):
                calls.append((command, kw))
                return subprocess.CompletedProcess(command, 0, stdout="No retired packages found", stderr="")

            with patch("security_audit.shutil.which", return_value="/usr/local/bin/mix"), \
                    patch("security_audit.subprocess.run", side_effect=fake_run):
                code, _ = security_audit.run_dependency_audit(proj)
            self.assertEqual(code, 0)
            self.assertEqual(calls[0][0], ["mix", "hex.audit"])
            self.assertIn("timeout", calls[0][1])
            self.assertNotIn("shell", calls[0][1])

    def test_mix_found_inside_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "mix.exs", "defmodule M do\nend\n")
            write(proj / "bin" / "mix", "#!/bin/sh\nexit 0\n")
            with patch("security_audit.shutil.which", return_value=str(proj / "bin" / "mix")):
                code, out = security_audit.run_dependency_audit(proj)
            self.assertEqual(code, 2)

    def test_unaudited_manifests_are_incomplete_never_clean(self):
        for name in ("go.mod", "Gemfile", "poetry.lock", "yarn.lock", "composer.json", "pom.xml"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                proj = Path(tmp).resolve()
                write(proj / name, "x\n")
                code, out = security_audit.run_dependency_audit(proj)
                self.assertEqual(code, 2)
                self.assertIn("INCOMPLETE", out)
                self.assertEqual(run_security(proj, dep=(code, out))[0], 2)

    def test_failed_audit_outranks_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "package.json", "{}")
            write(proj / "go.mod", "module x\n")
            with patch("security_audit.shutil.which", return_value="npm"), patch(
                    "security_audit.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 1, stdout="vulns", stderr="")):
                code, _ = security_audit.run_dependency_audit(proj)
            self.assertEqual(code, 1)

    def test_no_manifest_is_still_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(security_audit.run_dependency_audit(Path(tmp))[0], 0)


class ReDoSTests(unittest.TestCase):
    BUDGET = 5.0

    def timed(self, fn):
        t = time.monotonic()
        result = fn()
        self.assertLess(time.monotonic() - t, self.BUDGET)
        return result

    def attack(self, text, name="x.py"):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / name, text)
            return self.timed(lambda: red_team.run_red_team_audit(proj))

    def test_messages_fstring_repeated(self):
        self.attack('messages = f"' * 3500 + "\n")

    def test_invoke_fstring_repeated(self):
        self.attack('invoke(f"' * 2000 + "\n")

    def test_redos_detector_pathological_line(self):
        self.attack('"(a+(a+' * 9000 + "\n")
        self.attack('"(' * 30000 + "\n")

    def test_prompt_pattern_fstring_soup(self):
        self.attack('prompt = f"f"' * 4000 + "\n")

    def test_security_audit_select_where_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "q.py", 'q = f"' + "SELECT * WHERE " * 2000 + "\n")
            self.timed(lambda: security_audit.scan_code_vulnerabilities(proj))

    def test_security_audit_percent_format_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "q.py", '"' + "SELECT x WHERE " * 3000 + "\n")
            self.timed(lambda: security_audit.scan_code_vulnerabilities(proj))

    def test_elixir_rules_adversarial(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.ex", "Ecto.Adapters.SQL.query(" * 3000 + "\n")
            self.timed(lambda: security_audit.scan_code_vulnerabilities(proj))

    def test_detection_still_works_on_normal_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", 'import re\nr = re.compile("(a+)+")\nmessages = [f"hi {user_input}"]\n')
            cats = {f["category"] for f in red_team.run_red_team_audit(proj)["findings"]}
            self.assertIn("REDOS_DOS", cats)
            self.assertIn("PROMPT_INJECTION", cats)
            write(proj / "q.py", 'q = f"SELECT * FROM t WHERE id = {i}"\n')
            self.assertTrue(security_audit.scan_code_vulnerabilities(proj))

    def test_time_budget_exhaustion_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "x = 1\n" * 50)
            with patch.object(secret_patterns, "FILE_TIME_BUDGET", -1.0):
                audit = red_team.run_red_team_audit(proj)
                self.assertEqual(audit["verdict"], "INCOMPLETE")
                found = security_audit.scan_code_vulnerabilities(proj)
            self.assertEqual([f["type"] for f in found], ["SCAN_INCOMPLETE"])


class AttackZeroFilesTests(unittest.TestCase):
    def test_zero_files_scanned_is_incomplete_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "README.md", "hello\n")
            audit = red_team.run_red_team_audit(proj)
            self.assertEqual(audit["verdict"], "INCOMPLETE")
            self.assertEqual(audit["summary"]["files_scanned"], 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(red_team.main([str(proj)]), 2)
                self.assertEqual(red_team.main([str(proj), "--strict"]), 2)

    def test_empty_dir_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(red_team.run_red_team_audit(Path(tmp))["verdict"], "INCOMPLETE")

    def test_normal_repo_reports_nonzero_files_and_resilient(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "x = 1\n")
            write(proj / "b.ts", "export const y = 2;\n")
            audit = red_team.run_red_team_audit(proj)
            self.assertEqual(audit["summary"]["files_scanned"], 2)
            self.assertEqual(audit["verdict"], "RESILIENT")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(red_team.main([str(proj)]), 0)
            self.assertIn("Files scanned: 2", out.getvalue())

    def test_vulnerable_outranks_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "requests.get(u, verify=False)\n")
            self.assertEqual(red_team.run_red_team_audit(proj)["verdict"], "VULNERABLE")

    def test_red_team_build_dir_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "build" / "a.py", "requests.get(u, verify=False)\n")
            self.assertEqual(red_team.run_red_team_audit(proj)["verdict"], "VULNERABLE")


class ProjectCodeExecutionTests(unittest.TestCase):
    def test_project_venv_not_used_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            py = root / ".venv" / "bin" / "python"
            write(py, "#!/bin/sh\n")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CAPSULE_USE_PROJECT_VENV", None)
                self.assertEqual(verify_project.project_python(root), sys.executable)
            with patch.dict(os.environ, {"CAPSULE_USE_PROJECT_VENV": "1"}):
                self.assertEqual(verify_project.project_python(root), str(py))

    def test_config_drift_warns_not_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            write(root / "capsule.json", '{"test": "%s -c pass"}' % sys.executable)
            git_init(root, commit=True)
            self.assertEqual(verify_project.config_drift_warnings(root), [])
            write(root / "capsule.json", '{"test": "%s -c pass # changed"}' % sys.executable)
            self.assertEqual(len(verify_project.config_drift_warnings(root)), 1)
            res = check_project.run_project_checks(root)
            warn = [c for c in res["checks"] if c["name"] == "Config Integrity"]
            self.assertEqual(warn[0]["status"], "WARNING")
            self.assertEqual(res["verdict"], "PASS")

    def test_untracked_config_in_git_repo_warns_and_non_git_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            write(root / "capsule.json", "{}")
            self.assertEqual(verify_project.config_drift_warnings(root), [])  # not a repo
            git_init(root)
            self.assertEqual(len(verify_project.config_drift_warnings(root)), 1)

    def test_help_text_carries_notice(self):
        for script in ("check_project.py", "verify_project.py"):
            res = subprocess.run([sys.executable, str(CAPSULE_ROOT / "scripts" / script), "--help"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("EXECUTE code", res.stdout)
            self.assertIn("CAPSULE_USE_PROJECT_VENV", res.stdout)


class PipAuditTests(unittest.TestCase):
    def test_requirements_preferred_with_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "requirements.txt", "a==1\n")
            write(proj / "pyproject.toml", "[project]\nname='x'\n")
            calls = []

            def fake_run(command, **kw):
                calls.append((command, kw))
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            with patch("security_audit.shutil.which", return_value="/usr/bin/pip-audit"), \
                    patch("security_audit.subprocess.run", side_effect=fake_run):
                self.assertEqual(security_audit.run_dependency_audit(proj)[0], 0)
            self.assertEqual(calls[0][0], ["pip-audit", "-r", str(proj / "requirements.txt"),
                                           "--no-deps", "--disable-pip"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1]["timeout"], 60)

    def test_pipfile_only_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "Pipfile", "[packages]\n")
            self.assertEqual(security_audit.run_dependency_audit(proj)[0], 2)


class ExtendedSecretCoverageTests(unittest.TestCase):
    """Fixtures are assembled at runtime so the repo holds nothing secret-shaped."""

    def descs(self, text):
        return [d for _, _, d in secret_patterns.find_secrets(text)]

    def diff_hits(self, text):
        diff = "+" + text + "\n"
        return [d for pat, d in secret_patterns.DIFF_SECRET_PATTERNS if pat.search(diff)]

    def cases(self):
        b36 = "aB3dE6gH9jK2mN5pQ8sT1vW4yZ7bC0dF3hJ6"
        return [
            ("SendGrid", "S" + "G." + "A" * 22 + "." + "b" * 22),
            ("GitHub OAuth", "g" + "ho_" + b36),
            ("GitHub OAuth", "g" + "hs_" + b36),
            ("GitHub OAuth", "g" + "hu_" + b36),
            ("GitHub OAuth", "g" + "hr_" + b36),
            ("GitLab", "gl" + "pat-" + "Ab1_" * 6),
            ("npm", "np" + "m_" + b36),
            ("Stripe Webhook", "wh" + "sec_" + "a1B2c3D4e5F6g7H8i9J0k1L2"),
            ("Stripe Secret Test", "sk" + "_test_" + "a1B2c3D4e5F6g7H8i9J0k1L2"),
            ("Stripe Restricted", "rk" + "_live_" + "a1B2c3D4e5F6g7H8i9J0k1L2"),
            ("Google OAuth", "ya" + "29." + "a0Ab_" * 6),
            ("Twilio", "S" + "K" + "0123456789abcdef" * 2),
            ("Slack", "xo" + "xb-" + "1234567890abcdef"),
            ("AWS Secret", "aws_secret_" + "access_key = \"" + "aB3/" * 10 + "\""),
            ("Credential Assignment", "db_pass" + "word = \"" + "Zq8rT2vLp9Xw" + "\""),
            ("Credential Assignment", "JWT_" + "SECRET: '" + "k3Jd8sL0pQw9zXc" + "'"),
            ("Credential Assignment", "my_api_" + "key=\"" + "Qw3rTy7uIo9pAs" + "\""),
        ]

    def test_each_pattern_detected_in_files_and_diff(self):
        for label, secret in self.cases():
            with self.subTest(label=label):
                text = "x = 1\n" + secret + "\n"
                self.assertTrue(any(label.lower() in d.lower() for d in self.descs(text)),
                                (label, self.descs(text)))
                self.assertTrue(self.diff_hits(secret), label)

    def test_placeholders_not_flagged(self):
        quiet = [
            'password = "changeme-please-now"',
            'api_key = "example_key_value_123"',
            'secret = "xxxxxxxxxxxxxxxx"',
            'token = "your_token_goes_here"',
            'password = "<your-password-here>"',
            'secret = "${SECRET_FROM_ENV_VAR}"',
            'password = os.environ["DB_PASSWORD_VALUE"]',
            "token = os.getenv('GITHUB_TOKEN_VALUE')",
            'password = "short"',
            'password = "has some spaces inside"',
            "aws_secret_access_key = <set me>",
        ]
        for line in quiet:
            with self.subTest(line=line):
                self.assertEqual(self.descs(line), [], line)
                self.assertEqual(self.diff_hits(line), [], line)

    def test_new_patterns_are_fast_on_hostile_input(self):
        for hostile in ("password" + "=" * 5000, "secret" + "_" * 20000 + "=\"" + "a" * 20000,
                        "aws_secret_access_key=" + "A" * 50000, "SG." + "a" * 50000,
                        "token = '" + "a" * 100000):
            start = time.monotonic()
            secret_patterns.find_secrets(hostile)
            for pat, _ in secret_patterns.DIFF_SECRET_PATTERNS:
                pat.search("+" + hostile)
            self.assertLess(time.monotonic() - start, 5.0)


if __name__ == "__main__":
    unittest.main()
