#!/usr/bin/env python3
"""Epic 3 / slice M: scanner time budgets (Cell C3/C5/C6/C7), suffix coverage, honest wording,
and the F-043 no-declared-dependencies rule. Budgets are shortened so tests stay fast."""

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

import red_team
import secret_patterns as sp
import security_audit

GHP = "gh" + "p_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"   # ghp_ + 36 chars


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


class Timed(unittest.TestCase):
    def timed(self, limit, fn):
        t = time.monotonic()
        result = fn()
        self.assertLess(time.monotonic() - t, limit)
        return result


class WindowLoopBudgetTests(Timed):
    def test_one_megabyte_prompt_line_hits_file_budget_not_60s(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", ('prompt=f"f"{' * 100000)[:1024 * 1024] + "\n")
            with patch.object(sp, "FILE_TIME_BUDGET", 0.5):
                audit = self.timed(8, lambda: red_team.run_red_team_audit(proj))
            self.assertEqual(audit["verdict"], "INCOMPLETE")
            self.assertTrue(any("a.py" in n and "budget" in n for n in audit["incomplete"]))

    def test_security_audit_window_loop_honors_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "q.py", 'q = f"' + "SELECT x WHERE " * 70000 + "\n")
            with patch.object(sp, "FILE_TIME_BUDGET", -1.0):   # already expired: must stop inside the one line
                found = self.timed(2, lambda: security_audit.scan_code_vulnerabilities(proj))
            self.assertIn("SCAN_INCOMPLETE", [f["type"] for f in found])

    def test_prompt_pattern_is_bounded_per_window(self):
        window = ('prompt=f"f"{' * 100)[:sp.LINE_WINDOW]
        t = time.monotonic()
        for _ in range(20):
            red_team.PROMPT_INJECTION_PATTERNS[0][0].search(window)
        self.assertLess(time.monotonic() - t, 2.0)

    def test_prompt_detection_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", 'messages = [f"hi {user_input}"]\n')
            cats = {f["category"] for f in red_team.run_red_team_audit(proj)["findings"]}
            self.assertIn("PROMPT_INJECTION", cats)


class TotalBudgetTests(Timed):
    def _eight_files(self, proj):
        line = ('messages = [f"{' * 40000)[:560 * 1024] + "\n"
        for i in range(8):
            write(proj / ("m%d.py" % i), line)

    def test_total_budget_param_makes_attack_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            self._eight_files(proj)
            audit = self.timed(25, lambda: red_team.run_red_team_audit(proj, total_budget=1.0))
            self.assertEqual(audit["verdict"], "INCOMPLETE")
            self.assertTrue(any("Total scan time budget" in n or "budget exceeded" in n
                                for n in audit["incomplete"]))

    def test_total_budget_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            self._eight_files(proj)
            with patch.dict(os.environ, {"CAPSULE_SCAN_TOTAL_BUDGET": "1"}):
                self.assertEqual(sp.total_time_budget(), 1.0)
                audit = self.timed(25, lambda: red_team.run_red_team_audit(proj))
            self.assertEqual(audit["verdict"], "INCOMPLETE")

    def test_bad_env_falls_back_to_default(self):
        with patch.dict(os.environ, {"CAPSULE_SCAN_TOTAL_BUDGET": "nope"}):
            self.assertEqual(sp.total_time_budget(), sp.TOTAL_TIME_BUDGET)

    def test_secret_scan_total_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            for i in range(4):
                write(proj / ("f%d.txt" % i), "token=" + "a" * 3000000)
            found = self.timed(20, lambda: security_audit.scan_for_secrets(proj, total_budget=0.0))
            self.assertIn("SCAN_INCOMPLETE", [f["type"] for f in found])
            self.assertTrue(any("Total scan time budget" in f["description"] for f in found))


class WideTextTests(Timed):
    def test_eight_mb_utf16_is_chunked_and_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "u.txt", b"\xff\xfe" + b"_" * (8 * 1024 * 1024))
            chunks = list(sp.iter_text_chunks(proj / "u.txt", {}))
            self.assertGreater(len(chunks), 4)
            self.assertTrue(all(len(t) <= sp.CHUNK_BYTES + sp.CHUNK_OVERLAP + 8 for _, t in chunks))
            found = self.timed(12, lambda: security_audit.scan_for_secrets(proj, total_budget=0.5))
            self.assertIn("SCAN_INCOMPLETE", [f["type"] for f in found])

    def test_wide_secret_after_many_chunks_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            body = ("filler line\n" * 300000) + "key = " + GHP + "\n"
            (proj / "w.txt").write_bytes(body.encode("utf-16"))
            found = [f for f in security_audit.scan_for_secrets(proj) if f["type"] == "SECRET_LEAK"]
            self.assertTrue(found)
            self.assertEqual(found[0]["line"], 300001)

    def test_wide_cap_flags_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "w.txt"
            p.write_bytes(b"\xff\xfe" + b"a\x00" * 100000)
            info = {}
            list(sp.iter_text_chunks(p, info, chunk_bytes=4096, max_total=50000))
            self.assertTrue(info.get("truncated"))


