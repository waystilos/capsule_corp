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

from scripts import init_project, audit_transcripts  # noqa: E402


def run_quiet(fn, *args, **kwargs):
    out, err = StringIO(), StringIO()
    with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
        rc = fn(*args, **kwargs)
    return rc, out.getvalue(), err.getvalue()


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


def read_agent_md(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    raw = content.strip().replace("\\", "/")
    if not path.is_symlink() and "bots/" in raw:
        target = (path.parent / content.strip()).resolve()
        if target.is_file():
            return target.read_text(encoding="utf-8")
    return content


class AgentsDedupeTests(unittest.TestCase):
    def test_no_duplicate_agent_symlink_targets_or_names(self):
        agents = ROOT / ".claude" / "agents"
        targets = {}
        for f in sorted(agents.glob("*.md")):
            self.assertNotIn("_", f.name, f.name)
            if f.is_symlink():
                key = os.path.realpath(str(f))
            else:
                raw = f.read_text(encoding="utf-8").strip()
                target = (f.parent / raw).resolve()
                key = str(target) if target.is_file() else os.path.realpath(str(f))
            self.assertNotIn(key, targets, "%s duplicates %s" % (f.name, targets.get(key)))
            targets[key] = f.name
        names = []
        for key in targets:
            m = re.search(r'^name:\s*"?([\w-]+)"?\s*$', read_agent_md(Path(key)), re.M)
            self.assertIsNotNone(m, key)
            names.append(m.group(1))
        self.assertEqual(len(names), len(set(names)))

    def test_agent_files_match_frontmatter_name(self):
        for f in (ROOT / ".claude" / "agents").glob("*.md"):
            m = re.search(r'^name:\s*"?([\w-]+)"?\s*$', read_agent_md(f), re.M)
            self.assertEqual(m.group(1) + ".md", f.name)


if __name__ == "__main__":
    unittest.main()
