"""Machine-checked contracts: every routed chain satisfies each hop's `requires`."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import envelope as ev  # noqa: E402
from scripts import route_request as rr  # noqa: E402

REGISTRY = ev.load_registry(ROOT)
ROUTES = rr.load_routes()["routes"]


def run_chain(chain, entry):
    """Walk a chain with the REAL envelope code. Returns the final envelope or raises HopError."""
    env = ev.Envelope.new("some user request", {name: f"ref/{name}" for name in entry})
    for bot in chain:
        provides = ev.contract_of(bot, REGISTRY)["provides"]
        env = env.record_hop(bot, REGISTRY, {p: f"ref/{p}" for p in provides})
    return env


class TestRegistryContracts(unittest.TestCase):
    def test_every_contract_is_machine_checkable(self):
        for key, spec in REGISTRY["bots"].items():
            inp, out = spec["input_contract"], spec["output_contract"]
            self.assertIsInstance(inp, dict, key)
            self.assertIsInstance(out, dict, key)
            self.assertTrue(inp["requires"] and inp["description"], key)
            self.assertTrue(out["provides"] and out["description"], key)
            ev.contract_of(spec["name"], REGISTRY)  # validates field names

    def test_markdown_front_matter_mirrors_registry(self):
        for key, spec in REGISTRY["bots"].items():
            for folder in ("bots", ".claude/agents"):
                path = ROOT / folder / f"{key if folder == 'bots' else spec['name']}.md"
                if not path.exists():
                    continue  # .claude/agents files are renamed/synced separately
                fm = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
                self.assertEqual(fm["input_contract"]["requires"], spec["input_contract"]["requires"], path.name)
                self.assertEqual(fm["output_contract"]["provides"], spec["output_contract"]["provides"], path.name)

    def test_king_kai_is_shift_based_and_declares_entry_fields(self):
        req = ev.contract_of("king-kai", REGISTRY)["requires"]
        self.assertEqual(set(req), {"shift_id", "claimed_files", "active_diff_ref"})
        route = next(r for r in ROUTES if r["owner"] == "king-kai")
        self.assertEqual(set(route["entry"]), set(req))


class TestEveryRouteSatisfiesContracts(unittest.TestCase):
    def test_every_route_handoff_is_satisfiable_with_declared_entry(self):
        for route in ROUTES:
            with self.subTest(route=route["intent"]):
                run_chain(route["handoff"], route.get("entry") or [])

    def test_every_dynamic_chain_is_satisfiable(self):
        for route in ROUTES:
            for text in ("fix a thing", "plan the epic architecture", "add a thing"):
                tier, _wf, chain = rr.determine_workflow(text, route["owner"], route["handoff"])
                with self.subTest(route=route["intent"], tier=tier):
                    run_chain(chain, route.get("entry") or [])

    def test_missing_entry_field_is_actually_rejected(self):
        """Guards against a self-enforcing check: drop an entry field and the real validator must fail."""
        for route in ROUTES:
            for field in route.get("entry") or []:
                rest = [e for e in route["entry"] if e != field]
                with self.subTest(route=route["intent"], dropped=field):
                    with self.assertRaises(ev.HopError):
                        run_chain(route["handoff"], rest)

    def test_no_dead_entry_fields(self):
        """Every declared entry field is required by some hop that no earlier hop provides."""
        for route in ROUTES:
            provided = set()
            needed = set()
            for bot in route["handoff"]:
                c = ev.contract_of(bot, REGISTRY)
                needed |= {r for r in c["requires"] if r not in provided and r not in ev.SEEDED_FIELDS}
                provided |= set(c["provides"])
            self.assertEqual(set(route.get("entry") or []), needed, route["intent"])

    def test_known_hops(self):
        by_owner = {r["owner"]: r for r in ROUTES if r["intent"] not in ("idea_validation",)}
        # roshi provides target_files for goku; vegeta provides diff_reference for android-17/trunks
        self.assertIn("target_files", ev.contract_of("roshi", REGISTRY)["provides"])
        self.assertIn("diff_reference", ev.contract_of("vegeta", REGISTRY)["provides"])
        self.assertNotIn("target_files", by_owner["roshi"].get("entry", []))
        self.assertNotIn("diff_reference", by_owner["vegeta"].get("entry", []))
        # cell cannot supply a diff, so the caller declares it
        self.assertIn("diff_reference", by_owner["cell"]["entry"])


class TestRouteJsonEnvelope(unittest.TestCase):
    def cap(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "route_request.py")] + list(args),
                              capture_output=True, text=True)

    def test_json_is_envelope_shaped(self):
        r = self.cap("--json", "fix the typo in the README")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["root_request"], "fix the typo in the README")
        self.assertEqual(out["root_hash"], ev.hash_root(out["root_request"]))
        self.assertEqual(out["ledger"], [])
        self.assertEqual(out["artifacts"], {})
        self.assertEqual([h["bot"] for h in out["hops"]], out["handoff"])
        for h in out["hops"]:
            self.assertEqual(set(h), {"bot", "model", "tier"})
        self.assertEqual(out["entry_required"], ["target_files"])
        for key in ("status", "owner", "workflow_tier", "suggested_workflow", "model", "model_tier"):
            self.assertIn(key, out)
        ev.Envelope.from_dict({k: out[k] for k in ("root_request", "root_hash", "ledger", "artifacts")})

    def test_red_team_the_api_is_not_a_tie(self):
        res = rr.route_request("red team the api")
        self.assertEqual(res["status"], "routed")
        self.assertEqual(res["owner"], "cell")

    def test_small_fix_keeps_verification_step(self):
        res = rr.route_request("fix the typo in the README")
        self.assertEqual(res["workflow_tier"], "small_fix")
        self.assertEqual(res["handoff"], ["goku", "trunks"])
        self.assertEqual(res["suggested_workflow"][-1], rr.VERIFICATION_STEP)

    def test_hop_models_come_from_resolve_model(self):
        res = rr.attach_model(rr.route_request("add a user profile feature"))
        self.assertEqual(res["hops"][0]["bot"], res["handoff"][0])
        self.assertTrue(all(h["model"] and h["tier"] for h in res["hops"]))


if __name__ == "__main__":
    unittest.main()
