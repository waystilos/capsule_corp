#!/usr/bin/env python3
"""Round-2 security fixes: inbox identity rule, regex anchors, clean errors, secret pattern gaps."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import messaging  # noqa: E402
import room  # noqa: E402
import secret_patterns as sp  # noqa: E402

_AGENT_VARS = ("GEMINI_CLI", "ANTIGRAVITY", "CODEX", "CURSOR_AGENT", "CURSOR_VERSION", "WINDSURF_AGENT",
               "CLAUDECODE", "CLAUDE_CODE", "CAPSULE_SESSION_TOKEN")


def _env(user):
    env = {k: v for k, v in os.environ.items() if k not in _AGENT_VARS}
    env["USER"] = user
    return env


def _run(args, user, cwd):
    return subprocess.run([sys.executable, str(CAPSULE_ROOT / "scripts" / args[0])] + args[1:], cwd=str(cwd),
                          env=_env(user), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=60)


class TestInboxIdentity(unittest.TestCase):
    def test_off_shift_id_inbox_not_leaked_on_clock_in(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r = _run(["messaging.py", "send", "--dir", d, "--to", "victim", "--body", "SECRETBODY"], "alice", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _run(["room.py", "clock-in", d, "--agent", "victim", "--task", "t"], "mallory", root)
            self.assertNotIn("SECRETBODY", r.stdout + r.stderr)
            # the real victim identity does see it
            r = _run(["room.py", "clock-in", d, "--task", "t"], "victim", root)
            self.assertIn("SECRETBODY", r.stdout)

    def test_inbox_ack_compact_need_identity_without_token_shift(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, _env("mallory"), clear=True):
            root = Path(d)
            m = messaging.send_message(root, "victim", body="hi", sender="alice")
            with self.assertRaises(messaging.MessagingError):
                messaging.read_inbox(root, "victim", authenticate=True)
            with self.assertRaises(messaging.MessagingError):
                messaging.ack_message(root, "victim", m["id"])
            with self.assertRaises(messaging.MessagingError):
                messaging.compact_inbox(root, "victim")
            with patch.dict(os.environ, {"USER": "victim"}):
                self.assertEqual(len(messaging.read_inbox(root, "victim", authenticate=True)), 1)
                self.assertTrue(messaging.ack_message(root, "victim", m["id"]))
                self.assertEqual(messaging.compact_inbox(root, "victim"), 1)

    def test_send_to_off_shift_id_still_allowed(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, _env("mallory"), clear=True):
            self.assertTrue(messaging.send_message(Path(d), "victim", body="x")["id"].startswith("msg_"))


class TestAnchors(unittest.TestCase):
    def test_agent_id_trailing_newline_rejected(self):
        with self.assertRaises(room.RoomError):
            room.norm_agent_id("victim\n")
        self.assertEqual(room.norm_agent_id("victim"), "victim")

    def test_session_id_trailing_newline_rejected(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, _env("bob"), clear=True):
            res = room.clock_in(Path(d), session="abc\n", task="t")
            self.assertEqual(res.get("error"), "invalid_session")

    def test_msg_and_hash_regex_fullmatch(self):
        self.assertIsNone(messaging.MSG_ID_RE.fullmatch("msg_" + "0" * 16 + "\n"))
        self.assertIsNone(messaging.HASH_RE.fullmatch("a" * 64 + "\n"))
        self.assertIsNotNone(messaging.HASH_RE.fullmatch("a" * 64))

    def test_to_with_trailing_newline_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = _run(["messaging.py", "send", "--dir", d, "--to", "victim\n", "--body", "x"], "alice", Path(d))
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("Traceback", r.stderr)
            self.assertFalse((Path(d) / ".capsule" / "inbox" / "victim.jsonl").exists())


@unittest.skipIf(os.name == "nt", "mkfifo is POSIX only")
class TestCleanErrors(unittest.TestCase):
    def test_fifo_inbox_clean_error_no_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d) / ".capsule" / "inbox"
            inbox.mkdir(parents=True, mode=0o700)
            os.mkfifo(str(inbox / "b.jsonl"))
            for args in (["clock-in", d, "--task", "t"], ["status", d], [d]):
                r = _run(["room.py"] + args, "b", Path(d))
                self.assertNotIn("Traceback", r.stderr, r.stderr)
            r = _run(["room.py", "clock-in", d, "--task", "t"], "b", Path(d))
            self.assertNotIn("Traceback", r.stderr)


def _rt(text):
    """Assemble sensitive names at runtime so this file holds no credential-looking literals."""
    return (text.replace("@PU@", "PASS" + "WORD").replace("@P@", "pass" + "word")
            .replace("@T@", "TO" + "KEN").replace("@S@", "sec" + "ret"))


def hit(text):
    return bool(sp.find_secrets(text))


class TestSecretGaps(unittest.TestCase):
    def test_flagged(self):
        cases = [
            '@P@ = "Ab1$(whoami)zzzzz"',
            '@P@ = "correct horse battery staple 9"',
            '@P@ = "Ab1<xx>Zq9wertyuiop"',
            "@PU@=Ab1<Zq9wertyuiop>xyz",
            "@P@: Xk9!pQ2#rT7$vL1(zz",
            "@T@=aaaaaaaaaa.bbbbbbbbbb.cccccccccc",
            "API_@T@=" + "aB3" * 83,
            '@P@ = "' + "aB3" * 83 + '"',
            "config['@S@'] = 'Zq9Xk2pL7vR4mN8wT3yH'",
            'cfg["@S@"]="Zq9Xk2pL7vR4mN8wT3yH"',
            "Authorization: Bearer " + "abcdefghij" * 3,
            '@P@ = "Xk9Zq2pL7vR4mN8wexample"',
            "API_@T@=Xk9Zq2pL7vR4mN8wT3yHtodo123",
            '@P@ = "Zq9Xk2pL7vR4mN8wT3yH-example-Xk9pQ2rT7vL1"',
            '@P@ = "Zq9Xk2pL7vR4mN8wT3yHdummyXk9pQ2rT7vL1xxx"',
        ]
        for c in cases:
            c = _rt(c)
            self.assertTrue(hit(c), c)

    def test_placeholders_still_ignored(self):
        for c in ['password = "changeme123456"', 'password = "your_password_here"',
                  'password = "example-password-1"', "password=${DB_PASSWORD}",
                  'password = "${X}abc12345678"', "token=get_token(12345678901234)",
                  'password = "<your-password-1234>"', "TOKEN=xxxxxxxxxxxxxxxxxxxx"]:
            self.assertFalse(hit(c), c)

    def test_adversarial_input_bounded(self):
        for text in ("password=" * 100000, 'password="' * 100000, "TOKEN=" + "a." * 500000):
            t0 = time.monotonic()
            sp.find_secrets(text)
            self.assertLess(time.monotonic() - t0, 20)

    def test_diff_window_documented_limit(self):
        # content scan has no window: a secret deep into a long line is still found there
        line = "x" * 4500 + _rt(' @P@ = "Ab1Zq9wertyuiop99"')
        self.assertTrue(hit(line))


if __name__ == "__main__":
    unittest.main()
