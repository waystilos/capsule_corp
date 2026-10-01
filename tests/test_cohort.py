#!/usr/bin/env python3
"""
Unit Test Suite for Capsule Corp Cohort Infrastructure
Verifies registry schema, Dr. Gero's auditor, Trunks' sentinel, and bot scaffolding.
"""

import unittest
import os
import json
from datetime import datetime, timezone, timedelta
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
from verify_project import SUSPICIOUS_DIFF_PATTERNS, audit_git_diff, load_project_config
from route_request import route_request
from doctor import run_doctor
from check_project import run_project_checks, format_check_report
from room import clock_in, clock_out, clear_room, detect_environment, load_room_data, prune_stale_shifts, heartbeat
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

    def test_verify_fails_when_configured_lint_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "capsule.json").write_text('{"test": "true", "lint": "false"}', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CAPSULE_ROOT / "scripts" / "verify_project.py"), str(root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("RED", result.stdout)

    def test_verify_fails_on_empty_project_incomplete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            result = subprocess.run(
                [sys.executable, str(CAPSULE_ROOT / "scripts" / "verify_project.py"), str(root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("INCOMPLETE", result.stdout)

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

    def test_initializer_appends_capsule_to_gitignore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gi = root / ".gitignore"
            gi.write_text("node_modules/\n.env\n", encoding="utf-8")

            init_project(root, tools={"copilot"})
            content = gi.read_text(encoding="utf-8")
            self.assertIn(".capsule/", content)
            self.assertIn("node_modules/", content)


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


class TestCapsuleCheck(unittest.TestCase):
    def test_load_project_config_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "capsule.json").write_text('{"test": "pytest -v", "lint": "flake8"}\n', encoding="utf-8")
            cfg = load_project_config(root)
            self.assertEqual(cfg.get("test"), "pytest -v")
            self.assertEqual(cfg.get("lint"), "flake8")

    def test_load_project_config_pyproject(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text('[tool.capsule]\ntest = "pytest"\nlint = "ruff check"\n', encoding="utf-8")
            cfg = load_project_config(root)
            self.assertEqual(cfg.get("test"), "pytest")
            self.assertEqual(cfg.get("lint"), "ruff check")

    def test_run_project_checks_reports_factual_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pass_cmd = f"{sys.executable} -c 'import sys; sys.exit(0)'"
            res = run_project_checks(
                root,
                test_cmd_override=pass_cmd,
                skip_secrets=True
            )
            self.assertEqual(res["verdict"], "PASS")
            tests_check = next((c for c in res["checks"] if c["name"] == "Tests"), None)
            self.assertIsNotNone(tests_check)
            self.assertEqual(tests_check["status"], "PASSED")
            lint_check = next((c for c in res["checks"] if c["name"] == "Lint"), None)
            self.assertIsNotNone(lint_check)
            self.assertEqual(lint_check["status"], "SKIPPED")

    def test_run_project_checks_fails_on_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fail_cmd = f"{sys.executable} -c 'import sys; sys.exit(1)'"
            res = run_project_checks(
                root,
                test_cmd_override=fail_cmd,
                skip_secrets=True
            )
            self.assertEqual(res["verdict"], "FAIL")
            tests_check = next((c for c in res["checks"] if c["name"] == "Tests"), None)
            self.assertIsNotNone(tests_check)
            self.assertEqual(tests_check["status"], "FAILED")

    def test_run_project_checks_empty_project_incomplete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            res = run_project_checks(root, skip_secrets=True)
            self.assertEqual(res["verdict"], "INCOMPLETE")

    def test_run_project_checks_malformed_config_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "capsule.json").write_text("{malformed json...", encoding="utf-8")
            res = run_project_checks(root, skip_secrets=True)
            self.assertEqual(res["verdict"], "FAIL")
            cfg_check = next((c for c in res["checks"] if c["name"] == "Configuration"), None)
            self.assertIsNotNone(cfg_check)
            self.assertEqual(cfg_check["status"], "FAILED")

    def test_route_request_suggests_workflow_tiers(self):
        small = route_request("fix typo in button class")
        self.assertEqual(small["workflow_tier"], "small_fix")
        self.assertIn("Builder", small["suggested_workflow"][0])
        self.assertTrue(small.get("is_suggestion"))

        epic = route_request("deconstruct epic architecture for multi-agent system")
        self.assertEqual(epic["workflow_tier"], "complex_epic")
        self.assertIn("Coordinator", epic["suggested_workflow"][0])

    def test_route_request_workflow_is_scoped_to_handoff_chain(self):
        """Specialist routes must not cycle through Product/Builder/Reviewer by default."""
        import re as _re

        def bots_in(workflow):
            return [m.casefold() for step in workflow for m in _re.findall(r"@([\w-]+)", step)]

        cases = {
            "audit the auth flow for a security vulnerability": "android-17",
            "refactor dead code in room.py": "android-18",
            "add a docker pipeline for deploys": "vegeta",
            "improve onboarding usability": "videl",
            "scaffold a new agent for linting": "dr-gero",
        }
        for request, owner in cases.items():
            result = route_request(request)
            self.assertEqual(result["status"], "routed", request)
            self.assertEqual(result["owner"], owner, request)
            bots = bots_in(result["suggested_workflow"])
            self.assertEqual(bots[0], owner, request)
            self.assertEqual(set(bots), set(result["handoff"]), request)
            self.assertEqual(result["suggested_workflow"][-1], "Verification (capsule check)", request)

        # Builder-owned standard features are the only place Product is added by default.
        feature = route_request("add a user profile feature")
        self.assertEqual(bots_in(feature["suggested_workflow"]), ["bulma", "goku", "trunks"])

        # Small fixes never pull in a coordinator or reviewer step.
        fix = route_request("fix the typo in the README")
        self.assertEqual(bots_in(fix["suggested_workflow"]), ["goku"])


class TestCapsuleRoom(unittest.TestCase):
    def test_detect_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            detected = detect_environment()
            self.assertEqual(detected["provider"], "Local")

        with patch.dict(os.environ, {"CLAUDE_CODE": "1", "CLAUDE_MODEL": "claude-3-7-sonnet"}):
            detected = detect_environment()
            self.assertEqual(detected["agent_id"], "claude")
            self.assertEqual(detected["provider"], "Anthropic")
            self.assertEqual(detected["model"], "claude-3-7-sonnet")

        with patch.dict(os.environ, {"GEMINI_CLI": "1"}):
            detected = detect_environment()
            self.assertEqual(detected["agent_id"], "gemini")
            self.assertEqual(detected["provider"], "Google")
            self.assertEqual(detected["model"], "Unknown")

        with patch.dict(os.environ, {"CODEX": "1"}):
            detected = detect_environment()
            self.assertEqual(detected["agent_id"], "codex")
            self.assertEqual(detected["provider"], "OpenAI")
            self.assertEqual(detected["model"], "Unknown")

        with patch.dict(os.environ, {"CURSOR_AGENT": "1"}):
            detected = detect_environment()
            self.assertEqual(detected["agent_id"], "cursor")
            self.assertEqual(detected["provider"], "Cursor")
            self.assertEqual(detected["model"], "Unknown")

        with patch.dict(os.environ, {"WINDSURF_AGENT": "1"}):
            detected = detect_environment()
            self.assertEqual(detected["agent_id"], "windsurf")
            self.assertEqual(detected["provider"], "Codeium")
            self.assertEqual(detected["model"], "Unknown")

    def test_clock_in_and_out(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shift = clock_in(
                target_dir=root,
                agent="claude",
                provider="Anthropic",
                model="claude-3-7-sonnet",
                role="Builder (@Goku)",
                task="Refactor test runner",
                files=["tests/test_runner.py"],
            )
            self.assertEqual(shift["agent_id"], "claude")
            self.assertEqual(shift["files"], ["tests/test_runner.py"])

            # Verify files on disk
            room_json = root / ".capsule" / "room.json"
            conf_md = root / ".capsule" / "CONFERENCE.md"
            self.assertTrue(room_json.exists())
            self.assertTrue(conf_md.exists())

            data = load_room_data(room_json)
            self.assertIn(shift["shift_id"], data["active_shifts"])
            self.assertIn("Refactor test runner", conf_md.read_text(encoding="utf-8"))

            # Clock out
            out_shift = clock_out(
                target_dir=root,
                agent="claude",
                summary="Refactoring completed and verified",
            )
            self.assertIsNotNone(out_shift)
            self.assertEqual(out_shift["summary"], "Refactoring completed and verified")

            data = load_room_data(room_json)
            self.assertNotIn(shift["shift_id"], data["active_shifts"])
            self.assertEqual(len(data["history"]), 1)
            self.assertEqual(data["history"][0]["agent_id"], "claude")

    def test_unrelated_agent_cannot_clock_out_another_shift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shift = clock_in(root, agent="codex", task="Fix bug")
            # Unrelated agent attempts clock out
            out_unrelated = clock_out(root, agent="claude", summary="Unrelated attempt")
            self.assertIsNone(out_unrelated)

            room_json = root / ".capsule" / "room.json"
            data = load_room_data(room_json)
            self.assertIn(shift["shift_id"], data["active_shifts"])

            # Correct agent clocks out
            out_shift = clock_out(root, agent="codex", summary="Bug fixed")
            self.assertIsNotNone(out_shift)
            self.assertEqual(out_shift["agent_id"], "codex")

    def test_duplicate_provider_sessions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shift1 = clock_in(root, agent="codex", task="Session 1", files=["file1.py"])
            shift2 = clock_in(root, agent="codex", task="Session 2", files=["file2.py"])

            self.assertNotEqual(shift1["shift_id"], shift2["shift_id"])
            data = load_room_data(root / ".capsule" / "room.json")
            self.assertEqual(len(data["active_shifts"]), 2)
            self.assertIn(shift1["shift_id"], data["active_shifts"])
            self.assertIn(shift2["shift_id"], data["active_shifts"])

            ambig = clock_out(root, agent="codex", summary="Done")
            self.assertIsInstance(ambig, dict)
            self.assertEqual(ambig.get("error"), "ambiguous_session")

            out1 = clock_out(root, session=shift1["shift_id"], summary="Session 1 done")
            self.assertIsNotNone(out1)
            self.assertEqual(out1["shift_id"], shift1["shift_id"])

            data = load_room_data(root / ".capsule" / "room.json")
            self.assertNotIn(shift1["shift_id"], data["active_shifts"])
            self.assertIn(shift2["shift_id"], data["active_shifts"])

    def test_conflicting_file_claims_and_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shift1 = clock_in(root, agent="goku", files=["src/auth.py", "src/models.py"])
            self.assertNotIn("error", shift1)

            conflict = clock_in(root, agent="vegeta", files=["src/auth.py"])
            self.assertEqual(conflict.get("error"), "file_conflict")
            self.assertEqual(conflict["conflicts"][0]["owner_agent"], "goku")

            override = clock_in(root, agent="vegeta", files=["src/auth.py"], force=True)
            self.assertNotIn("error", override)
            self.assertTrue(override.get("forced_override"))

    def test_heartbeat_updates_last_seen_and_prevents_expiration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shift = clock_in(root, agent="gemini", task="Long task")

            # Simulate shift active 90 minutes ago (within 2h window)
            past_iso = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
            room_json = root / ".capsule" / "room.json"
            data = load_room_data(room_json)
            data["active_shifts"][shift["shift_id"]]["last_seen_at"] = past_iso
            data["active_shifts"][shift["shift_id"]]["clocked_in_at"] = past_iso
            (root / ".capsule" / "room.json").write_text(json.dumps(data), encoding="utf-8")

            hb = heartbeat(root, session=shift["shift_id"])
            self.assertIsNotNone(hb)
            self.assertTrue(hb.get("ok"))
            self.assertNotEqual(hb["last_seen_at"], past_iso)

            data = load_room_data(room_json)
            changed = prune_stale_shifts(data)
            self.assertFalse(changed)
            self.assertIn(shift["shift_id"], data["active_shifts"])

    def test_prune_stale_shifts_and_cap_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = {
                "active_shifts": {
                    "stale_shift": {
                        "shift_id": "stale_shift",
                        "agent_id": "stale_agent",
                        "agent_name": "Stale Agent",
                        "clocked_in_at": "2020-01-01T00:00:00+00:00",
                        "last_seen_at": "2020-01-01T00:00:00+00:00",
                        "task": "Old task",
                    },
                    "fresh_shift": {
                        "shift_id": "fresh_shift",
                        "agent_id": "fresh_agent",
                        "agent_name": "Fresh Agent",
                        "clocked_in_at": "2099-01-01T00:00:00+00:00",
                        "last_seen_at": "2099-01-01T00:00:00+00:00",
                        "task": "Future task",
                    },
                },
                "history": [{"summary": f"Task {i}"} for i in range(20)],
            }
            changed = prune_stale_shifts(data)
            self.assertTrue(changed)
            self.assertNotIn("stale_shift", data["active_shifts"])
            self.assertIn("fresh_shift", data["active_shifts"])
            self.assertIn("[Auto-Expired]", data["history"][0]["summary"])
            self.assertEqual(len(data["history"]), 15)

    def test_concurrent_registrations_preserve_all_shifts(self):
        import concurrent.futures
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def do_clock_in(i):
                return clock_in(
                    target_dir=root,
                    agent=f"agent_{i}",
                    task=f"Task {i}",
                    files=[f"file_{i}.py"],
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                results = list(executor.map(do_clock_in, range(10)))

            data = load_room_data(root / ".capsule" / "room.json")
            self.assertEqual(len(data["active_shifts"]), 10)
            for i, res in enumerate(results):
                self.assertIn(res["shift_id"], data["active_shifts"])
                self.assertEqual(data["active_shifts"][res["shift_id"]]["agent_id"], f"agent_{i}")

    def test_clear_room(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clock_in(root, agent="gemini", task="Docs")
            clock_in(root, agent="claude", task="Tests")
            room_json = root / ".capsule" / "room.json"
            data = load_room_data(room_json)
            self.assertEqual(len(data["active_shifts"]), 2)

            clear_room(root)
            data = load_room_data(room_json)
            self.assertEqual(len(data["active_shifts"]), 0)


if __name__ == "__main__":
    unittest.main()

