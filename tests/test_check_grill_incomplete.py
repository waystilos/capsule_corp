#!/usr/bin/env python3
"""check --grill must map grill's INCOMPLETE verdict to INCOMPLETE, never PASSED."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import check_project  # noqa: E402
import grill_code  # noqa: E402


def _run(verdict):
    fake = {"verdict": verdict, "threat_level": "X", "issues": [], "summary": {"critical": 0}}
    with tempfile.TemporaryDirectory() as d, mock.patch.object(grill_code, "run_grill_audit", return_value=fake):
        return check_project.run_project_checks(
            Path(d), skip_secrets=True, skip_tests=True, check_grill=True
        )


def _beerus(report):
    return [c for c in report["checks"] if c["name"] == "Beerus Inquisition"][0] if "checks" in report else \
        [c for c in report["results"] if c["name"] == "Beerus Inquisition"][0]


class GrillIncompleteTests(unittest.TestCase):
    def test_incomplete_not_passed(self):
        report = _run("INCOMPLETE")
        self.assertEqual(_beerus(report)["status"], "INCOMPLETE")
        self.assertEqual(report["verdict"], "INCOMPLETE")

    def test_pass_still_passes(self):
        self.assertEqual(_beerus(_run("PASS"))["status"], "PASSED")

    def test_unknown_verdict_is_incomplete(self):
        self.assertEqual(_beerus(_run("???"))["status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
