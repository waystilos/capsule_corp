import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import models  # noqa: E402

BIN = str(ROOT / "bin" / "capsule")


def make_root(config_text=None):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "config").mkdir()
    (root / "registry.yaml").write_text(
        'bots:\n  goku:\n    name: "goku"\n    model_tier: "pro"\n'
        '  trunks:\n    name: "trunks"\n    model_tier: "flash"\n'
        '  piccolo:\n    name: "piccolo"\n    model_tier: "pro"\n',
        encoding="utf-8",
    )
    if config_text is not None:
        (root / "config" / "models.yaml").write_text(config_text, encoding="utf-8")
    return tmp, root


def run(args, root, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CAPSULE_MODEL")}
    env["CAPSULE_RESOURCE_ROOT"] = str(root)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "models.py")] + args,
                          capture_output=True, text=True, env=env)


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.root = make_root("tiers:\n  flash: f1\n  pro: p1\n  premium: x1\nbots:\n  goku: gk\n")

    def tearDown(self):
        self.tmp.cleanup()

    def r(self, **kw):
        kw.setdefault("env", {})
        return models.resolve_model(root=self.root, **kw)

    def test_precedence_chain(self):
        env = {"CAPSULE_MODEL": "e1", "CAPSULE_MODEL_PRO": "e2"}
        self.assertEqual(self.r(bot="goku", cli_model="c", env=env)["source"], "cli:--model")
        self.assertEqual(self.r(bot="goku", env=env)["source"], "env:CAPSULE_MODEL")
        res = self.r(bot="goku", env={"CAPSULE_MODEL_PRO": "e2"})
        self.assertEqual((res["model"], res["source"]), ("e2", "env:CAPSULE_MODEL_PRO"))
        res = self.r(bot="goku")
        self.assertEqual((res["model"], res["source"]), ("gk", "config:bots.goku"))
        res = self.r(bot="trunks")
        self.assertEqual((res["model"], res["tier"]), ("f1", "flash"))

    def test_tier_env_only_matches_tier(self):
        self.assertEqual(self.r(bot="trunks", env={"CAPSULE_MODEL_PRO": "z"})["model"], "f1")

    def test_defaults_without_config(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        res = models.resolve_model(bot="trunks", root=root, env={})
        self.assertEqual((res["model"], res["tier"]), ("haiku", "flash"))
        self.assertEqual(models.resolve_model(tier="premium", root=root, env={})["model"], "opus")

    def test_bad_config_falls_back(self):
        tmp, root = make_root("tiers: [unclosed\n  : :\n")
        self.addCleanup(tmp.cleanup)
        cfg, warns = models.load_config(root)
        self.assertEqual(cfg["tiers"], models.DEFAULT_TIERS)
        self.assertTrue(warns)
        tmp2, root2 = make_root("- a\n- b\n")
        self.addCleanup(tmp2.cleanup)
        self.assertTrue(models.load_config(root2)[1])

    def test_unknown(self):
        with self.assertRaises(models.ModelsError):
            self.r(bot="nobody")
        with self.assertRaises(models.ModelsError):
            self.r(tier="ultra")

    def test_route_tier_rule(self):
        self.assertEqual(models.route_tier("small_fix", "pro")[0], "flash")
        self.assertEqual(models.route_tier("complex_epic", "pro")[0], "pro")
        self.assertEqual(models.route_tier("small_fix", "pro", escalate=True)[0], "premium")
        self.assertEqual(models.route_tier("small_fix", "pro", tier="pro")[0], "pro")
        self.assertIsNone(models.route_tier("standard_feature", "pro")[0])


class SetTests(unittest.TestCase):
    def test_set_preserves_and_refuses(self):
        tmp, root = make_root("# keep me\ntiers:\n  flash: haiku\n  pro: sonnet\nbots: {}\n")
        self.addCleanup(tmp.cleanup)
        p = root / "config" / "models.yaml"
        r = run(["set", "pro", "other"], root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--force", r.stderr)
        self.assertIn("sonnet", p.read_text())
        self.assertEqual(run(["set", "premium", "opus-x"], root).returncode, 0)
        self.assertEqual(run(["set", "pro", "other", "--force"], root).returncode, 0)
        text = p.read_text()
        self.assertIn("# keep me", text)
        self.assertIn("pro: other", text)
        self.assertIn("premium: opus-x", text)
        self.assertEqual(run(["set", "--bot", "goku", "gk"], root).returncode, 0)
        self.assertEqual(models.load_config(root)[0]["bots"], {"goku": "gk"})

    def test_set_unknown(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        self.assertEqual(run(["set", "bogus", "m"], root).returncode, 2)
        self.assertEqual(run(["set", "--bot", "nobody", "m"], root).returncode, 2)
        self.assertFalse((root / "config" / "models.yaml").exists())

    def test_show_bad_config_no_traceback(self):
        tmp, root = make_root("tiers: [x\n")
        self.addCleanup(tmp.cleanup)
        r = run([], root)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("warning", r.stderr)
        self.assertIn("haiku", r.stdout)


class CliTests(unittest.TestCase):
    def cap(self, args, env_extra=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CAPSULE_MODEL")}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, BIN] + args, capture_output=True, text=True, env=env)

    def test_route_json_includes_model(self):
        r = self.cap(["route", "--json", "fix typo"])
        d = json.loads(r.stdout)
        self.assertEqual(d["model_tier"], "flash")
        self.assertIn("model_source", d)
        self.assertTrue(d["model"])

    def test_route_env_and_flag(self):
        d = json.loads(self.cap(["route", "--json", "fix typo"], {"CAPSULE_MODEL_FLASH": "xx"}).stdout)
        self.assertEqual((d["model"], d["model_source"]), ("xx", "env:CAPSULE_MODEL_FLASH"))
        d = json.loads(self.cap(["route", "--json", "--model", "yy", "fix typo"], {"CAPSULE_MODEL": "xx"}).stdout)
        self.assertEqual(d["model"], "yy")
        d = json.loads(self.cap(["route", "--json", "--escalate", "fix typo"]).stdout)
        self.assertEqual(d["model_tier"], "premium")

    def test_route_text_and_bad_tier(self):
        self.assertIn("Model:", self.cap(["route", "fix typo"]).stdout)
        self.assertEqual(self.cap(["route", "--tier", "ultra", "fix typo"]).returncode, 2)

    def test_list_includes_model(self):
        r = self.cap(["list"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("MODEL", r.stdout)

    def test_models_command(self):
        r = self.cap(["models"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("flash", r.stdout)


if __name__ == "__main__":
    unittest.main()
