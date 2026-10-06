import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import envelope as E  # noqa: E402


def _write(path, lines):
    path.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in lines), encoding="utf-8")


class ChainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        env = E.Envelope.new("build a thing").append("one").append("two").append("three")
        self.path = E.persist(env, self.base)
        self.env = env

    def tearDown(self):
        self._tmp.cleanup()

    def recs(self):
        return [json.loads(l) for l in self.path.read_text().splitlines()]

    def test_roundtrip_and_chain_fields(self):
        events = [r for r in self.recs() if r["type"] == "event"]
        self.assertEqual(events[0]["prev_hash"], self.env.root_hash)
        self.assertEqual(events[1]["prev_hash"], events[0]["hash"])
        loaded = E.load(self.path)
        self.assertEqual(loaded, self.env)
        self.assertFalse(loaded.legacy_ledger)

    def test_append_across_persists_keeps_chain(self):
        E.persist(self.env.append("four"), self.base)
        self.assertEqual(len(E.load(self.path).ledger), 4)

    def test_reorder_rejected(self):
        r = self.recs()
        r[1], r[2] = r[2], r[1]
        _write(self.path, r)
        with self.assertRaisesRegex(E.EnvelopeError, "chain broken"):
            E.load(self.path)

    def test_drop_rejected(self):
        r = self.recs()
        del r[2]
        _write(self.path, r)
        with self.assertRaisesRegex(E.EnvelopeError, "chain broken"):
            E.load(self.path)

    def test_forged_event_rejected(self):
        r = self.recs()
        r[2]["event"] = {"note": "forged"}
        _write(self.path, r)
        with self.assertRaisesRegex(E.EnvelopeError, "chain broken"):
            E.load(self.path)

    def test_injected_unchained_event_rejected(self):
        r = self.recs()
        r.insert(3, {"type": "event", "event": {"note": "sneaky"}})
        _write(self.path, r)
        with self.assertRaisesRegex(E.EnvelopeError, "chain broken"):
            E.load(self.path)

    def test_legacy_loads_with_flag_and_can_extend(self):
        r = self.recs()
        for rec in r:
            rec.pop("hash", None)
            rec.pop("prev_hash", None)
        _write(self.path, r)
        loaded = E.load(self.path)
        self.assertTrue(loaded.legacy_ledger)
        self.assertEqual(len(loaded.ledger), 3)
        E.persist(loaded.append("four"), self.base)
        again = E.load(self.path)
        self.assertEqual(len(again.ledger), 4)
        self.assertTrue(again.legacy_ledger)

    @unittest.skipIf(os.name == "nt", "symlinks")
    def test_symlink_rejected(self):
        link = self.base / "link.jsonl"
        os.symlink(self.path, link)
        with self.assertRaises(E.EnvelopeError):
            E.load(link)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs mkfifo")
    def test_fifo_rejected_without_blocking(self):
        fifo = self.base / "f.jsonl"
        os.mkfifo(fifo)
        with self.assertRaises(E.EnvelopeError):
            E.load(fifo)

    def test_oversized_rejected(self):
        old = E.MAX_ENVELOPE_BYTES
        E.MAX_ENVELOPE_BYTES = 50
        try:
            with self.assertRaisesRegex(E.EnvelopeError, "too large"):
                E.load(self.path)
        finally:
            E.MAX_ENVELOPE_BYTES = old

    def test_non_utf8_is_clear_error(self):
        self.path.write_bytes(b"\xff\xfe\n")
        with self.assertRaises(E.EnvelopeError):
            E.load(self.path)


if __name__ == "__main__":
    unittest.main()
