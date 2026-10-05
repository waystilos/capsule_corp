#!/usr/bin/env python3
"""Docs/template drift guard: every `capsule <cmd>` documented must exist in the CLI dispatcher."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CMD_RE = re.compile(r"(?<![\w.\-/])(?:\./bin/)?capsule[ \t]+([a-z][a-z\-]+)")
DOC_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".github/copilot-instructions.md"]
# Prose uses of the word "capsule" that are not commands.
NOT_COMMANDS = {"corp", "will", "is", "cli", "and", "or", "the", "has", "never", "config", "directives", "binary", "permissions"}


def dispatcher_commands():
    src = (ROOT / "bin" / "capsule").read_text(encoding="utf-8")
    names = set()
    for line in src.splitlines():
        if re.search(r"\bsubcommand\s*(?:==|in\b)", line):
            names.update(re.findall(r"""["']([a-z][a-z\-]+)["']""", line))
    return names


def documented(text):
    return {m for m in CMD_RE.findall(text) if m not in NOT_COMMANDS}


REQUIRED = {"send", "inbox", "ack", "models", "install-elixir"}


class TestDocsMatchCli(unittest.TestCase):
    def setUp(self):
        self.cli = dispatcher_commands()

    def test_dispatcher_parsed(self):
        self.assertTrue({"check", "verify", "room", "send", "install-elixir"} <= self.cli)

    def test_init_templates_commands_exist(self):
        text = (ROOT / "scripts" / "init_project.py").read_text(encoding="utf-8")
        cmds = documented(text)
        self.assertTrue(REQUIRED <= cmds, REQUIRED - cmds)
        self.assertEqual(sorted(cmds - self.cli), [])

    def test_repo_docs_commands_exist(self):
        for name in DOC_FILES + ["README.md"]:
            cmds = documented((ROOT / name).read_text(encoding="utf-8"))
            self.assertEqual(sorted(cmds - self.cli), [], name)

    def test_repo_docs_match_template_essentials(self):
        for name in DOC_FILES:
            text = (ROOT / name).read_text(encoding="utf-8")
            for cmd in ("send", "inbox", "ack", "models", "install-elixir"):
                self.assertIn("capsule " + cmd, text, f"{name} missing `capsule {cmd}`")
            low = text.lower()
            self.assertIn("untrusted", low, name)
            self.assertIn("installer only", low, name)
            self.assertIn("--trust", text, name)
            self.assertIn("CAPSULE_TRUST", text, name)

    def test_template_documents_trust_modes(self):
        text = (ROOT / "scripts" / "init_project.py").read_text(encoding="utf-8")
        self.assertIn("--trust", text)
        self.assertIn("--strict", text)
        self.assertIn("CAPSULE_TRUST", text)

    def test_readme_documents_trust(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for needle in ("--trust", "--strict", "CAPSULE_TRUST=1", "CAPSULE_TRUST=0"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
