"""Envelope core: immutability, hash anchor, sanitization, pass-by-reference, persistence."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import envelope as ev  # noqa: E402
from scripts.envelope import Envelope, EnvelopeError, HopError  # noqa: E402

REGISTRY = {"bots": {
    "goku": {"name": "goku", "input_contract": {"requires": ["root_request", "ledger", "target_files"]},
             "output_contract": {"provides": ["diff_reference"]}},
    "legacy": {"name": "legacy", "input_contract": "CapsuleEnvelope (root_request)"},
    "bare_bot": {"name": "bare-bot"},
}}


class TestEnvelopeCore(unittest.TestCase):
    def test_append_returns_new_envelope_and_original_untouched(self):
        a = Envelope.new("build x")
        b = a.append({"kind": "note", "note": "found a thing"})
        self.assertEqual(len(a.ledger), 0)
        self.assertEqual(len(b.ledger), 1)
        self.assertEqual(a.root_hash, b.root_hash)
        self.assertEqual(a.root_hash, ev.hash_root("build x"))

    def test_with_artifact_new_envelope_and_artifacts_readonly(self):
        a = Envelope.new("x")
        b = a.with_artifact("target_files", ["src/a.py", "src/b.py"])
        self.assertNotIn("target_files", a.artifacts)
        self.assertEqual(b.artifacts["target_files"], ("src/a.py", "src/b.py"))
        with self.assertRaises(TypeError):
            b.artifacts["x"] = "y"
        with self.assertRaises(AttributeError):
            b.root_request = "evil"
        with self.assertRaises(TypeError):
            b.ledger[0:0] = [1]

    def test_artifacts_are_copied_not_aliased(self):
        src = {"diff_reference": "abc123"}
        e = Envelope.new("x", src)
        src["diff_reference"] = "zzz"
        self.assertEqual(e.artifacts["diff_reference"], "abc123")

    def test_tampered_root_request_rejected_on_load(self):
        data = json.loads(Envelope.new("original").to_json())
        data["root_request"] = "tampered"
        with self.assertRaises(EnvelopeError):
            Envelope.from_json(json.dumps(data))
        with self.assertRaises(EnvelopeError):
            Envelope("tampered", ev.hash_root("original"))

    def test_json_roundtrip(self):
        e = Envelope.new("x").with_artifact("diff_reference", "HEAD~1..HEAD").append("hello")
        self.assertEqual(Envelope.from_json(e.to_json()), e)

    def test_sanitizes_control_chars_and_ansi(self):
        e = Envelope.new("fix\x00 it\x1b[31m red\x1b[0m\x07").append({"note": "a\x1b]0;title\x07b\nc\x7f"})
        self.assertEqual(e.root_request, "fix it red")
        self.assertEqual(e.ledger[0]["note"], "ab c")
        self.assertEqual(e.root_hash, ev.hash_root("fix it red"))

    def test_caps(self):
        with self.assertRaises(EnvelopeError):
            Envelope.new("x" * (ev.MAX_ROOT_REQUEST + 1))
        e = Envelope.new("x").append({"note": "y" * 10000})
        self.assertLessEqual(len(e.ledger[0]["note"]), ev.MAX_EVENT_VALUE)
        with self.assertRaises(EnvelopeError):
            Envelope.new("")

    def test_pass_by_reference_rejects_inlined_bodies(self):
        e = Envelope.new("x")
        for good in ("src/app.py", "a" * 40, "src/x.py#L10", "HEAD~1..HEAD", "pkg.mod:Class"):
            e.with_artifact("diff_reference", good)
        bad = ["def f():\n    return 1", "x" * (ev.MAX_REF + 1), "line1\nline2", "import os; os.system('x')",
               "a\x1b[31mb", "  padded", "", "print('hi') # call", 5,
               "my dir/file.py", "a/../b", "..", "../x", "http://evil.example/x", "/etc/passwd", "\\\\srv\\share", "C:\\x", "two words"]
        for body in bad:
            with self.assertRaises(EnvelopeError, msg=repr(body)):
                e.with_artifact("diff_reference", body)

    def test_bidi_and_zero_width_stripped(self):
        bad = "".join(chr(c) for c in list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A)) + list(range(0x200B, 0x2010)))
        e = Envelope.new("a" + bad + "b").append({"note": "x" + bad + "y"})
        self.assertEqual(e.root_request, "ab")
        self.assertEqual(e.ledger[0]["note"], "xy")
        with self.assertRaises(EnvelopeError):
            Envelope.new("x").with_artifact("diff_reference", "a\u202eb")

    def test_reserved_and_invalid_artifact_names(self):
        e = Envelope.new("x")
        for name in ("root_request", "ledger", "root_hash", "Bad Name", "", "../x"):
            with self.assertRaises(EnvelopeError, msg=name):
                e.with_artifact(name, "a/b")

    def test_validate_hop(self):
        e = Envelope.new("x")
        with self.assertRaises(HopError) as ctx:
            e.validate_hop("goku", REGISTRY)
        self.assertEqual(ctx.exception.missing, ("target_files",))
        e2 = e.with_artifact("target_files", "src/a.py")
        self.assertIs(e2.validate_hop("goku", REGISTRY), e2)
        out = e2.record_hop("goku", REGISTRY, {"diff_reference": "abc123"})
        self.assertEqual(out.artifacts["diff_reference"], "abc123")
        self.assertEqual(out.ledger[-1]["bot"], "goku")
        with self.assertRaises(EnvelopeError):
            e2.record_hop("goku", REGISTRY, {})

    def test_legacy_prose_contract_rejected_and_missing_contract_defaults(self):
        with self.assertRaises(EnvelopeError):
            Envelope.new("x").validate_hop("legacy", REGISTRY)
        Envelope.new("x").validate_hop("bare_bot", REGISTRY)
        Envelope.new("x").validate_hop("bare-bot", REGISTRY)
        with self.assertRaises(EnvelopeError):
            Envelope.new("x").validate_hop("nobody", REGISTRY)


class TestEnvelopePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_append_only_jsonl_roundtrip(self):
        e = Envelope.new("x").append("one")
        path = ev.persist(e, self.base)
        self.assertEqual(path.parent, self.base / ".capsule" / "envelopes")
        first = path.read_text()
        e2 = e.append("two").with_artifact("diff_reference", "abc123")
        ev.persist(e2, self.base)
        text = path.read_text()
        self.assertTrue(text.startswith(first))  # earlier lines never rewritten
        self.assertEqual(ev.load(path), e2)
        ev.persist(e2, self.base)  # idempotent
        self.assertEqual(path.read_text(), text)
        for line in text.splitlines():
            json.loads(line)

    def test_diverged_ledger_refused(self):
        e = Envelope.new("x").append("one")
        ev.persist(e, self.base)
        other = Envelope.new("x").append("different")
        with self.assertRaises(EnvelopeError):
            ev.persist(other, self.base)

    def test_tampered_file_rejected(self):
        path = ev.persist(Envelope.new("x").append("one"), self.base)
        path.write_text(path.read_text().replace('"root_request": "x"', '"root_request": "y"'))
        with self.assertRaises(EnvelopeError):
            ev.load(path)

    def test_concurrent_persist_loads_cleanly(self):
        import threading
        e = Envelope.new("race").append("one")
        errors = []

        def worker():
            try:
                ev.persist(e, self.base)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        path = self.base / ".capsule" / "envelopes" / f"{e.root_hash[:16]}.jsonl"
        self.assertEqual(path.read_text().count('"type": "root"'), 1)
        self.assertEqual(ev.load(path), e)

    def test_load_tolerates_exact_duplicate_root(self):
        path = ev.persist(Envelope.new("x").append("one"), self.base)
        lines = path.read_text().splitlines()
        path.write_text("\n".join([lines[0], lines[0]] + lines[1:]) + "\n")
        self.assertEqual(ev.load(path), Envelope.new("x").append("one"))
        other = json.dumps({"type": "root", "root_request": "y", "root_hash": ev.hash_root("y")})
        path.write_text("\n".join([lines[0], other] + lines[1:]) + "\n")
        with self.assertRaises(EnvelopeError):
            ev.load(path)

    @unittest.skipIf(os.name == "nt", "symlinks")
    def test_symlinked_file_refused(self):
        e = Envelope.new("x")
        d = self.base / ".capsule" / "envelopes"
        d.mkdir(parents=True)
        target = self.base / "victim.txt"
        target.write_text("keep")
        (d / f"{e.root_hash[:16]}.jsonl").symlink_to(target)
        with self.assertRaises(EnvelopeError):
            ev.persist(e, self.base)
        self.assertEqual(target.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
