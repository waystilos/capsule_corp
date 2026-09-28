#!/usr/bin/env python3
"""
Unit Test Suite for Capsule Corp Cohort Infrastructure
Verifies registry schema, Dr. Gero's auditor, Trunks' sentinel, and bot scaffolding.
"""

import unittest
from pathlib import Path
import yaml
import sys

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

from scaffold_bot import generate_bot_markdown
from audit_transcripts import analyze_transcript
from verify_project import SUSPICIOUS_DIFF_PATTERNS


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


class TestDrGeroScaffolder(unittest.TestCase):
    def test_generate_bot_markdown(self):
        md = generate_bot_markdown(
            name="test-bot",
            alias="Test Bot",
            role="Testing Specialist",
            inspiration="Lauren Tan Spec",
            description="A test bot",
            jtbd="Run automated checks",
            boundaries="- Do not write production code.",
            tools=["run_command", "view_file"],
            verification="exit code 0",
            creed="Testing is life."
        )
        self.assertIn("# Test Bot: Testing Specialist", md)
        self.assertIn("## 1. Job To Be Done (JTBD)", md)
        self.assertIn("## 2. Allowed Tools", md)
        self.assertIn("## 3. Execution Directives", md)
        self.assertIn("## 4. Verification Gate", md)


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
        dirty_diff = f"""
+<<<<<<< HEAD
+print("conflict")
+=======
+print("resolved")
+>>>>>>> branch
+const apiKey = "{dummy_key}";
"""
        detected_issues = []
        for pattern, desc in SUSPICIOUS_DIFF_PATTERNS:
            if pattern.search(dirty_diff):
                detected_issues.append(desc)

        self.assertIn("Git merge conflict marker (start)", detected_issues)
        self.assertIn("Git merge conflict marker (mid)", detected_issues)
        self.assertIn("Git merge conflict marker (end)", detected_issues)
        self.assertIn("Exposed OpenAI / Service Secret Key", detected_issues)


if __name__ == "__main__":
    unittest.main()
