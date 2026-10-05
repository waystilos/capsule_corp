#!/usr/bin/env python3
"""Regression tests for Cell's C9-C16 findings (room/messaging DoS, unsafe reads, claim aliasing). Temp dirs only."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unicodedata
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = CAPSULE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import messaging  # noqa: E402
import room  # noqa: E402
from messaging import MessagingError, ack_message, read_inbox, send_message  # noqa: E402
from room import RoomCorruptError  # noqa: E402

CODEX = {"CODEX": "1"}


def _shift(i, agent=None, files=None, token_hash=None, **extra):
    now = datetime.now(timezone.utc).isoformat()
    s = {"shift_id": f"s{i}", "agent_id": agent or f"agent{i}", "agent_name": "n", "task": "t",
         "files": files or [], "clocked_in_at": now, "last_seen_at": now}
    if token_hash:
        s["token_hash"] = token_hash
    s.update(extra)
    return s


def _write_room(root, shifts):
    (root / ".capsule").mkdir(exist_ok=True)
    (root / ".capsule" / "room.json").write_text(
        json.dumps({"active_shifts": {s["shift_id"]: s for s in shifts}, "history": []}), encoding="utf-8")


def run_with_timeout(fn, timeout=20):
    box = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - surfaced to the test
            box["error"] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise AssertionError("operation hung (blocked on a special file?)")
    if "error" in box:
        raise box["error"]
    return box.get("value")


class TestC9Caps(unittest.TestCase):
    def test_total_active_shift_cap(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            _write_room(root, [_shift(i) for i in range(room.MAX_ACTIVE_SHIFTS)])
            res = room.clock_in(root, agent="newcomer", task="t")
            self.assertEqual(res.get("error"), "shift_cap")
            self.assertIn("full", res["message"])

    def test_per_agent_cap(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            for _ in range(room.MAX_SHIFTS_PER_AGENT):
                self.assertNotIn("error", room.clock_in(root, agent="codex", task="t"))
            res = room.clock_in(root, agent="codex", task="t")
            self.assertEqual(res.get("error"), "shift_cap")
            self.assertEqual(len(room.load_room_data(root / ".capsule" / "room.json")["active_shifts"]),
                             room.MAX_SHIFTS_PER_AGENT)

    def test_oversized_room_json_refused_without_backup_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule").mkdir()
            rj = root / ".capsule" / "room.json"
            with open(rj, "wb") as f:
                f.truncate(room.MAX_ROOM_BYTES + 1)  # sparse
            with self.assertRaises(RoomCorruptError) as cm:
                room.load_room_data(rj)
            self.assertIn("too large", str(cm.exception))
            self.assertEqual(list((root / ".capsule").glob("room.json.corrupt-*")), [])

    def test_render_is_capped(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            _write_room(root, [_shift(i, files=[f"f{i}.py"]) for i in range(400)])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                room.print_room(root)
            text = out.getvalue()
            self.assertIn("400 active sessions", text)
            self.assertIn(f"{400 - room.MAX_RENDER_SHIFTS} more active session(s) not shown", text)
            self.assertLess(len(text), 100_000)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                room.print_room(root, as_json=True)
            view = json.loads(out.getvalue())
            self.assertEqual(len(view["active_shifts"]), room.MAX_RENDER_SHIFTS)
            self.assertEqual(view["active_omitted"], 400 - room.MAX_RENDER_SHIFTS)

    def test_clock_in_time_is_bounded_at_cap(self):
        import time
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            _write_room(root, [_shift(i, files=[f"d{i}/f{j}" for j in range(room.MAX_CLAIMS)])
                               for i in range(room.MAX_ACTIVE_SHIFTS - 1)])
            t0 = time.time()
            room.clock_in(root, agent="late", task="t", files=["z/a.py"])
            self.assertLess(time.time() - t0, 10)


class TestC10SafeReads(unittest.TestCase):
    def test_room_json_symlink_not_followed_or_copied(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule").mkdir()
            target = root / "big.bin"
            with open(target, "wb") as f:
                f.truncate(300 * 1024 * 1024)  # sparse
            os.symlink(str(target), str(root / ".capsule" / "room.json"))
            with self.assertRaises(RoomCorruptError):
                room.load_room_data(root / ".capsule" / "room.json")
            self.assertEqual(list((root / ".capsule").glob("room.json.corrupt-*")), [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs FIFOs")
    def test_room_json_fifo_does_not_hang(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule").mkdir()
            os.mkfifo(str(root / ".capsule" / "room.json"))
            with self.assertRaises(RoomCorruptError):
                run_with_timeout(lambda: room.load_room_data(root / ".capsule" / "room.json"))
            res = subprocess.run([sys.executable, str(SCRIPTS / "room.py"), "status", str(root)],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(res.returncode, 1)
            self.assertIn("not a regular file", res.stderr)

    def test_session_json_symlink_and_fifo_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule").mkdir()
            secret = root / "secret.json"
            secret.write_text(json.dumps({"tokens": {"s": "tok"}}), encoding="utf-8")
            os.symlink(str(secret), str(root / ".capsule" / "session.json"))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(room._read_session_file(root / ".capsule" / "session.json")["tokens"], {})
            if hasattr(os, "mkfifo"):
                os.unlink(str(root / ".capsule" / "session.json"))
                os.mkfifo(str(root / ".capsule" / "session.json"))
                with contextlib.redirect_stderr(io.StringIO()):
                    tokens = run_with_timeout(lambda: room._read_session_file(root / ".capsule" / "session.json"))
                self.assertEqual(tokens["tokens"], {})

    def test_inbox_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule" / "inbox").mkdir(parents=True)
            target = root / "t.jsonl"
            target.write_text('{"id":"msg_0000000000000001","body":"x"}\n', encoding="utf-8")
            os.symlink(str(target), str(root / ".capsule" / "inbox" / "goku.jsonl"))
            with self.assertRaises(MessagingError):
                read_inbox(root, "goku")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs FIFOs")
    def test_inbox_fifo_refused_without_hanging(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule" / "inbox").mkdir(parents=True)
            os.mkfifo(str(root / ".capsule" / "inbox" / "goku.jsonl"))
            with self.assertRaises(MessagingError):
                run_with_timeout(lambda: read_inbox(root, "goku"))

    def test_envelope_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root / "e.json"
            real.write_text("{}", encoding="utf-8")
            link = root / "link.json"
            os.symlink(str(real), str(link))
            with self.assertRaises(MessagingError):
                messaging.read_envelope(str(link))
            self.assertEqual(len(messaging.read_envelope(str(real))), 2)


class TestC11InboxFlood(unittest.TestCase):
    def _fill(self, root, agent, n, acked):
        f = root / ".capsule" / "inbox" / f"{agent}.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as fh:
            for i in range(n):
                mid = "msg_%016x" % (i + 1)
                fh.write(json.dumps({"id": mid, "from": "p", "to": agent, "body": "y" * 2000}) + "\n")
                if acked:
                    fh.write(json.dumps({"ack": mid}) + "\n")

    def test_full_inbox_recovers_after_ack_automatically(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._fill(root, "victim", messaging.MAX_INBOX_FILE_BYTES // 2000 + 5, acked=True)
            m = send_message(root, "victim", body="after ack", sender="p")
            msgs = read_inbox(root, "victim")
            self.assertEqual([x["id"] for x in msgs], [m["id"]])  # acked history compacted away
            self.assertLess((root / ".capsule/inbox/victim.jsonl").stat().st_size, 10_000)

    def test_unacked_full_inbox_still_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._fill(root, "victim", messaging.MAX_INBOX_FILE_BYTES // 2000 + 5, acked=False)
            with self.assertRaises(MessagingError) as cm:
                send_message(root, "victim", body="x", sender="p")
            self.assertIn("full", str(cm.exception))

    @patch.dict(os.environ, {"CODEX": "1"})
    def test_compact_command(self):
        with tempfile.TemporaryDirectory() as d, patch.object(messaging, "detected_agent_id", return_value="goku"):
            root = Path(d)
            a = send_message(root, "goku", body="a", sender="p")
            b = send_message(root, "goku", body="b", sender="p")
            ack_message(root, "goku", a["id"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = messaging.main(["inbox", "--agent", "goku", "--compact", "--dir", str(root)])
            self.assertEqual(rc, 0)
            self.assertIn("removed 1", out.getvalue())
            self.assertEqual([m["id"] for m in read_inbox(root, "goku")], [b["id"]])
            self.assertEqual(len((root / ".capsule/inbox/goku.jsonl").read_text().splitlines()), 1)

    def test_compact_needs_token_for_tokened_agent(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            s = room.clock_in(root, agent="victim", task="t")
            (root / ".capsule" / "session.json").unlink()
            with self.assertRaises(MessagingError):
                messaging.compact_inbox(root, "victim")
            self.assertEqual(messaging.compact_inbox(root, "victim", token=s["session_token"]), 0)

    def test_per_sender_rate_limit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(messaging, "RATE_PER_SENDER", 3):
                for _ in range(3):
                    send_message(root, "goku", body="x", sender="spammer")
                with self.assertRaises(MessagingError) as cm:
                    send_message(root, "goku", body="x", sender="spammer")
                self.assertIn("rate limit", str(cm.exception))
                send_message(root, "goku", body="x", sender="someone-else")  # other senders unaffected

    def test_global_rate_limit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(messaging, "RATE_GLOBAL", 3):
                for i in range(3):
                    send_message(root, "goku", body="x", sender=f"s{i}")
                with self.assertRaises(MessagingError):
                    send_message(root, "goku", body="x", sender="s9")

    def test_sending_to_token_protected_recipient_needs_authenticated_sender(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            room.clock_in(root, agent="victim", task="t")
            with self.assertRaises(MessagingError) as cm:
                send_message(root, "victim", body="lockout", sender="mallory")
            self.assertIn("authenticate", str(cm.exception))
            self.assertEqual(read_inbox(root, "victim"), [])
            sender = room.clock_in(root, agent="friend", task="t")
            m = send_message(root, "victim", body="hi", sender="friend", token=sender["session_token"])
            self.assertEqual(m["auth"], "token")

    def test_global_inbox_file_cap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(messaging, "MAX_INBOX_FILES", 3):
                for i in range(3):
                    send_message(root, f"r{i}", body="x", sender="p")
                with self.assertRaises(MessagingError) as cm:
                    send_message(root, "r9", body="x", sender="p")
                self.assertIn("inbox store is full", str(cm.exception))
                send_message(root, "r0", body="existing inbox still works", sender="p")

    def test_envelope_store_cap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(messaging, "MAX_ENVELOPE_FILES", 2):
                for i in range(2):
                    messaging.store_raw_envelope(root, json.dumps({"i": i}).encode())
                with self.assertRaises(MessagingError):
                    messaging.store_raw_envelope(root, b'{"i": 99}')
                messaging.store_raw_envelope(root, json.dumps({"i": 0}).encode())  # already stored: fine


class TestC12EnvelopeBeforeLock(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs FIFOs")
    def test_fifo_envelope_refused_and_lock_not_held(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fifo = root / "env.json"
            os.mkfifo(str(fifo))
            with self.assertRaises(MessagingError):
                run_with_timeout(lambda: send_message(root, "goku", envelope=str(fifo), sender="p"))
            # the room lock is free: a clock-in completes promptly
            with patch.dict(os.environ, CODEX, clear=True):
                res = run_with_timeout(lambda: room.clock_in(root, agent="codex", task="t"))
            self.assertNotIn("error", res)

    def test_envelope_read_happens_before_lock(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            env = root / "e.json"
            env.write_text("{}", encoding="utf-8")
            order = []
            real_read, real_lock = messaging.read_envelope, messaging.room_lock

            def spy_read(p):
                order.append("read")
                return real_read(p)

            @contextlib.contextmanager
            def spy_lock(r):
                order.append("lock")
                with real_lock(r):
                    yield

            with patch.object(messaging, "read_envelope", spy_read), patch.object(messaging, "room_lock", spy_lock):
                send_message(root, "goku", envelope=str(env), sender="p")
            self.assertEqual(order, ["read", "lock"])


class TestC13HandoffRotation(unittest.TestCase):
    def test_handoffs_rotated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inbox = root / ".capsule" / "inbox"
            inbox.mkdir(parents=True)
            log = inbox / "_handoffs.jsonl"
            log.write_text("x" * (room.MAX_HANDOFF_BYTES + 1), encoding="utf-8")
            room._archive_handoff(root, {"agent_id": "a", "shift_id": "s", "summary": "done"})
            self.assertTrue((inbox / "_handoffs.jsonl.1").exists())
            self.assertLess(log.stat().st_size, 2000)
            self.assertIn("done", log.read_text(encoding="utf-8"))


class TestC14UnreadableTimestamps(unittest.TestCase):
    def test_garbage_and_integer_timestamps_expire(self):
        for bad in ("garbage", 12345, ["x"], None):
            data = {"active_shifts": {"s": {"agent_id": "a", "last_seen_at": bad, "clocked_in_at": bad}}, "history": []}
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertTrue(room.prune_stale_shifts(data), bad)
            self.assertEqual(data["active_shifts"], {}, bad)
            self.assertEqual(len(data["history"]), 1)

    def test_fresh_shift_survives(self):
        data = {"active_shifts": {"s": _shift(1)}, "history": []}
        room.prune_stale_shifts(data)
        self.assertIn("s", data["active_shifts"])


class TestC15ClaimAliasing(unittest.TestCase):
    def test_nfc_nfd_claims_collide(self):
        nfc = unicodedata.normalize("NFC", "src/é.py")
        nfd = unicodedata.normalize("NFD", "src/é.py")
        self.assertNotEqual(nfc, nfd)
        self.assertEqual(room.normalize_claim(nfc), room.normalize_claim(nfd))
        shifts = {"s1": {"files": [nfc], "agent_id": "a"}}
        self.assertTrue(room.check_file_conflicts(shifts, [nfd]))
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            self.assertNotIn("error", room.clock_in(root, agent="a1", task="t", files=[nfc]))
            self.assertEqual(room.clock_in(root, agent="b1", task="t", files=[nfd]).get("error"), "file_conflict")

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_symlink_claim_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            root = Path(d)
            os.symlink(outside, str(root / "link"))
            claims, err = room.prepare_claims(["link/x.py"], root)
            self.assertEqual(err["error"], "invalid_claim")
            self.assertIn("outside", err["message"])
            claims, err = room.prepare_claims(["link"], root)
            self.assertIsNotNone(err)

    def test_windows_variants(self):
        root = Path(tempfile.gettempdir())
        for bad in ("dir./x.py", "dir /x.py", "x.py::$DATA", "x.py:stream", "PROGRA~1/x", "src/LONGNA~1.txt"):
            claims, err = room.prepare_claims([bad], root)
            self.assertIsNotNone(err, bad)
            self.assertEqual(err["error"], "invalid_claim")
        # stored/legacy spellings still alias to the canonical file for conflict detection
        self.assertEqual(room.normalize_claim("dir./x.py"), "dir/x.py")
        self.assertEqual(room.normalize_claim("x.py::$DATA"), "x.py")
        claims, err = room.prepare_claims(["src/ok.py", "~tilde/file", "a~b.py"], root)
        self.assertIsNone(err)


class TestC16SameAgentDifferentSessions(unittest.TestCase):
    def test_unprotected_same_agent_ids_conflict_across_sessions(self):
        shifts = {"s1": _shift(1, agent="codex", files=["src/a.py"])}
        self.assertTrue(room.check_file_conflicts(shifts, ["src/a.py"], current_shift_id="s2", agent_id="codex"))
        self.assertFalse(room.check_file_conflicts(shifts, ["src/a.py"], current_shift_id="s1", agent_id="codex"))

    def test_clock_in_conflicts_with_tokenless_same_agent_shift(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            _write_room(root, [_shift(1, agent="codex", files=["src/a.py"])])
            res = room.clock_in(root, agent="codex", task="t", files=["src/a.py"])
            self.assertEqual(res.get("error"), "file_conflict")

    def test_token_proven_owner_may_reclaim_own_files(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX, clear=True):
            root = Path(d)
            self.assertNotIn("error", room.clock_in(root, agent="codex", task="t", files=["src/a.py"]))
            self.assertNotIn("error", room.clock_in(root, agent="codex", task="t2", files=["src/a.py"]))


if __name__ == "__main__":
    unittest.main()
