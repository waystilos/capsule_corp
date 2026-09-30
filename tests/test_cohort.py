#!/usr/bin/env python3
"""
Unit Test Suite for Capsule Corp Cohort Infrastructure
Verifies registry schema, Dr. Gero's auditor, Trunks' sentinel, and bot scaffolding.
"""

import unittest
import os
from pathlib import Path
import subprocess
import yaml
import sys
import tempfile
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))
sys.path.insert(0, str(CAPSULE_ROOT / "src"))

from init_project import ALL_TOOLS, init_project
from scaffold_bot import generate_bot_markdown, update_registry_yaml, validate_bot_name
from audit_transcripts import analyze_transcript
from security_audit import scan_for_secrets
from security_audit import run_dependency_audit
from verify_project import SUSPICIOUS_DIFF_PATTERNS, audit_git_diff
from route_request import route_request
from doctor import run_doctor
from capsule.cli import _installed_resource_candidates, cmd_list


class TestCapsuleCorpRegistry(unittest.TestCase):
    def test_registry_valid_yaml(self):
        reg_path = CAPSULE_ROOT / "registry.yaml"
        self.assertTrue(reg_path.exists(), "registry.yaml must exist")
        data = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
        self.assertIn("bots", data)
        self.assertGreaterEqual(len(data["bots"]), 5)

        for bot_id, details in data["bots"].items():
            self.assertIn("name", details, f"{bot_id} missing name")
            self.assertIn("role", details, f"{bot_id} missing role")
            self.assertIn("job_to_be_done", details, f"{bot_id} missing job_to_be_done")
            self.assertIn("allowed_tools", details, f"{bot_id} missing allowed_tools")
            self.assertIn("verification_gate", details, f"{bot_id} missing verification_gate")

    def test_routing_uses_specialist_and_whis_for_ambiguity(self):
        ux = route_request("design an accessible onboarding flow with useful error states")
        self.assertEqual(ux["owner"], "videl")
        self.assertEqual(ux["status"], "routed")

        ambiguous = route_request("help me with this project")
        self.assertEqual(ambiguous["owner"], "whis")
        self.assertEqual(ambiguous["status"], "needs_clarification")

    def test_user_install_resource_path_is_checked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            userbase = Path(temp_dir) / "Roaming" / "Python"
            expected = userbase / "share" / "capsule-corp"
            expected.mkdir(parents=True)
            (expected / "registry.yaml").write_text("bots: {}\n", encoding="utf-8")
            with patch("capsule.cli.sysconfig.get_path") as get_path, patch(
                "capsule.cli.sysconfig.get_config_var", return_value=str(userbase)
            ):
                get_path.side_effect = lambda key: str(Path(temp_dir) / ("system" if key == "data" else "site-packages"))
                candidates = _installed_resource_candidates()
            self.assertIn(expected.resolve(), candidates)

    def test_malformed_registry_does_not_raise_traceback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "registry.yaml").write_text("bots: [\n", encoding="utf-8")
            with patch("capsule.cli.resource_root", return_value=root):
                self.assertEqual(cmd_list(), 1)


class TestDrGeroScaffolder(unittest.TestCase):
    def test_generate_bot_markdown(self):
        md = generate_bot_markdown(
            name="test-bot",
            alias="Test Bot",
            role="Testing Specialist",
            description="A test bot",
            jtbd="Run automated checks",
            boundaries="- Do not write production code.",
            tools=["run_command", "view_file"],
            verification="exit code 0"
        )
        self.assertIn("# Test Bot: Testing Specialist", md)
        self.assertIn("## 1. Job To Be Done (JTBD)", md)
        self.assertIn("## 2. Allowed Tools", md)
        self.assertIn("## 3. Execution Directives", md)
        self.assertIn("## 4. Verification Gate", md)

    def test_bot_names_are_safe_and_registry_values_are_escaped(self):
        with self.assertRaises(ValueError):
            validate_bot_name("../../outside")

        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "registry.yaml"
            registry.write_text("bots:\n", encoding="utf-8")
            update_registry_yaml(
                registry_path=registry,
                name="safe-bot",
                alias='Alias: "quoted"',
                role="Testing",
                jtbd="Run checks",
                tools=["run_command"],
                verification="exit code 0",
            )
            data = yaml.safe_load(registry.read_text(encoding="utf-8"))
            self.assertEqual(data["bots"]["safe_bot"]["alias"], 'Alias: "quoted"')


