import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPSULE = str(ROOT / "bin" / "capsule")

from scripts import models  # noqa: E402


def run(args, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("CAPSULE_")}
    e.update(env or {})
    return subprocess.run([sys.executable, CAPSULE] + args, env=e, capture_output=True, text=True)


def route(text, *flags, env=None):
    res = run(["route", "--json", *flags, text], env)
    return json.loads(res.stdout)


SECURITY_REQUESTS = (
    "fix the xss in the login form",
    "fix csrf token check bypass in the settings page",
    "fix a typo in the password reset flow, rce possible",
    "implement a fix for the sqli in webhooks",
    "code review of crypto signing, fix bug",
)


class SecurityRoutingTests(unittest.TestCase):
    def test_examples_never_downshift(self):
        for text in SECURITY_REQUESTS:
            with self.subTest(text=text):
                d = route(text)
                self.assertNotEqual(d["model"], "haiku")
                for hop in d["hops"]:
                    self.assertNotEqual(hop["tier"], "flash", hop)
                    self.assertNotEqual(hop["model"], "haiku", hop)
                self.assertEqual(d["owner"], "android-17")
                self.assertNotIn("small_fix downshift", d["model_reason"].replace("small_fix downshift skipped", ""))

    def test_small_fix_route_tier_skips_downshift_for_security(self):
        self.assertIsNone(models.route_tier("small_fix", "pro", request="fix the xss")[0])
        self.assertEqual(models.route_tier("small_fix", "pro", request="fix a typo")[0], "flash")

    def test_keywords_word_boundary(self):
        for kw in ("xss", "csrf", "ssrf", "rce", "password", "token", "crypto", "exploit", "privilege", "overflow",
                   "bypass", "sqli", "traversal", "deserialization", "jwt", "oauth", "session", "cookie", "cors",
                   "encryption", "hash", "sanitize", "vuln", "cve", "secret", "leak", "auth", "injection"):
            with self.subTest(kw=kw):
                self.assertTrue(models.has_security_keyword(f"fix the {kw.upper()} thing"))
        for text in ("fix the author page", "fix the hashtag", "tweak the source css", "fix typo in the author bio"):
            with self.subTest(text=text):
                self.assertFalse(models.has_security_keyword(text))


class ProtectedDowngradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "config", self.tmp / "config")
        shutil.copy(ROOT / "registry.yaml", self.tmp / "registry.yaml")
        self.env = {"CAPSULE_RESOURCE_ROOT": str(self.tmp)}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_persistent_config_downgrade_warns_and_logs(self):
        res = run(["models", "set", "pro", "haiku", "--force"], self.env)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("WARN", res.stdout)
        log = (self.tmp / "config" / "models-changes.log").read_text()
        self.assertIn("tiers.pro", log)
        self.assertIn("-> haiku", log)
        d = route("run a red team attack on the auth flow", env=self.env)
        self.assertIn("override_warning", d)
        self.assertIn("haiku", d["override_warning"])
        self.assertTrue(any("protected" in w for w in d["warnings"]), d["warnings"])

    def test_tier_env_downgrade_warns(self):
        d = route("security audit of secrets", env=dict(self.env, CAPSULE_MODEL_PRO="haiku"))
        self.assertIn("override_warning", d)

    def test_no_warning_by_default(self):
        d = route("security audit of secrets", env=self.env)
        self.assertNotIn("override_warning", d)


class ComplexEpicTests(unittest.TestCase):
    def test_single_weak_signal_is_not_epic(self):
        for text in ("fix typo in the system", "migrate the users table", "tweak the architecture diagram css"):
            with self.subTest(text=text):
                d = route(text)
                self.assertNotEqual(d["workflow_tier"], "complex_epic", d)
                self.assertNotIn("piccolo", d["handoff"])

    def test_strong_or_multiple_signals_are_epic(self):
        for text in ("plan the epic for onboarding", "redesign the system architecture"):
            with self.subTest(text=text):
                self.assertEqual(route(text)["workflow_tier"], "complex_epic")

    def test_flags_warn_on_every_hop(self):
        d = route("add a settings page feature", "--model", "sonnet")
        self.assertEqual(len([w for w in d["warnings"] if "--model" in w]), len(d["hops"]))
        d = route("add a settings page feature", "--escalate")
        self.assertTrue(any("--escalate" in w for w in d["warnings"]), d["warnings"])
        d = route("add a settings page feature", "--tier", "premium")
        self.assertEqual(len([w for w in d["warnings"] if "--tier" in w]), len(d["hops"]))


if __name__ == "__main__":
    unittest.main()
