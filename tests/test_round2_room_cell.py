#!/usr/bin/env python3
"""Round-2 Cell fixes: FIFO/non-regular state files, inbox lockouts, per-recipient rate limit. Temp dirs only."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = CAPSULE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import messaging  # noqa: E402
import room  # noqa: E402
from messaging import MessagingError, send_message  # noqa: E402

ENV = dict(os.environ, CODEX="1")
ENV.pop("CAPSULE_SESSION_TOKEN", None)
HAS_FIFO = hasattr(os, "mkfifo")


def run(args, root, timeout=20):
    """Run a script as a subprocess; a hang regression raises TimeoutExpired (test failure) instead of blocking."""
    return subprocess.run([sys.executable] + args + ["--dir", str(root)], capture_output=True, text=True,
                          timeout=timeout, env=ENV)


def msg(root, *a, **k):
    return run([str(SCRIPTS / "messaging.py")] + list(a), root, **k)


def rm(root, *a, **k):
    timeout = k.get("timeout", 20)
    return subprocess.run([sys.executable, str(SCRIPTS / "room.py")] + list(a) + [str(root)], capture_output=True,
                          text=True, timeout=timeout, env=ENV)


@unittest.skipUnless(HAS_FIFO, "mkfifo unavailable")
class FifoTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / ".capsule" / "inbox").mkdir(parents=True)

    def tearDown(self):
        self.td.cleanup()

    def test_send_to_fifo_inbox_refused_no_hang(self):
        os.mkfifo(str(self.root / ".capsule" / "inbox" / "bob.jsonl"))
        r = msg(self.root, "send", "--to", "bob", "--body", "hi", "--from", "alice")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("not a regular file", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        # lock was released: other commands still work
        self.assertEqual(rm(self.root, "clock-in", "--task", "t", "--agent", "carol").returncode, 0)

    def test_append_jsonl_private_fifo_with_reader_refused(self):
        p = self.root / ".capsule" / "inbox" / "_handoffs.jsonl"
        os.mkfifo(str(p))
        rfd = os.open(str(p), os.O_RDONLY | os.O_NONBLOCK)  # a reader makes the write-open succeed
        try:
            with self.assertRaises(room.RoomSecurityError):
                room.append_jsonl_private(p, {"a": 1})
        finally:
            os.close(rfd)

    def test_clock_out_with_fifo_handoffs_does_not_hang(self):
        self.assertEqual(rm(self.root, "clock-in", "--task", "t", "--agent", "dave").returncode, 0)
        os.mkfifo(str(self.root / ".capsule" / "inbox" / "_handoffs.jsonl"))
        r = rm(self.root, "clock-out", "--summary", "done", "--agent", "dave")
        self.assertNotIn("Traceback", r.stderr)

    def test_room_lock_fifo_clean_error(self):
        os.mkfifo(str(self.root / ".capsule" / "room.lock"))
        r = msg(self.root, "send", "--to", "bob", "--body", "hi", "--from", "alice")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("not a regular file", r.stderr)


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / ".capsule" / "inbox").mkdir(parents=True)
        self.inbox = self.root / ".capsule" / "inbox"

    def tearDown(self):
        self.td.cleanup()

    def test_sparse_oversized_inbox_reset_by_recipient(self):
        f = self.inbox / "bob.jsonl"
        with open(f, "wb") as h:
            h.truncate(40 * 1024 * 1024)
        with self.assertRaises(MessagingError):
            send_message(self.root, "bob", "hi", sender="alice")
        r = msg(self.root, "inbox", "--agent", "bob", "--compact")  # detected id != bob: refused
        self.assertEqual(r.returncode, 1)
        self.assertTrue(f.exists())
        with patch.object(messaging, "detected_agent_id", return_value="bob"):
            self.assertEqual(messaging.compact_inbox(self.root, "bob"), 0)
        self.assertFalse(f.exists())
        send_message(self.root, "bob", "hi again", sender="alice")

    def test_reset_removes_symlink_without_following(self):
        victim = self.root / "victim.txt"
        victim.write_text("keep")
        link = self.inbox / "bob.jsonl"
        os.symlink(str(victim), str(link))
        with self.assertRaises(MessagingError):
            send_message(self.root, "bob", "hi", sender="alice")
        self.assertTrue(messaging._discard_inbox_locked(self.root, "bob"))
        self.assertFalse(os.path.lexists(str(link)))
        self.assertEqual(victim.read_text(), "keep")

    def test_gc_frees_store_when_full(self):
        old = time.time() - 2 * 3600
        for i in range(messaging.MAX_INBOX_FILES):
            p = self.inbox / f"g{i}.jsonl"
            p.write_text("")
            os.utime(str(p), (old, old))
        # empty inboxes do not count toward the cap at all
        self.assertEqual(messaging._inbox_usage(self.inbox)[0], 0)
        # fill with fresh non-empty inboxes, of which some are fully acked and old
        for i in range(messaging.MAX_INBOX_FILES):
            p = self.inbox / f"g{i}.jsonl"
            mid = "msg_%016x" % i
            p.write_text('{"id":"%s","body":"x"}\n{"ack":"%s"}\n' % (mid, mid))
            os.utime(str(p), (old, old))
        self.assertGreaterEqual(messaging._inbox_usage(self.inbox)[0], messaging.MAX_INBOX_FILES)
        m = send_message(self.root, "newbie", "hi", sender="alice")
        self.assertEqual(m["to"], "newbie")
        self.assertLess(len(list(self.inbox.glob("g*.jsonl"))), messaging.MAX_INBOX_FILES)

    def test_gc_keeps_unacked_and_fresh(self):
        old = time.time() - 2 * 3600
        a = self.inbox / "a.jsonl"
        a.write_text('{"id":"msg_0000000000000001","body":"x"}\n')
        os.utime(str(a), (old, old))
        b = self.inbox / "b.jsonl"
        b.write_text("")
        self.assertEqual(messaging._gc_inboxes(self.inbox), 0)
        self.assertTrue(a.exists() and b.exists())

    def test_per_recipient_rate_limit_beats_rotating_senders(self):
        for i in range(messaging.RATE_PER_RECIPIENT):
            send_message(self.root, "bob", "hi", sender=f"s{i}")
        with self.assertRaises(MessagingError) as cm:
            send_message(self.root, "bob", "hi", sender="fresh")
        self.assertIn("received", str(cm.exception))
        send_message(self.root, "other", "hi", sender="fresh")  # other recipients unaffected


if __name__ == "__main__":
    unittest.main()
