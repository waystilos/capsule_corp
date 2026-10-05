#!/usr/bin/env python3
"""Epic 3 / slice B: new secret patterns, generic-rule false-positive reduction,
quoted-literal snippet redaction and vendor-dir reporting.

Fake secrets are assembled at runtime so the repo never holds anything secret-shaped.
"""

import contextlib
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import grill_code
import red_team
import secret_patterns as sp
import security_audit


def descs(text):
    return [d for _, _, d in sp.find_secrets(text)]


def diff_hits(text):
    diff = "+" + text + "\n"
    return [d for pat, d in sp.DIFF_SECRET_PATTERNS if pat.search(diff)]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class NewPatternTests(unittest.TestCase):
    def cases(self):
        return [
            ("Unquoted", "API_" + "TOKEN=" + "Ab3dEf6hIj9kLm2nOp5q"),
            ("Unquoted", "SECRET_" + "KEY=" + "abcdefghijklmnopqrst"),
            ("Unquoted", "DB_PASS" + "WORD=" + "hunter2hunter2hunter2"),
            ("Unquoted", "pass" + "word: " + "s3cretvalue1234567"),
            ("URL", "postgres://" + "admin" + ":" + "S3cr3tPw" + "@db.internal:5432/app"),
            ("Bearer", "Authorization: " + "Bearer " + "abcDEF123456789xyzABCDEF"),
            ("JSON Web Token", "e" + "yJhbGciOiJIUzI1NiJ9" + "." + "e" + "yJzdWIiOiIxMjM0NTY3ODkwIn0" + "." + "SflKxwRJSMeKKF2QT4fwpM"),
            ("Mailgun", "ke" + "y-" + "0123456789abcdef" * 2),
            ("Azure", "Account" + "Key=" + "aB3/" * 12 + "=="),
            ("DigitalOcean", "do" + "p_v1_" + "a1" * 32),
            ("Shopify", "shp" + "at_" + "a1" * 16),
            ("PyPI", "py" + "pi-AgEIcHlwaS5vcmc" + "A1_" * 20),
            ("Square", "sq0" + "atp-" + "Ab1_" * 5 + "Ab"),
            ("Discord", "M" + "TA1234567890123456789012" + ".abcdEF." + "a1" * 14),
        ]

    def test_each_new_pattern_detected_in_files_and_diff(self):
        for label, secret in self.cases():
            with self.subTest(label=label):
                text = "x = 1\n" + secret + "\n"
                self.assertTrue(any(label.lower() in d.lower() for d in descs(text)), (label, descs(text)))
                self.assertTrue(diff_hits(secret), label)

    def test_env_file_flagged_by_security_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / ".env", "API_" + "TOKEN=" + "x9Yz8Wv7Ut6Sr5Qp4On3Ml\n")
            found = [f for f in security_audit.scan_for_secrets(proj) if f["type"] == "SECRET_LEAK"]
            self.assertEqual(len(found), 1)
            self.assertNotIn("x9Yz8Wv7Ut6Sr5Qp4On3Ml", found[0]["snippet"])

    def test_placeholders_and_non_secrets_not_flagged(self):
        quiet = [
            "API_" + "TOKEN=changeme",
            "API_" + "TOKEN=your_token_here",
            "API_" + "TOKEN=${VAR}",
            "API_" + "TOKEN=$SOME_ENV_VAR_VALUE",
            "pass" + "word: ${DB_PASSWORD}",
            "pass" + "word: changeme_changeme_1234",
            "http://user:pass@localhost/x",
            "postgres://user:${PW}@host/db",
            "Authorization: Bearer ${TOKEN}",
            "Authorization: Bearer <token>",
            "Authorization: Bearer your_token_here_abc123",
            "token = get_token_from_config_value",
            "API_TOKEN=SOME_CONSTANT_NAME_VALUE",
        ]
        for line in quiet:
            with self.subTest(line=line):
                self.assertEqual(descs(line), [], line)
                self.assertEqual(diff_hits(line), [], line)

    def test_generic_rule_false_positives_removed(self):
        for line in ('token_type = "authorization_code_flow"',
                     "secret_path = '/etc/secrets/service.json'",
                     "passwordField = 'user_password_input'"):
            with self.subTest(line=line):
                self.assertEqual(descs(line), [], line)
                self.assertEqual(diff_hits(line), [], line)

    def test_generic_rule_still_flags_digit_or_mixed_case(self):
        self.assertTrue(descs("my_sec" + "ret = 'Abc123DefGhi456'"))
        self.assertTrue(descs("my_to" + "ken = 'AbCdEfGhIjKlMn'"))


