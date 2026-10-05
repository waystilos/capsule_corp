"""Regression tests for routing consistency and bot scaffolding wiring."""

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import route_request as rr  # noqa: E402
import scaffold_bot as sb  # noqa: E402


def registry_bots():
    data = yaml.safe_load((ROOT / "registry.yaml").read_text(encoding="utf-8"))
    return [d["name"] for d in data["bots"].values()]


class TestRouting(unittest.TestCase):
    def test_every_registry_bot_has_role_and_is_routable(self):
        routed_owners = {r["owner"] for r in rr.load_routes()["routes"]}
        for bot in registry_bots():
            self.assertIn(bot, rr.BOT_TO_ROLE, bot)
            self.assertIn(bot, rr.WORKFLOW_ROLE, bot)
            if bot not in rr.COORDINATORS:
                self.assertIn(bot, routed_owners, f"{bot} has no route")

    def test_grill_routes_to_beerus(self):
        res = rr.route_request("grill my code")
        self.assertEqual(res["status"], "routed")
        self.assertEqual(res["owner"], "beerus")

    def test_bug_check_routes_to_trunks(self):
        for text in ("check for bugs", "find bugs and faults in this module"):
            res = rr.route_request(text)
            self.assertEqual(res["owner"], "trunks", text)
            self.assertEqual(res["role"], "Reviewer")

    def test_outputs_are_self_consistent(self):
        for text in ("grill my code", "check for bugs", "fix the typo in the README",
                     "deconstruct epic architecture", "help me with this project",
                     "animate volleyball sprite frames", "rig the rive artboard"):
            res = rr.route_request(text)
            bots = [m.casefold() for s in res["suggested_workflow"] for m in re.findall(r"@([\w-]+)", s)]
            self.assertEqual(bots, res["handoff"], text)

    def test_needs_clarification_is_triage_with_whis_only(self):
        res = rr.route_request("help me with this project")
        self.assertEqual(res["status"], "needs_clarification")
        self.assertEqual(res["workflow_tier"], "triage")
        self.assertEqual(res["handoff"], ["whis"])
        self.assertEqual(len(res["suggested_workflow"]), 1)
        self.assertIn("@Whis", res["suggested_workflow"][0])


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        (self.tmp / "config").mkdir()
        (self.tmp / "bots").mkdir()
        shutil.copy(str(ROOT / "registry.yaml"), str(self.tmp / "registry.yaml"))
        shutil.copy(str(ROOT / "config" / "routing.yaml"), str(self.tmp / "config" / "routing.yaml"))

    def scaffold(self, name="gohan", tier="flash"):
        return sb.scaffold_bot(
            self.tmp, name, "Gohan (Analytics)", "Analyst", "desc", "jtbd",
            "- none", ["view_file"], "exit 0", tier)

    def test_archetypes_do_not_collide_with_existing_bots(self):
        existing = {n.replace("-", "_") for n in registry_bots()}
        for key in sb.DBZ_RESERVE_ARCHETYPES:
            self.assertNotIn(key.replace("-", "_"), existing, key)

    def test_scaffold_wires_registry_tier_routing_and_agent(self):
        self.scaffold(tier="flash")
        reg = yaml.safe_load((self.tmp / "registry.yaml").read_text(encoding="utf-8"))
        self.assertEqual(reg["bots"]["gohan"]["model_tier"], "flash")
        self.assertIn("gohan", reg["functional_envelope"]["tiers"]["flash"]["operatives"])
        routes = yaml.safe_load((self.tmp / "config" / "routing.yaml").read_text(encoding="utf-8"))["routes"]
        self.assertIn("gohan", [r["owner"] for r in routes])
        self.assertTrue((self.tmp / "bots" / "gohan.md").exists())
        agent = (self.tmp / ".claude" / "agents" / "gohan.md").read_text(encoding="utf-8")
        self.assertIn("model_tier: flash", agent)

    def test_tier_normalized_and_unknown_tier_rejected(self):
        self.scaffold(name="a-b", tier="PRO")
        reg = yaml.safe_load((self.tmp / "registry.yaml").read_text(encoding="utf-8"))
        self.assertIn("a_b", reg["functional_envelope"]["tiers"]["pro"]["operatives"])
        with self.assertRaises(ValueError):
            self.scaffold(name="zed", tier="ultra-max")
        self.assertFalse((self.tmp / "bots" / "zed.md").exists())

    def test_failure_rolls_back_everything(self):
        before_reg = (self.tmp / "registry.yaml").read_bytes()
        routing = self.tmp / "config" / "routing.yaml"
        # A colliding route owner makes the last step fail after the registry write.
        routing.write_text(
            routing.read_text(encoding="utf-8")
            + "  - intent: x\n    owner: gohan\n    keywords: [x]\n    handoff: [gohan]\n",
            encoding="utf-8",
        )
        before_route = routing.read_bytes()
        with self.assertRaises(ValueError):
            self.scaffold()
        self.assertEqual((self.tmp / "registry.yaml").read_bytes(), before_reg)
        self.assertEqual(routing.read_bytes(), before_route)
        self.assertFalse((self.tmp / "bots" / "gohan.md").exists())
        self.assertFalse((self.tmp / ".claude" / "agents" / "gohan.md").exists())

    def test_scaffolded_bot_is_routable_with_registry_role(self):
        self.scaffold()
        old = rr.CAPSULE_ROOT
        rr.CAPSULE_ROOT = self.tmp
        try:
            res = rr.route_request("ask gohan")
        finally:
            rr.CAPSULE_ROOT = old
        self.assertEqual(res["owner"], "gohan")
        self.assertEqual(res["role"], "Analyst")


if __name__ == "__main__":
    unittest.main()
