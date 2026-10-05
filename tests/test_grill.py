#!/usr/bin/env python3
"""Regression tests for scripts/grill_code.py (Lord Beerus' code griller)."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

from grill_code import (  # noqa: E402
    format_grill_report,
    interactive_grill,
    is_valid_defense,
    run_grill_audit,
    save_defense,
)

BAD = "try:\n    work()\nexcept Exception:\n    pass\n"


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(root), check=True, capture_output=True, text=True,
    )


def init_repo(root, commit=True):
    git(root, "init", "-q")
    if commit:
        (Path(root) / "README.md").write_text("hi\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-q", "-m", "init")


class TestUntrackedAndGitModes(unittest.TestCase):
    def test_untracked_file_is_grilled_when_diff_empty(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            report = run_grill_audit(root)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertTrue(any(i["category"] == "SWALLOWED_EXCEPTION" and i["file"] == "bad.py" for i in report["issues"]))

    def test_untracked_scanned_alongside_tracked_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            (root / "README.md").write_text("changed\n", encoding="utf-8")
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            report = run_grill_audit(root)
            self.assertEqual(report["mode"], "diff_audit")
            self.assertEqual(report["verdict"], "FAIL")

    def test_broken_symlink_untracked_is_tolerated(self):
        if not hasattr(os, "symlink"):
            self.skipTest("no symlink support")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            try:
                os.symlink(str(root / "nowhere"), str(root / "dangling.py"))
            except (OSError, NotImplementedError):
                self.skipTest("cannot create symlink")
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            report = run_grill_audit(root)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIsNone(report["error"])

    def test_staged_with_nothing_staged_does_not_full_scan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            (root / "bad.py").write_text(BAD, encoding="utf-8")  # untracked, not staged
            report = run_grill_audit(root, staged=True)
            self.assertNotEqual(report["mode"], "full_scan")
            self.assertTrue(report["nothing_to_grill"])
            self.assertEqual(report["issues"], [])
            self.assertIn("NOTHING TO GRILL", report["threat_level"])
            self.assertNotIn("DIVINE APPROVAL (SAFE)", report["threat_level"])
            self.assertIn("nothing to grill", format_grill_report(report))

    def test_staged_scans_staged_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            git(root, "add", "bad.py")
            report = run_grill_audit(root, staged=True)
            self.assertEqual(report["verdict"], "FAIL")

    def test_fresh_repo_without_commits_is_not_all_clear(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root, commit=False)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            git(root, "add", "bad.py")
            report = run_grill_audit(root)
            self.assertIsNone(report["error"])
            self.assertEqual(report["verdict"], "FAIL")

    def test_fresh_repo_tracked_add_is_diffed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root, commit=False)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            git(root, "add", "bad.py")
            (root / "other.txt").write_text("x\n", encoding="utf-8")  # untracked non-code
            report = run_grill_audit(root)
            self.assertTrue(any(i["file"] == "bad.py" for i in report["issues"]))

    def test_non_git_dir_reports_honest_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            report = run_grill_audit(root)
            self.assertEqual(report["mode"], "full_scan")
            self.assertIn("Not a git repository", report["note"])
            self.assertEqual(report["verdict"], "FAIL")

    def test_noprefix_diff_config_does_not_break_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            (root / "bad.py").write_text("x = 1\n", encoding="utf-8")
            git(root, "add", "bad.py")
            git(root, "commit", "-q", "-m", "add")
            git(root, "config", "diff.noprefix", "true")
            (root / "bad.py").write_text("x = 1\n" + BAD, encoding="utf-8")
            report = run_grill_audit(root)
            hits = [i for i in report["issues"] if i["category"] == "SWALLOWED_EXCEPTION"]
            self.assertTrue(hits)
            self.assertEqual(hits[0]["file"], "bad.py")

    def test_line_numbers_account_for_context_lines(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            (root / "m.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
            git(root, "add", "m.py")
            git(root, "commit", "-q", "-m", "m")
            (root / "m.py").write_text("a = 1\nb = 2\nc = 3\nd = 4  # TODO: fix this\n", encoding="utf-8")
            report = run_grill_audit(root)
            debt = [i for i in report["issues"] if i["category"] == "DEFERRED_DEBT"]
            self.assertEqual(debt[0]["line"], 4)

    def test_full_scan_runs_null_hazard(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "n.py").write_text("v = resp.data.user.name\n", encoding="utf-8")
            report = run_grill_audit(root, scan_all=True)
            self.assertTrue(any(i["category"] == "UNGUARDED_DEEP_ACCESS" for i in report["issues"]))

    def test_diff_mode_untested_complexity_for_untracked_code(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_repo(root)
            (root / "feature.py").write_text("def brand_new():\n    return 1\n", encoding="utf-8")
            report = run_grill_audit(root)
            self.assertTrue(any(i["category"] == "UNTESTED_COMPLEXITY" for i in report["issues"]))


class TestDefenses(unittest.TestCase):
    def test_is_valid_defense(self):
        for bad in ["", "   ", "ok", "n/a", "because", "aaaaaaaaaaaaaaaaaaaa", "too short", None]:
            self.assertFalse(is_valid_defense(bad), bad)
        self.assertTrue(is_valid_defense("Best-effort cleanup during shutdown"))

    def test_save_defense_rejects_trivial(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                save_defense(root, "x", "fine", "q")
            self.assertFalse((root / ".capsule" / "grill_defenses.json").exists())

    def test_trivial_defense_in_file_does_not_defend(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            issue_id = run_grill_audit(root, scan_all=True)["issues"][0]["id"]
            (root / ".capsule").mkdir()
            (root / ".capsule" / "grill_defenses.json").write_text(
                '{"%s": {"defense": "ok", "question": "q"}}' % issue_id, encoding="utf-8")
            report = run_grill_audit(root, scan_all=True)
            self.assertFalse(report["issues"][0]["defended"])
            self.assertEqual(report["verdict"], "FAIL")

    def test_defense_survives_line_shift(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "bad.py"
            f.write_text(BAD, encoding="utf-8")
            r1 = run_grill_audit(root, scan_all=True)
            save_defense(root, r1["issues"][0]["id"], "Best-effort cleanup during shutdown", "q")
            f.write_text("import os\n\n\n# padding\n" + BAD, encoding="utf-8")
            r2 = run_grill_audit(root, scan_all=True)
            self.assertNotEqual(r2["issues"][0]["line"], r1["issues"][0]["line"])
            self.assertTrue(r2["issues"][0]["defended"])

    def test_defense_does_not_cover_changed_content(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "bad.py"
            f.write_text("try:\n    a()\nexcept ValueError:\n    pass\n", encoding="utf-8")
            r1 = run_grill_audit(root, scan_all=True)
            save_defense(root, r1["issues"][0]["id"], "Best-effort cleanup during shutdown", "q")
            f.write_text("try:\n    a()\nexcept KeyError:\n    pass\n", encoding="utf-8")
            r2 = run_grill_audit(root, scan_all=True)
            self.assertFalse(r2["issues"][0]["defended"])

    def test_defended_critical_is_surfaced_in_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            r1 = run_grill_audit(root, scan_all=True)
            save_defense(root, r1["issues"][0]["id"], "Best-effort cleanup during shutdown", "q")
            r2 = run_grill_audit(root, scan_all=True)
            self.assertEqual(r2["summary"]["critical"], 0)
            self.assertEqual(r2["summary"]["defended_critical"], 1)
            self.assertEqual(r2["defended_critical"][0]["defense"], "Best-effort cleanup during shutdown")
            self.assertNotEqual(r2["threat_level"], "DIVINE APPROVAL (SAFE)")
            rendered = format_grill_report(r2)
            self.assertIn("DEFENDED", rendered)
            self.assertIn("Best-effort cleanup during shutdown", rendered)

    def test_interactive_rejects_trivial_then_accepts_real(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bad.py").write_text(BAD, encoding="utf-8")
            report = run_grill_audit(root, scan_all=True)
            with patch("builtins.input", return_value="ok"):
                interactive_grill(root, report, scan_all=True)
            self.assertFalse(run_grill_audit(root, scan_all=True)["issues"][0]["defended"])
            with patch("builtins.input", return_value="Best-effort cleanup during shutdown"):
                interactive_grill(root, report, scan_all=True)
            self.assertTrue(run_grill_audit(root, scan_all=True)["issues"][0]["defended"])


if __name__ == "__main__":
    unittest.main()