class SuffixAndWordingTests(unittest.TestCase):
    def test_new_suffixes_are_scanned_by_both_scanners(self):
        for suffix in (".mjs", ".cjs", ".mts", ".java", ".cs", ".kt", ".vue", ".svelte", ".sh"):
            self.assertIn(suffix, red_team.CODE_SUFFIXES, suffix)
            self.assertIn(suffix, security_audit.CODE_SUFFIXES, suffix)
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.mjs", 'const r = requests.get(url, verify=False)\n')
            write(proj / "b.kt", "val x = 1\n")
            audit = red_team.run_red_team_audit(proj)
            self.assertTrue(audit["findings"])
            self.assertEqual(audit["summary"]["files_scanned"], 2)
            write(proj / "c.vue", "q = eval(x)\n")
            found = security_audit.scan_code_vulnerabilities(proj)
            self.assertTrue(any(f["file"] == "c.vue" for f in found))

    def test_unknown_text_suffix_is_counted_not_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "x = 1\n")
            write(proj / "s.lua", "print('hi')\n")
            write(proj / "blob.dat", bytes(range(256)) * 4)
            write(proj / "notes.md", "# hi\n")
            audit = red_team.run_red_team_audit(proj)
            self.assertEqual(audit["unscanned_text_files"], ["s.lua"])
            self.assertEqual(audit["summary"]["unscanned_text_files"], 1)
            self.assertIn("s.lua", red_team.format_red_team_report(audit))
            stats = {}
            security_audit.scan_code_vulnerabilities(proj, stats=stats)
            self.assertEqual(stats["unscanned_text"], ["s.lua"])

    def test_clean_report_does_not_claim_defenses_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "x = 1\n")
            audit = red_team.run_red_team_audit(proj)
            self.assertEqual(audit["verdict"], "RESILIENT")   # key kept for compatibility
            text = red_team.format_red_team_report(audit)
            self.assertNotIn("DEFENSES HOLD", text)
            self.assertNotIn("Zero High-Severity", audit["verdict_badge"])
            self.assertIn("not proof", text)
            self.assertIn("not proof", audit["verdict_badge"])


class NoDeclaredDependenciesTests(unittest.TestCase):
    def audit(self, proj):
        with patch("security_audit.shutil.which", return_value=None):
            return security_audit.run_dependency_audit(proj)

    def test_empty_or_absent_dependencies_are_pass_class(self):
        for body in ("[project]\nname='x'\n", "[project]\nname='x'\ndependencies = []\n",
                     "[project]\nname='x'\ndependencies = [\n]\n"):
            with tempfile.TemporaryDirectory() as tmp:
                proj = Path(tmp).resolve()
                write(proj / "pyproject.toml", body)
                code, out = self.audit(proj)
                self.assertEqual(code, 0, body)
                self.assertIn("no declared dependencies", out)

    def test_regex_fallback_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pyproject.toml"
            write(p, "[project]\nname='x'\ndependencies = []\n")
            with patch("_config.load_toml", side_effect=ValueError("boom")):
                self.assertFalse(security_audit._pyproject_declares_deps(p))
            write(p, "[project]\nname='x'\ndependencies = [\n  'a>=1',\n]\n")
            with patch("_config.load_toml", side_effect=ValueError("boom")):
                self.assertTrue(security_audit._pyproject_declares_deps(p))

    def test_declared_dependencies_without_requirements_stay_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "pyproject.toml", "[project]\nname='x'\ndependencies = [\"requests>=2\"]\n")
            code, out = self.audit(proj)
            self.assertEqual(code, 2)
            self.assertIn("INCOMPLETE", out)

    def test_dynamic_dependencies_and_opaque_manifests_stay_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "pyproject.toml", "[project]\nname='x'\ndynamic = ['dependencies']\n")
            self.assertEqual(self.audit(proj)[0], 2)
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "setup.py", "x\n")
            self.assertEqual(self.audit(proj)[0], 2)

    def test_setup_py_without_dependency_keywords(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "setup.py", "from setuptools import setup\nsetup(name='x')\n")
            self.assertEqual(self.audit(proj)[0], 0)
            write(proj / "setup.py", "from setuptools import setup\nsetup(name='x', install_requires=['a'])\n")
            self.assertEqual(self.audit(proj)[0], 2)

    def test_no_pip_audit_is_ever_run_for_empty_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "pyproject.toml", "[project]\nname='x'\n")
            with patch("security_audit.subprocess.run") as run:
                self.assertEqual(security_audit.run_dependency_audit(proj)[0], 0)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