class TimingTests(unittest.TestCase):
    BUDGET = 15.0   # generous: only catches catastrophic backtracking

    def test_new_patterns_fast_on_megabyte_adversarial_input(self):
        m = 1_100_000
        hostile = {
            "underscore": "a_" * (m // 2),
            "jwt_chain": "eyJaaaaaaaaaaa." * (m // 15),
            "jwt_run": "eyJ" + "a" * m,
            "discord": "Maaaaaaaaaaaaaaaaaaaaaaaa." * (m // 26),
            "env_chain": "token=" * (m // 6),
            "yaml_chain": "password: " * (m // 10),
            "env_value": "password=" + "a" * m,
            "url": "http://" + "a:" * (m // 2),
            "bearer": "Authorization: Bearer " + "a" * m,
            "azure": "AccountKey=" * (m // 11),
            "square": "sq0atp-" * (m // 7),
        }
        for name, text in hostile.items():
            with self.subTest(name=name):
                start = time.monotonic()
                sp.find_secrets(text)
                for pat, _ in sp.DIFF_SECRET_PATTERNS:
                    pat.search("+" + text[:200000])
                self.assertLess(time.monotonic() - start, self.BUDGET)


class SnippetRedactionTests(unittest.TestCase):
    LIT = "Zq8rT2vLp9XwKc"

    def test_safe_snippet_masks_quoted_literals(self):
        out = sp.safe_snippet('requests.get(url, headers={"X-Auth": "%s"}, verify=False)' % self.LIT)
        self.assertNotIn(self.LIT, out)
        self.assertIn("verify=False", out)

    def test_safe_snippet_keeps_plain_snake_words_and_short_literals(self):
        out = sp.safe_snippet("mode = 'read_only_mode'; k = 'abc'")
        self.assertIn("read_only_mode", out)
        self.assertIn("'abc'", out)

    def test_red_team_snippet_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "app.py", 'import requests\nrequests.get("https://x", headers={"k": "%s"}, verify=False)\n'
                  % self.LIT)
            audit = red_team.run_red_team_audit(proj)
            self.assertTrue(audit["findings"])
            self.assertNotIn(self.LIT, json.dumps(audit))

    def test_security_code_vuln_snippet_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "app.py", 'x = eval("%s")\n' % self.LIT)
            found = security_audit.scan_code_vulnerabilities(proj)
            self.assertTrue(found)
            self.assertNotIn(self.LIT, json.dumps(found))

    def test_grill_snippet_redacted_but_issue_id_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "app.py", 'import requests\nr = requests.get("https://h/%s")  # TODO: fix\n' % self.LIT)
            report = grill_code.run_grill_audit(proj, scan_all=True)
            self.assertTrue(report["issues"])
            self.assertNotIn(self.LIT, json.dumps(report))
            self.assertNotIn(self.LIT, grill_code.format_grill_report(report))
            raw = 'r = requests.get("https://h/%s")  # TODO: fix' % self.LIT
            ids = [i["id"] for i in report["issues"]]
            self.assertIn(grill_code.make_issue_id("app.py", "MISSING_HTTP_TIMEOUT", raw), ids)


class VendorReportTests(unittest.TestCase):
    def make(self, tmp):
        proj = Path(tmp).resolve()
        write(proj / "app.py", "x = 1\n")
        write(proj / "node_modules" / "pkg" / "i.js", "// vendored\n")
        write(proj / ".venv" / "lib" / "a.py", "y = 2\n")
        return proj

    def run_main(self, module, argv):
        out = io.StringIO()
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
            try:
                rc = module.main()
            except SystemExit as exc:
                rc = exc.code
        return rc, out.getvalue()

    def test_collect_files_reports_only_present_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.make(tmp)
            uni = sp.collect_files(proj)
            self.assertEqual(uni.skipped_vendor_dirs, [".venv", "node_modules"])
            self.assertFalse(any("node_modules" in rel for _, rel in uni.files))

    def test_no_vendor_dirs_reports_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "x = 1\n")
            self.assertEqual(sp.collect_files(proj).skipped_vendor_dirs, [])

    def test_security_text_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.make(tmp)
            with patch.object(security_audit, "run_dependency_audit", return_value=(0, "ok")):
                _, out = self.run_main(security_audit, ["s", str(proj)])
                self.assertIn("Skipped vendor dirs: .venv, node_modules", out)
                _, jout = self.run_main(security_audit, ["s", str(proj), "--json"])
            self.assertEqual(json.loads(jout)["skipped_vendor_dirs"], [".venv", "node_modules"])

    def test_attack_text_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.make(tmp)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                red_team.main([str(proj), "--json"])
            self.assertEqual(json.loads(out.getvalue())["skipped_vendor_dirs"], [".venv", "node_modules"])
            text = red_team.format_red_team_report(red_team.run_red_team_audit(proj))
            self.assertIn("Skipped vendor dirs: .venv, node_modules", text)
            self.assertEqual(red_team.run_red_team_audit(proj)["skipped_vendor_dirs"], [".venv", "node_modules"])

    def test_no_line_when_nothing_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp).resolve()
            write(proj / "a.py", "x = 1\n")
            self.assertNotIn("Skipped vendor dirs", red_team.format_red_team_report(red_team.run_red_team_audit(proj)))


if __name__ == "__main__":
    unittest.main()
