import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPSULE = str(ROOT / "bin" / "capsule")

from scripts.envelope import Envelope, EnvelopeError, load  # noqa: E402


def run(args, cwd=None, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("CAPSULE_MODEL")}
    e.update(env or {})
    return subprocess.run([sys.executable, CAPSULE] + args, cwd=cwd, env=e, capture_output=True, text=True)


class CheckRefTests(unittest.TestCase):
    def test_rejects_unsafe_refs(self):
        for bad in ("~/x", "~root/x", ".capsule/room.json", "./.capsule/x", ".git/config", ".GIT/config",
                    ".git", "file:x", "file:///etc/passwd", "x:y", "javascript:alert", "a/./b", "a/b/."):
            with self.subTest(bad=bad), self.assertRaises(EnvelopeError):
                Envelope.new("r").with_artifact("diff_reference", bad)

    def test_still_accepts_good_refs(self):
        for good in ("src/app.py", "HEAD~1..HEAD", "pkg.mod:Class", "Foo::bar", "./src/a.py", ".gitignore", "a/.capsule2/x"):
            with self.subTest(good=good):
                Envelope.new("r").with_artifact("diff_reference", good)


class ListJsonTests(unittest.TestCase):
    def test_list_json_is_pure_json_on_stdout(self):
        res = run(["list", "--json"])
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        bots = {b["bot"]: b for b in data["bots"]}
        self.assertIn("goku", bots)
        self.assertEqual(set(bots["goku"]), {"bot", "tier", "model", "source"})
        self.assertNotIn("ROSTER", res.stdout)

    def test_list_json_respects_env_model(self):
        data = json.loads(run(["list", "--json"], env={"CAPSULE_MODEL": "opus"}).stdout)
        self.assertTrue(all(b["model"] == "opus" for b in data["bots"]))


class ModelsBotViewTests(unittest.TestCase):
    def test_bot_view(self):
        res = run(["models", "--bot", "goku"])
        self.assertEqual(res.returncode, 0, res.stderr)
        for label in ("tier:", "registry model:", "resolved model:", "source:"):
            self.assertIn(label, res.stdout)

    def test_bot_view_json_and_unknown(self):
        data = json.loads(run(["models", "--bot", "cell", "--json"]).stdout)
        self.assertTrue(data["protected"])
        self.assertEqual(data["tier"], "pro")
        bad = run(["models", "--bot", "nobody"])
        self.assertEqual(bad.returncode, 2)


class ProtectedOverrideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "config").mkdir()
        shutil.copy(ROOT / "registry.yaml", self.tmp / "registry.yaml")
        shutil.copy(ROOT / "config" / "models.yaml", self.tmp / "config" / "models.yaml")
        self.env = {"CAPSULE_RESOURCE_ROOT": str(self.tmp)}

    def test_set_protected_downgrade_needs_force(self):
        res = run(["models", "set", "--bot", "android-17", "haiku"], env=self.env)
        self.assertEqual(res.returncode, 2)
        self.assertIn("--force", res.stderr)
        self.assertNotIn("android-17", (self.tmp / "config" / "models.yaml").read_text().split("bots:")[1])
        forced = run(["models", "set", "--bot", "android-17", "haiku", "--force"], env=self.env)
        self.assertEqual(forced.returncode, 0, forced.stderr)

    def test_set_protected_upgrade_and_unprotected_ok(self):
        self.assertEqual(run(["models", "set", "--bot", "cell", "opus"], env=self.env).returncode, 0)
        self.assertEqual(run(["models", "set", "--bot", "goku", "haiku"], env=self.env).returncode, 0)

    def test_route_override_warning(self):
        res = run(["route", "--json", "security audit of auth secrets"], env={"CAPSULE_MODEL": "haiku"})
        data = json.loads(res.stdout)
        self.assertIn("android-17", data["override_warning"])
        self.assertIn("haiku", data["override_warning"])
        human = run(["route", "--model", "haiku", "security audit of auth secrets"])
        self.assertIn("WARN: android-17", human.stderr)
        self.assertNotIn("WARN:", human.stdout)

    def test_no_override_no_warning(self):
        data = json.loads(run(["route", "--json", "security audit of auth secrets"]).stdout)
        self.assertNotIn("override_warning", data)


class PersistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_not_persisted_by_default(self):
        res = run(["route", "--json", "fix a typo in the readme"], cwd=str(self.tmp))
        self.assertNotIn("envelope_ref", json.loads(res.stdout))
        self.assertFalse((self.tmp / ".capsule").exists())

    def test_persist_json_and_human(self):
        data = json.loads(run(["route", "--json", "--persist", "fix a typo in the readme"], cwd=str(self.tmp)).stdout)
        ref = data["envelope_ref"]
        self.assertTrue(ref.startswith(".capsule/envelopes/"))
        env = load(self.tmp / ref)
        self.assertEqual(env.root_hash, data["root_hash"])
        human = run(["route", "--persist", "fix a typo in the readme"], cwd=str(self.tmp))
        self.assertIn(f"Envelope: {ref}", human.stdout)

    def test_concurrent_persist(self):
        reqs = [f"fix a typo in readme number {i}" for i in range(8)]
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda r: run(["route", "--json", "--persist", r], cwd=str(self.tmp)), reqs))
        refs = []
        for res in results:
            self.assertEqual(res.returncode, 0, res.stderr)
            refs.append(json.loads(res.stdout)["envelope_ref"])
        self.assertEqual(len(set(refs)), len(reqs))
        for ref, req in zip(refs, reqs):
            self.assertEqual(load(self.tmp / ref).root_request, req)


if __name__ == "__main__":
    unittest.main()
