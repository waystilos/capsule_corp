import json
import os
import re
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import install_elixir, init_project, audit_transcripts  # noqa: E402

NO_ELIXIR = {"elixir": None, "erlang": None, "path": None}


def run_quiet(fn, *args, **kwargs):
    out, err = StringIO(), StringIO()
    with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
        rc = fn(*args, **kwargs)
    return rc, out.getvalue(), err.getvalue()


class InstallElixirTests(unittest.TestCase):
    def _patch(self, commands, manager="apt"):
        return (
            mock.patch.object(install_elixir, "get_installed_versions", return_value=NO_ELIXIR),
            mock.patch.object(install_elixir, "detect_installer", return_value=(manager, commands, "plan")),
        )

    def test_json_without_yes_refuses_and_runs_nothing(self):
        p1, p2 = self._patch([["sudo", "apt-get", "update"]])
        with p1, p2, mock.patch.object(install_elixir.subprocess, "run") as run:
            rc, out, _ = run_quiet(install_elixir.run_install, json_mode=True)
        self.assertNotEqual(rc, 0)
        run.assert_not_called()
        self.assertEqual(json.loads(out)["status"], "error")

    def test_declining_prompt_is_nonzero(self):
        p1, p2 = self._patch([["brew", "install", "elixir"]], "homebrew")
        with p1, p2, mock.patch("builtins.input", return_value="n"), \
                mock.patch.object(install_elixir.subprocess, "run") as run:
            rc, _, _ = run_quiet(install_elixir.run_install)
        self.assertNotEqual(rc, 0)
        run.assert_not_called()

    def test_asdf_plugin_add_failure_is_tolerated(self):
        cmds = [["asdf", "plugin", "add", "erlang"], ["asdf", "install", "erlang", "latest"]]
        p1, p2 = self._patch(cmds, "asdf")
        calls = []

        def fake_run(cmd, check=False):
            calls.append((cmd, check))
            return mock.Mock(returncode=0)

        with p1, p2, mock.patch.object(install_elixir.subprocess, "run", side_effect=fake_run):
            run_quiet(install_elixir.run_install, yes=True)
        self.assertEqual(len(calls), 2)
        self.assertFalse(calls[0][1])
        self.assertTrue(calls[1][1])

    def test_missing_sudo_errors(self):
        p1, p2 = self._patch([["sudo", "apt-get", "update"]])
        with p1, p2, mock.patch.object(install_elixir.shutil, "which", return_value=None), \
                mock.patch.object(install_elixir.os, "geteuid", create=True, return_value=1000), \
                mock.patch.object(install_elixir.subprocess, "run") as run:
            rc, _, err = run_quiet(install_elixir.run_install, yes=True)
        self.assertEqual(rc, 1)
        self.assertIn("sudo", err)
        run.assert_not_called()

    def test_root_strips_sudo(self):
        with mock.patch.object(install_elixir.os, "geteuid", create=True, return_value=0):
            cmds, err = install_elixir.adjust_for_privileges([["sudo", "apt-get", "update"]])
        self.assertIsNone(err)
        self.assertEqual(cmds, [["apt-get", "update"]])

    def test_ps1_wrapper_forwards_json(self):
        text = (ROOT / "scripts" / "install_elixir.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$Json", text)
        self.assertIn('"--json"', text)


class InitProjectTests(unittest.TestCase):
    def test_force_merges_claude_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".claude").mkdir()
            existing = {"model": "opus", "permissions": {"allow": ["Bash(git *)"], "deny": ["Bash(rm *)"]}}
            (target / ".claude" / "settings.json").write_text(json.dumps(existing), encoding="utf-8")
            run_quiet(init_project.init_project, target, force=True, tools={"claude"})
            data = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["permissions"]["deny"], ["Bash(rm *)"])
        allow = data["permissions"]["allow"]
        for rule in ("Bash(git *)", "Bash(capsule *)", "Bash(./bin/capsule *)"):
            self.assertIn(rule, allow)

    def test_force_invalid_settings_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".claude").mkdir()
            f = target / ".claude" / "settings.json"
            f.write_text("{not json", encoding="utf-8")
            run_quiet(init_project.init_project, target, force=True, tools={"claude"})
            self.assertEqual(f.read_text(encoding="utf-8"), "{not json")

    def test_missing_copilot_source_reports_not_crashes(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as empty_root:
            with mock.patch.object(init_project, "CAPSULE_ROOT", Path(empty_root)):
                _, _, err = run_quiet(init_project.init_project, Path(tmp), tools={"copilot"})
        self.assertIn("copilot-instructions.md", err)


class AuditTranscriptTests(unittest.TestCase):
    def test_non_string_content_does_not_crash(self):
        steps = [
            {"type": "PLANNER_RESPONSE", "content": [{"type": "text", "text": "done"}], "tool_calls": None},
            {"type": "USER_INPUT", "content": [{"type": "text", "text": "no, stop that"}, "extra"]},
            {"type": "PLANNER_RESPONSE", "content": {"text": "x"}, "tool_calls": ["bad", {"function": None, "name": "t"}]},
            {"type": "USER_INPUT", "content": None, "status": "ERROR"},
        ]
        result = audit_transcripts.analyze_transcript(steps)
        self.assertEqual(len(result["human_corrections"]), 1)
        self.assertEqual(result["tool_usage"], {"t": 1})


class AgentsDedupeTests(unittest.TestCase):
    def test_no_duplicate_agent_symlink_targets_or_names(self):
        agents = ROOT / ".claude" / "agents"
        targets = {}
        for f in sorted(agents.glob("*.md")):
            self.assertNotIn("_", f.name, f.name)
            key = os.path.realpath(str(f))
            self.assertNotIn(key, targets, "%s duplicates %s" % (f.name, targets.get(key)))
            targets[key] = f.name
        names = []
        for key in targets:
            m = re.search(r'^name:\s*"?([\w-]+)"?\s*$', Path(key).read_text(encoding="utf-8"), re.M)
            self.assertIsNotNone(m, key)
            names.append(m.group(1))
        self.assertEqual(len(names), len(set(names)))

    def test_agent_files_match_frontmatter_name(self):
        for f in (ROOT / ".claude" / "agents").glob("*.md"):
            m = re.search(r'^name:\s*"?([\w-]+)"?\s*$', f.read_text(encoding="utf-8"), re.M)
            self.assertEqual(m.group(1) + ".md", f.name)


if __name__ == "__main__":
    unittest.main()
