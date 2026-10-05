"""Model downshift safety, input validation, no-PyYAML fallback, atomic config writes."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import models, route_request as rr  # noqa: E402

REG = (
    'bots:\n  goku:\n    name: "goku"\n    model_tier: "pro"\n'
    '  trunks:\n    name: "trunks"\n    model_tier: "flash"\n'
    '  android_17:\n    name: "android-17"\n    model_tier: "pro"\n'
    '  cell:\n    name: "cell"\n    model_tier: "pro"\n'
    '  beerus:\n    name: "beerus"\n    model_tier: "pro"\n'
)


def make_root(config=None):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "config").mkdir()
    (root / "registry.yaml").write_text(REG, encoding="utf-8")
    if config is not None:
        (root / "config" / "models.yaml").write_text(config, encoding="utf-8")
    return tmp, root


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CAPSULE_MODEL")}
    env.update(extra)
    return env


class TestDownshiftGuard(unittest.TestCase):
    def route(self, text, env=None, **kw):
        with mock.patch.dict(os.environ, clean_env(**(env or {})), clear=True):
            return rr.attach_model(rr.route_request(text), **kw)

    def test_protected_bots_never_below_registry_tier(self):
        for bot in ("android-17", "cell", "beerus"):
            tier, why = models.guard_tier(bot, "flash")
            self.assertEqual(tier, models.bot_tier(bot), bot)
            self.assertTrue(why)
        self.assertEqual(models.guard_tier("goku", "flash")[0], "flash")  # ordinary bots still downshift

    def test_security_request_keeps_android_17_pro(self):
        res = self.route("fix leaked api key and auth bypass")
        self.assertEqual(res["owner"], "android-17")
        self.assertEqual(res["workflow_tier"], "small_fix")
        self.assertEqual(res["model_tier"], "pro")
        for hop in res["hops"]:
            self.assertNotEqual(hop["tier"], "flash", hop)

    def test_security_keywords_keep_any_route_off_flash(self):
        for kw in ("security", "vulnerab", "secret", "auth", "leak", "injection", "cve"):
            self.assertTrue(models.has_security_keyword(f"fix the {kw} thing"), kw)
        res = self.route("fix the secret handling typo in config")
        self.assertTrue(all(h["tier"] != "flash" for h in res["hops"]))

    def test_plain_small_fix_still_downshifts(self):
        res = self.route("fix the typo in the README")
        self.assertEqual(res["model_tier"], "flash")

    def test_explicit_flash_tier_cannot_downshift_protected_bot(self):
        res = self.route("red team the api", tier="flash")
        self.assertEqual(res["owner"], "cell")
        self.assertEqual(res["model_tier"], "pro")

    def test_env_override_beating_a_downshift_warns(self):
        res = self.route("fix the typo in the README", env={"CAPSULE_MODEL_FLASH": "tiny"})
        self.assertEqual(res["model"], "tiny")
        self.assertTrue(any("CAPSULE_MODEL_FLASH" in w for w in res["warnings"]), res["warnings"])
        res = self.route("red team the api", env={"CAPSULE_MODEL": "weak"})
        self.assertTrue(any("CAPSULE_MODEL" in w for w in res["warnings"]))


class TestModelNameValidation(unittest.TestCase):
    def test_trailing_newline_rejected(self):
        # old `^...$` + re.match accepted "opus\n"
        with self.assertRaises(models.ModelsError):
            models.validate_model_name("opus\n")
        self.assertEqual(models.validate_model_name("claude-opus-4:1m"), "claude-opus-4:1m")

    def test_resolve_rejects_bad_cli_and_env(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        bad = ["--x", "-x", "opus\n--x", "opus\n", "a b", "x\x1b[31m", "", ]
        for value in bad[:-1]:
            with self.assertRaises(models.ModelsError, msg=repr(value)):
                models.resolve_model(bot="goku", root=root, cli_model=value, env={})
            for var in ("CAPSULE_MODEL", "CAPSULE_MODEL_PRO"):
                with self.assertRaises(models.ModelsError, msg=f"{var}={value!r}"):
                    models.resolve_model(bot="goku", root=root, env={var: value})

    def test_cli_rejects_dash_prefixed_and_newline_env(self):
        base = [sys.executable, str(ROOT / "scripts" / "route_request.py")]
        env = clean_env()
        r = subprocess.run(base + ["--model=--x", "fix typo"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2, r.stderr)
        r = subprocess.run(base + ["fix typo"], capture_output=True, text=True,
                           env=dict(env, CAPSULE_MODEL="opus\n--x"))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn("\n--x", r.stderr)

    def test_load_config_rejects_trailing_newline_model(self):
        tmp, root = make_root('tiers:\n  pro: "p1\\n"\n')
        self.addCleanup(tmp.cleanup)
        cfg, warnings = models.load_config(root)
        self.assertEqual(cfg["tiers"]["pro"], "sonnet")
        self.assertTrue(warnings)


class TestSanitizedOutput(unittest.TestCase):
    def test_show_strips_ansi_and_control_from_env(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        env = clean_env(CAPSULE_RESOURCE_ROOT=str(root), CAPSULE_MODEL="\x1b[31mred\x1b[0m\x07")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "models.py")], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("\x1b", r.stdout)
        self.assertNotIn("\x07", r.stdout)
        self.assertIn("CAPSULE_MODEL=red", r.stdout)

    def test_route_error_output_is_sanitized(self):
        env = clean_env(CAPSULE_MODEL="\x1b[2Jevil\x1b[0m bad name")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "route_request.py"), "fix typo"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("\x1b", r.stderr)


class TestNoPyYaml(unittest.TestCase):
    def test_registry_tiers_without_yaml_matches_yaml(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        with_yaml = models.registry_tiers(root)
        with mock.patch.dict(sys.modules, {"yaml": None}):
            without = models.registry_tiers(root)
            self.assertEqual(models.resolve_model(bot="android-17", root=root, env={})["tier"], "pro")
        self.assertEqual(without, with_yaml)
        self.assertEqual(without["android-17"], "pro")

    def test_real_registry_without_yaml(self):
        expected = models.registry_tiers(ROOT)
        with mock.patch.dict(sys.modules, {"yaml": None}):
            self.assertEqual(models.registry_tiers(ROOT), expected)
        self.assertGreaterEqual(len(expected), 18)

    def test_mini_parse_agrees_with_yaml_on_hash_in_quotes(self):
        cases = [
            'tiers:\n  pro: "a#b"\n',
            "tiers:\n  pro: 'a #b'  # trailing\n",
            "tiers:\n  pro: a#b\n",
            "tiers:\n  pro: ab # comment\n",
            'tiers:\n  pro: "ab"   # c\nbots: {}\n',
            "# only comment\ntiers:\n  flash: x\n",
        ]
        for text in cases:
            self.assertEqual(models._mini_parse(text), yaml.safe_load(text), text)


class TestAtomicSet(unittest.TestCase):
    def test_set_writes_atomically_and_leaves_no_temp(self):
        tmp, root = make_root("tiers:\n  flash: haiku\n  pro: sonnet\n")
        self.addCleanup(tmp.cleanup)
        with mock.patch("os.replace", wraps=os.replace) as rep:
            models.set_model("pro", "p9", root=root, force=True)
        self.assertEqual(rep.call_count, 1)
        self.assertIn("pro: p9", (root / "config" / "models.yaml").read_text())
        self.assertEqual(sorted(p.name for p in (root / "config").iterdir() if p.suffix != ".log"), ["models.yaml"])

    def test_failed_write_keeps_original(self):
        tmp, root = make_root("tiers:\n  pro: sonnet\n")
        self.addCleanup(tmp.cleanup)
        with mock.patch("os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                models.set_model("pro", "p9", root=root, force=True)
        self.assertEqual((root / "config" / "models.yaml").read_text(), "tiers:\n  pro: sonnet\n")
        self.assertEqual(sorted(p.name for p in (root / "config").iterdir() if p.suffix != ".log"), ["models.yaml"])

    @unittest.skipIf(os.name == "nt", "symlinks")
    def test_refuses_symlinked_config(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        victim = root / "victim.yaml"
        victim.write_text("keep: 1\n")
        (root / "config" / "models.yaml").symlink_to(victim)
        with self.assertRaises(models.ModelsError):
            models.set_model("pro", "p9", root=root)
        self.assertEqual(victim.read_text(), "keep: 1\n")

    def test_set_rejects_bad_model(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        for bad in ("--x", "a\n", "a b"):
            with self.assertRaises(models.ModelsError):
                models.set_model("pro", bad, root=root)


if __name__ == "__main__":
    unittest.main()
