#!/usr/bin/env python3
"""Epic 3 / slice M (C1b, C8): grill's diff gate must not be dodgeable, and must not be ReDoS-able."""

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import grill_code  # noqa: E402
from grill_code import run_grill_audit  # noqa: E402


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(root), check=True, capture_output=True,
    )


def make_repo(root, files):
    git(root, "init", "-q")
    for name, data in files.items():
        p = Path(root) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")


def cats(report):
    return {i["category"] for i in report["issues"]}


class DiffGateBypassTests(unittest.TestCase):
    def test_plus_plus_prefixed_content_line_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"a.py": "x = 1\n"})
            (root / "a.py").write_text("x = 1\n++ requests.get(url)\n", encoding="utf-8")   # diff line: '+++ requests...'
            report = run_grill_audit(root)
            self.assertEqual(report["mode"], "diff_audit")
            self.assertIn("MISSING_HTTP_TIMEOUT", cats(report))
            self.assertEqual([i["line"] for i in report["issues"] if i["category"] == "MISSING_HTTP_TIMEOUT"], [2])

    def test_line_separator_control_char_does_not_hide_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"a.py": "x = 1\n"})
            (root / "a.py").write_bytes(b"x = 1\ny = 2\x0b# ok\x0brequests.get(url)\nz = 3\ntry:\n    w()\nexcept Exception:\n    pass\n")
            report = run_grill_audit(root)
            self.assertIn("MISSING_HTTP_TIMEOUT", cats(report))
            swallowed = [i for i in report["issues"] if i["category"] == "SWALLOWED_EXCEPTION"]
            self.assertEqual(swallowed[0]["line"], 6)    # \x0b does not shift line numbers

    def test_x0b_in_untracked_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"README.md": "hi\n"})
            (root / "n.py").write_bytes(b"a = 1\x0b\x0brequests.get(url)\n")
            self.assertIn("MISSING_HTTP_TIMEOUT", cats(run_grill_audit(root)))

    def test_nul_byte_file_is_still_diffed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"a.py": b"x = 1\n\x00\n"})
            (root / "a.py").write_bytes(b"x = 1\n\x00\ntry:\n    w()\nexcept Exception:\n    pass\n")
            report = run_grill_audit(root)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("SWALLOWED_EXCEPTION", cats(report))

    def test_gitattributes_minus_diff_does_not_hide_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {".gitattributes": "* -diff\n", "a.py": "x = 1\n"})
            (root / "a.py").write_text("x = 1\ntry:\n    w()\nexcept Exception:\n    pass\n", encoding="utf-8")
            report = run_grill_audit(root)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("SWALLOWED_EXCEPTION", cats(report))

    def test_assume_unchanged_and_skip_worktree_are_incomplete(self):
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                make_repo(root, {"a.py": "x = 1\n", "b.py": "y = 1\n"})
                git(root, "update-index", flag, "a.py")
                (root / "a.py").write_text("x = 1\ntry:\n    w()\nexcept Exception:\n    pass\n", encoding="utf-8")
                (root / "b.py").write_text("y = 2\n", encoding="utf-8")
                report = run_grill_audit(root)
                self.assertEqual(report["verdict"], "INCOMPLETE", flag)
                self.assertTrue(any("a.py" in n for n in report["incomplete"]))
                self.assertNotIn("DIVINE APPROVAL", report["threat_level"])
                self.assertIn("INCOMPLETE", grill_code.format_grill_report(report))

    def test_incomplete_exit_code_is_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"a.py": "x = 1\n"})
            git(root, "update-index", "--assume-unchanged", "a.py")
            (root / "a.py").write_text("x = 2\n", encoding="utf-8")
            res = subprocess.run([sys.executable, str(CAPSULE_ROOT / "scripts" / "grill_code.py"), str(root)],
                                 capture_output=True)
            self.assertEqual(res.returncode, 2)

    def test_real_critical_outranks_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"a.py": "x = 1\n", "b.py": "y = 1\n"})
            git(root, "update-index", "--assume-unchanged", "a.py")
            (root / "b.py").write_text("y = 1\ntry:\n    w()\nexcept Exception:\n    pass\n", encoding="utf-8")
            self.assertEqual(run_grill_audit(root)["verdict"], "FAIL")

    def test_quoted_path_names_are_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"README.md": "hi\n", "we ird\tname.py": "x = 1\n"})
            (root / "we ird\tname.py").write_text("x = 1\nrequests.get(url)\n", encoding="utf-8")
            report = run_grill_audit(root)
            self.assertIn("MISSING_HTTP_TIMEOUT", cats(report))
            self.assertEqual(grill_code._unquote_git_path('"a\\tb\\303\\251"'), "a\tbé")

    def test_clean_change_is_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"a.py": "x = 1\n"})
            (root / "a.py").write_text("x = 2\n", encoding="utf-8")
            report = run_grill_audit(root)
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["incomplete"], [])

    def test_truncated_untracked_file_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            make_repo(root, {"README.md": "hi\n"})
            (root / "big.py").write_text("x = 1\n" * 10 + "#" * 300, encoding="utf-8")
            old = grill_code.MAX_SCAN_BYTES
            grill_code.MAX_SCAN_BYTES = 100
            try:
                report = run_grill_audit(root)
            finally:
                grill_code.MAX_SCAN_BYTES = old
            self.assertEqual(report["verdict"], "INCOMPLETE")


class GrillReDoSTests(unittest.TestCase):
    def timed(self, limit, fn):
        t = time.monotonic()
        result = fn()
        self.assertLess(time.monotonic() - t, limit)
        return result

    def test_requests_get_390kb_line_is_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "a.py").write_text("requests.get(" * 30000 + "\n", encoding="utf-8")
            self.timed(8, lambda: run_grill_audit(root))

    def test_closed_calls_on_huge_line_are_flagged_quickly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "a.py").write_text("requests.get(a) " * 25000 + "\n", encoding="utf-8")
            report = self.timed(8, lambda: run_grill_audit(root))
            self.assertIn("MISSING_HTTP_TIMEOUT", cats(report))
            self.assertEqual(len([i for i in report["issues"] if i["category"] == "MISSING_HTTP_TIMEOUT"]), 1)

    def test_other_quadratic_candidates_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for name, text in {
                "a.py": "except " + " " * 380000 + "x",
                "b.js": "catch(" * 60000,
                "c.py": "# " * 100000 + "a.b.c." * 40000,
                "d.py": "x = open(" * 40000,
            }.items():
                (root / name).write_text(text + "\n", encoding="utf-8")
            self.timed(20, lambda: run_grill_audit(root, scan_all=True))

    def test_timeout_keyword_suppresses_and_unclosed_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "a.py").write_text(
                "requests.get(url, timeout=3)\nhttpx.post(u, data=d)\nurllib.request.urlopen(u, timeout=2)\n"
                "requests.get(\n", encoding="utf-8")
            report = run_grill_audit(root, scan_all=True)
            lines = [i["line"] for i in report["issues"] if i["category"] == "MISSING_HTTP_TIMEOUT"]
            self.assertEqual(lines, [2])

    def test_budgets_yield_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for i in range(3):
                (root / ("f%d.py" % i)).write_text("x = 1\n" * 2000, encoding="utf-8")
            report = run_grill_audit(root, scan_all=True, total_budget=-1.0)
            self.assertEqual(report["verdict"], "INCOMPLETE")
            self.assertTrue(any("budget" in n for n in report["incomplete"]))


if __name__ == "__main__":
    unittest.main()
