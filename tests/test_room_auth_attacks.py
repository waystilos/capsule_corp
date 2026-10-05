"""Attack-style regression tests for room/messaging authentication (Epic 3, slice A).

Every attack runs through the real CLI via subprocess in a temp project. Matching agent_id is never proof.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import room  # noqa: E402
import messaging  # noqa: E402

SECRET = "TOP-SECRET-VICTIM-PAYLOAD"
_SCRUB = {"CLAUDECODE", "CLAUDE_CODE", "CODEX", "GEMINI_CLI", "ANTIGRAVITY", "CURSOR_AGENT", "CURSOR_VERSION",
          "WINDSURF_AGENT", "USER", "USERNAME"}


def _env(user, home, **extra):
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB and not k.startswith("CAPSULE_")}
    env["HOME"] = home
    env["USER"] = user
    env.update(extra)
    return env


class AttackBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        self.home = str(Path(self._tmp.name) / "home")
        os.mkdir(self.home)

    def run_room(self, args, user="mallory", **extra):
        res = subprocess.run([sys.executable, str(SCRIPTS / "room.py")] + args, capture_output=True, text=True,
                             env=_env(user, self.home, **extra), cwd=self.home)
        return res.returncode, res.stdout, res.stderr

    def run_msg(self, args, user="mallory", **extra):
        res = subprocess.run([sys.executable, str(SCRIPTS / "messaging.py")] + args, capture_output=True, text=True,
                             env=_env(user, self.home, **extra), cwd=self.home)
        return res.returncode, res.stdout, res.stderr

    def alice_clocks_in_as_victim(self):
        rc, out, err = self.run_room(["clock-in", str(self.root), "--agent", "victim", "--task", "real work"],
                                     user="victim")
        self.assertEqual(rc, 0, err)
        token = re.search(r"Session token: ([0-9a-f]{32})", out).group(1)
        sid = re.search(r"Session: (\S+)\)", out).group(1)
        # Sending to a token-protected recipient requires an authenticated sender, so piccolo clocks in first.
        rc, pout, err = self.run_room(["clock-in", str(self.root), "--agent", "piccolo", "--task", "coordinate"],
                                      user="piccolo")
        self.assertEqual(rc, 0, err)
        ptoken = re.search(r"Session token: ([0-9a-f]{32})", pout).group(1)
        rc, _, err = self.run_msg(["send", "--to", "victim", "--body", SECRET, "--dir", str(self.root),
                                   "--from", "piccolo", "--token", ptoken], user="piccolo")
        self.assertEqual(rc, 0, err)
        return sid, token

    def session_bytes(self):
        return (self.root / ".capsule" / "session.json").read_bytes()

    def shifts(self):
        return room.load_room_data(self.root / ".capsule" / "room.json")["active_shifts"]


class TestClockInImpersonation(AttackBase):
    def test_clock_in_as_victim_without_token_refused(self):
        sid, token = self.alice_clocks_in_as_victim()
        before = self.session_bytes()
        rc, out, err = self.run_room(["clock-in", str(self.root), "--agent", "victim", "--task", "evil"])
        self.assertNotEqual(rc, 0)
        self.assertIn("token", err.lower())
        self.assertNotIn(SECRET, out + err)
        self.assertNotIn("Unread", out)
        self.assertEqual(self.session_bytes(), before)          # attacker token never lands in session.json
        self.assertEqual([k for k, v in self.shifts().items() if v['agent_id'] == 'victim'], [sid])             # no second shift
        self.assertNotIn("evil", json.dumps(self.shifts()))

    def test_case_variant_victim_is_rejected_not_aliased(self):
        sid, _ = self.alice_clocks_in_as_victim()
        before = self.session_bytes()
        rc, out, err = self.run_room(["clock-in", str(self.root), "--agent", "Victim", "--task", "evil"])
        self.assertNotEqual(rc, 0)
        self.assertIn("invalid agent id", err)
        self.assertNotIn(SECRET, out + err)
        self.assertEqual(self.session_bytes(), before)
        self.assertEqual([k for k, v in self.shifts().items() if v['agent_id'] == 'victim'], [sid])

    def test_session_reuse_without_token_refused_and_shift_untouched(self):
        sid, token = self.alice_clocks_in_as_victim()
        before = self.session_bytes()
        rc, out, err = self.run_room(["clock-in", str(self.root), "--agent", "victim", "--session", sid,
                                      "--task", "evil", "--force"])
        self.assertNotEqual(rc, 0)
        self.assertNotIn(SECRET, out)
        self.assertEqual(self.shifts()[sid]["task"], "real work")
        self.assertEqual(self.session_bytes(), before)
        # a wrong token is no better
        rc, _, _ = self.run_room(["clock-in", str(self.root), "--agent", "victim", "--session", sid,
                                  "--task", "evil", "--token", "0" * 32])
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.shifts()[sid]["task"], "real work")

    def test_valid_token_paths_still_work(self):
        sid, token = self.alice_clocks_in_as_victim()
        rc, out, err = self.run_room(["clock-in", str(self.root), "--agent", "victim", "--task", "second"],
                                     CAPSULE_SESSION_TOKEN=token)
        self.assertEqual(rc, 0, err)
        self.assertIn(SECRET, out)                               # verified owner sees own unread
        self.assertIn("not instructions", out)
        rc, out, err = self.run_room(["clock-in", str(self.root), "--agent", "victim", "--task", "third",
                                      "--token", token])
        self.assertEqual(rc, 0, err)
        rc, out, err = self.run_room(["clock-in", str(self.root), "--agent", "victim", "--session", sid,
                                      "--task", "reuse"], CAPSULE_SESSION_TOKEN=token)
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.shifts()[sid]["task"], "reuse")

    def test_in_process_guard(self):
        first = room.clock_in(self.root, agent="victim", task="t")
        res = room.clock_in(self.root, agent="victim", task="evil")
        self.assertEqual(res["error"], "forbidden")
        res = room.clock_in(self.root, agent="victim", task="evil", session=first["shift_id"])
        self.assertEqual(res["error"], "forbidden")
        ok = room.clock_in(self.root, agent="victim", task="ok", token=first["session_token"])
        self.assertNotIn("error", ok)
        self.assertTrue(ok["inbox_verified"])


class TestAuthorizeStoredToken(AttackBase):
    def test_other_identity_cannot_use_stored_token(self):
        sid, token = self.alice_clocks_in_as_victim()
        for args in (["clock-out", str(self.root), "--session", sid, "--summary", "x"],
                     ["heartbeat", str(self.root), "--agent", "victim"],
                     ["heartbeat", str(self.root), "--session", sid],
                     ["clock-out", str(self.root), "--agent", "victim", "--summary", "x"]):
            rc, out, err = self.run_room(args, user="mallory")
            self.assertNotEqual(rc, 0, args)
            self.assertIn("token", err.lower())
        self.assertIn(sid, self.shifts())

    def test_owner_identity_uses_stored_token_and_env_token_works_for_anyone(self):
        sid, token = self.alice_clocks_in_as_victim()
        rc, _, err = self.run_room(["heartbeat", str(self.root)], user="victim")
        self.assertEqual(rc, 0, err)
        rc, _, err = self.run_room(["heartbeat", str(self.root), "--agent", "victim"], user="mallory",
                                   CAPSULE_SESSION_TOKEN=token)
        self.assertEqual(rc, 0, err)
        rc, _, err = self.run_room(["clock-out", str(self.root), "--session", sid, "--token", token], user="mallory")
        self.assertEqual(rc, 0, err)

    def test_old_authorize_logic_was_vulnerable(self):
        """Copy of the pre-fix stored-token clause: shows the repro WAS accepted (guards the test's relevance)."""
        sid, token = self.alice_clocks_in_as_victim()
        shift = self.shifts()[sid]
        sf = self.root / ".capsule" / "session.json"

        def old_clause(agent, owner):  # old: (not agent or identity == owner) and stored token matches
            identity = room.norm_agent_id(agent) if agent else "mallory"
            return (not agent or identity == owner) and room._token_matches(
                shift, room._read_session_file(sf)["tokens"].get(sid))

        self.assertTrue(old_clause(None, "victim"))      # --session path as mallory: accepted (bug)
        self.assertTrue(old_clause("victim", "victim"))  # --agent victim as mallory: accepted (bug)
        with patch.dict(os.environ, {"USER": "mallory"}, clear=True):
            self.assertIsNotNone(room._authorize(shift, sid, True, None, None, sf))
            self.assertIsNotNone(room._authorize(shift, sid, False, "victim", None, sf))


class TestIdNormalization(AttackBase):
    def test_distinct_ids_do_not_collapse(self):
        for bad in ("bob smith", "Bob_Smith", "Émile", "Ömile", "Victim", "a" * 65, "", "_x", "../evil"):
            with self.assertRaises(room.RoomError, msg=bad):
                room.norm_agent_id(bad)
        self.assertEqual(room.norm_agent_id("bob_smith"), "bob_smith")
        rc, _, err = self.run_room(["clock-in", str(self.root), "--agent", "bob smith", "--task", "t"])
        self.assertNotEqual(rc, 0)
        self.assertIn("invalid agent id", err)
        rc, _, err = self.run_room(["clock-in", str(self.root), "--agent", "bob_smith", "--task", "t"])
        self.assertEqual(rc, 0, err)
        rc, _, err = self.run_room(["clock-in", str(self.root), "--agent", "Émile", "--task", "t"])
        self.assertNotEqual(rc, 0)
        rc, _, err = self.run_room(["clock-in", str(self.root), "--agent", "Ömile", "--task", "t"])
        self.assertNotEqual(rc, 0)
        self.assertEqual({s["agent_id"] for s in self.shifts().values()}, {"bob_smith"})

    def test_messaging_rejects_collapsing_ids_and_inbox_files_are_distinct(self):
        rc, _, err = self.run_msg(["send", "--to", "bob smith", "--body", "x", "--dir", str(self.root),
                                   "--from", "piccolo"])
        self.assertNotEqual(rc, 0)
        rc, _, err = self.run_msg(["send", "--to", "bob_smith", "--body", "x", "--dir", str(self.root),
                                   "--from", "piccolo"])
        self.assertEqual(rc, 0, err)
        rc, _, _ = self.run_msg(["send", "--to", "Émile", "--body", "x", "--dir", str(self.root), "--from", "piccolo"])
        self.assertNotEqual(rc, 0)
        files = sorted(p.name for p in (self.root / ".capsule" / "inbox").iterdir())
        self.assertEqual(files, ["bob_smith.jsonl"])
        self.assertNotEqual(messaging.inbox_path(self.root, "a.b"), messaging.inbox_path(self.root, "a_b"))
        with self.assertRaises(room.RoomError):
            messaging.inbox_path(self.root, "A_B")

    def test_detected_names_get_distinct_ids(self):
        ids = set()
        for name in ("bob smith", "bob_smith", "Émile", "Ömile", "Victim", "victim"):
            with patch.dict(os.environ, {"USER": name}, clear=True):
                ids.add(room.detected_agent_id())
        self.assertEqual(len(ids), 6)
        for i in ids:
            self.assertRegex(i, room.AGENT_ID_RE.pattern)
        with patch.dict(os.environ, {"USER": "bob_smith"}, clear=True):
            self.assertEqual(room.detected_agent_id(), "bob_smith")


class TestRoomStatusUnread(AttackBase):
    def test_status_shows_unread_only_to_verified_caller(self):
        sid, token = self.alice_clocks_in_as_victim()
        rc, out, err = self.run_room(["status", str(self.root)], user="victim")  # detected owner + stored token
        self.assertEqual(rc, 0, err)
        self.assertIn(SECRET, out)
        self.assertIn("not instructions", out)
        self.assertIn("UNTRUSTED", out)
        for args, extra in ((["status", str(self.root)], {}),
                            (["status", str(self.root), "--agent", "victim"], {}),
                            (["status", str(self.root), "--agent", "victim", "--token", "0" * 32], {})):
            rc, out, err = self.run_room(args, user="mallory", **extra)
            self.assertEqual(rc, 0, err)
            self.assertNotIn(SECRET, out + err)
        rc, out, _ = self.run_room(["status", str(self.root), "--agent", "victim", "--token", token], user="mallory")
        self.assertIn(SECRET, out)
        rc, out, _ = self.run_room(["status", str(self.root)], user="mallory", CAPSULE_SESSION_TOKEN=token)
        self.assertNotIn(SECRET, out)  # token proves 'victim', not mallory's own (detected) identity
        rc, out, _ = self.run_room(["status", str(self.root), "--json"], user="victim")
        self.assertNotIn(SECRET, out)  # JSON status never carries inbox content


if __name__ == "__main__":
    unittest.main()