class TestDrGeroAuditor(unittest.TestCase):
    def test_analyze_transcript_detects_steering(self):
        mock_steps = [
            {"type": "PLANNER_RESPONSE", "source": "MODEL", "tool_calls": [{"name": "view_file"}]},
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "No, that's wrong! Fix the test."},
            {"type": "PLANNER_RESPONSE", "source": "MODEL", "tool_calls": [{"name": "run_command"}]},
            {"type": "TOOL_RESULT", "status": "ERROR", "content": "Command failed"}
        ]
        result = analyze_transcript(mock_steps)
        self.assertEqual(len(result["human_corrections"]), 1)
        self.assertEqual(len(result["tool_failures"]), 1)
        self.assertEqual(result["tool_usage"]["view_file"], 1)
        self.assertEqual(result["tool_usage"]["run_command"], 1)


class TestTrunksSentinel(unittest.TestCase):
    def test_diff_detects_merge_conflicts_and_secrets(self):
        dummy_key = "sk-" + "testdummykey" * 3
        dummy_ant = "sk-" + "ant-api03-" + "1" * 85
        dirty_diff = f"""
+<<<<<<< HEAD
+print("conflict")
+=======
+print("resolved")
+>>>>>>> branch
+const apiKey = "{dummy_key}";
+const antKey = "{dummy_ant}";
"""
        detected_issues = []
        for pattern, desc in SUSPICIOUS_DIFF_PATTERNS:
            if pattern.search(dirty_diff):
                detected_issues.append(desc)

        self.assertIn("Git merge conflict marker (start)", detected_issues)
        self.assertIn("Git merge conflict marker (mid)", detected_issues)
        self.assertIn("Git merge conflict marker (end)", detected_issues)
        self.assertIn("Exposed OpenAI / Service Secret Key", detected_issues)
        self.assertIn("Exposed Anthropic API Key", detected_issues)

    def test_doctor_inspects_environment_health(self):
        report = run_doctor(CAPSULE_ROOT)
        self.assertIn(report["status"], ("HEALTHY", "WARN"))
        self.assertGreaterEqual(len(report["categories"]), 3)

    def test_cli_propagates_failed_child_exit_code(self):
        result = subprocess.run(
            [sys.executable, str(CAPSULE_ROOT / "bin" / "capsule"), "verify", "--test-cmd", "false"],
            cwd=CAPSULE_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 1)

    def test_cli_output_is_utf8_when_stdout_is_redirected(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "cp1252"
        result = subprocess.run(
            [sys.executable, str(CAPSULE_ROOT / "bin" / "capsule"), "list"],
            cwd=CAPSULE_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        output = result.stdout.decode("utf-8")
        self.assertIn("🚀 CAPSULE CORP AGENT COHORT ROSTER", output)

    def test_verifier_scans_untracked_files_in_fresh_repositories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            secret = "sk-" + "b" * 24
            (root / "new_config.py").write_text(f"value = '{secret}'\n", encoding="utf-8")

            issues = audit_git_diff(root)

            self.assertTrue(any("OpenAI / Service Secret Key" in issue["description"] for issue in issues))


class TestProjectSafety(unittest.TestCase):
    def test_security_scan_does_not_skip_test_named_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            secret = "sk-" + "a" * 24
            (root / "contest.py").write_text(f"value = '{secret}'\n", encoding="utf-8")
            (root / "test_fixture.py").write_text(f"value = '{secret}'\n", encoding="utf-8")

            findings = scan_for_secrets(root)
            files = {finding["file"] for finding in findings}
            self.assertEqual(files, {"contest.py", "test_fixture.py"})

    def test_initializer_preserves_existing_directives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            github_dir = root / ".github"
            github_dir.mkdir()
            existing = "project-specific instructions\n"
            (github_dir / "copilot-instructions.md").write_text(existing, encoding="utf-8")

            init_project(root)

            self.assertEqual(
                (github_dir / "copilot-instructions.md").read_text(encoding="utf-8"),
                existing,
            )

    def test_initializer_defaults_to_only_copilot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            init_project(root)

            self.assertTrue((root / ".github" / "copilot-instructions.md").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".cursorrules").exists())
            self.assertFalse((root / ".windsurfrules").exists())
            self.assertFalse((root / "GEMINI.md").exists())
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertFalse((root / ".claude").exists())

    def test_initializer_installs_only_explicit_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            init_project(root, tools={"copilot", "cursor"})

            self.assertTrue((root / ".github" / "copilot-instructions.md").exists())
            self.assertTrue((root / ".cursorrules").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".windsurfrules").exists())
            self.assertFalse((root / "GEMINI.md").exists())
            self.assertFalse((root / "CLAUDE.md").exists())

    def test_initializer_installs_gemini_and_agy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            init_project(root, tools={"gemini"})
            self.assertTrue((root / "GEMINI.md").exists())
            self.assertIn("Capsule Corp Directives", (root / "GEMINI.md").read_text(encoding="utf-8"))
            self.assertFalse((root / "AGENTS.md").exists())

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            init_project(root, tools={"agy"})
            self.assertTrue((root / "GEMINI.md").exists())
            self.assertIn("Capsule Corp Directives", (root / "GEMINI.md").read_text(encoding="utf-8"))

    def test_initializer_installs_claude_and_claudecode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            init_project(root, tools={"claude"})
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertTrue((root / ".claude" / "settings.json").exists())
            self.assertIn("Capsule Corp Directives for Claude Code", (root / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn("capsule", (root / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertFalse((root / "AGENTS.md").exists())

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            init_project(root, tools={"claudecode"})
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertTrue((root / ".claude" / "settings.json").exists())
            self.assertIn("Capsule Corp Directives for Claude Code", (root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_initializer_all_tools_includes_gemini_and_claude(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            init_project(root, tools=ALL_TOOLS)
            self.assertTrue((root / ".github" / "copilot-instructions.md").exists())
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertTrue((root / ".cursorrules").exists())
            self.assertTrue((root / ".windsurfrules").exists())
            self.assertTrue((root / "GEMINI.md").exists())
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertTrue((root / ".claude" / "settings.json").exists())

    def test_initializer_preserves_existing_gemini(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = "custom gemini rules\n"
            (root / "GEMINI.md").write_text(existing, encoding="utf-8")

            init_project(root, tools={"gemini"})
            self.assertEqual((root / "GEMINI.md").read_text(encoding="utf-8"), existing)

            init_project(root, force=True, tools={"gemini"})
            self.assertIn("Capsule Corp Directives", (root / "GEMINI.md").read_text(encoding="utf-8"))

    def test_initializer_preserves_existing_claude(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing_claude = "custom claude rules\n"
            (root / "CLAUDE.md").write_text(existing_claude, encoding="utf-8")
            claude_dir = root / ".claude"
            claude_dir.mkdir()
            existing_settings = '{"custom": true}\n'
            (claude_dir / "settings.json").write_text(existing_settings, encoding="utf-8")

            init_project(root, tools={"claude"})
            self.assertEqual((root / "CLAUDE.md").read_text(encoding="utf-8"), existing_claude)
            self.assertEqual((claude_dir / "settings.json").read_text(encoding="utf-8"), existing_settings)

            init_project(root, force=True, tools={"claude"})
            self.assertIn("Capsule Corp Directives for Claude Code", (root / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn("Bash(capsule *)", (claude_dir / "settings.json").read_text(encoding="utf-8"))

    def test_initializer_includes_self_provisioning_directive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_project(root, tools={"copilot", "agents", "claude", "gemini"})
            self.assertIn("Agent Self-Provisioning", (root / ".github" / "copilot-instructions.md").read_text(encoding="utf-8"))
            self.assertIn("Agent Self-Provisioning", (root / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("Agent Self-Provisioning", (root / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn("Agent Self-Provisioning", (root / "GEMINI.md").read_text(encoding="utf-8"))

    def test_initializer_auto_detects_claude_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(os.environ, {"CLAUDE_CODE": "1"}):
                init_project(root, tools={"auto"})
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertTrue((root / ".claude" / "settings.json").exists())

    def test_initializer_auto_detects_gemini_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(os.environ, {"GEMINI_CLI": "1"}):
                init_project(root, tools={"auto"})
            self.assertTrue((root / "GEMINI.md").exists())


class TestAndroid17Security(unittest.TestCase):
    def test_security_patterns_detect_eval_and_injection(self):
        from security_audit import CODE_VULN_PATTERNS
        dirty_code = """
        eval(user_input)
        f"SELECT * FROM users WHERE id = {user_id}"
        """
        detected = []
        for pattern, desc in CODE_VULN_PATTERNS:
            if pattern.search(dirty_code):
                detected.append(desc)
        self.assertIn("Dangerous dynamic code execution (eval)", detected)
        self.assertIn("Possible SQL injection in formatted string query", detected)

    def test_missing_dependency_audit_is_incomplete_not_vulnerability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
            with patch("security_audit.shutil.which", return_value=None):
                exit_code, output = run_dependency_audit(root)
            self.assertEqual(exit_code, 2)
            self.assertIn("INCOMPLETE", output)

    def test_dependency_audit_does_not_skip_multiple_ecosystems(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text("{}\n", encoding="utf-8")
            (root / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
            calls = []

            def fake_run(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, stdout="clean", stderr="")

            with patch("security_audit.shutil.which", return_value="available"), patch(
                "security_audit.subprocess.run", side_effect=fake_run
            ):
                exit_code, _ = run_dependency_audit(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(calls, [["npm", "audit", "--audit-level=high"], ["pip-audit", "-r", str(root / "requirements.txt")]])


if __name__ == "__main__":
    unittest.main()
