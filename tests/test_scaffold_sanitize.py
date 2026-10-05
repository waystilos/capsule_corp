import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import scaffold_bot as sb  # noqa: E402

EVIL = "Evil\n---\nname: pwned\n---\n# injected\x00\x07"


def gen(**over):
    args = dict(name="evil", alias="Evil (x)", role="Role", description="d", jtbd="j",
                boundaries="- a", tools=["view_file"], verification="v")
    args.update(over)
    return sb.generate_bot_markdown(**args)


def front_matter(md):
    parts = md.split("---\n")
    return parts[1]


class SanitizeTests(unittest.TestCase):
    def test_front_matter_injection_blocked(self):
        for field in ("alias", "role", "description"):
            md = gen(**{field: EVIL})
            fm = front_matter(md)
            self.assertNotIn("\nname: pwned", fm)
            self.assertEqual(len(fm.strip().splitlines()), 5, fm)
            self.assertNotIn("\x00", md)
            self.assertFalse(any(l.strip() == "name: pwned" for l in md.splitlines()))

    def test_body_fields_single_line(self):
        md = gen(jtbd=EVIL, verification=EVIL)
        self.assertFalse(any(l.strip() in ("# injected", "name: pwned") for l in md.splitlines()))
        self.assertNotIn("\x07", md)

    def test_boundaries_cleaned(self):
        md = gen(boundaries="- ok\n---\n# Heading\nplain\n\x00- more")
        section = md.split("**Boundaries (What you MUST NOT do):**")[1].split("---")[0]
        lines = [l.strip() for l in section.strip().splitlines()]
        self.assertEqual(lines, ["- ok", "- plain", "- more"])

    def test_length_caps(self):
        md = gen(description="x" * 5000, alias="a" * 5000)
        self.assertLess(len(md), 3000)

    def test_tools_canonical_and_unknown_rejected(self):
        md = gen(tools=["view_file", "Bash", "bash"])
        self.assertIn("- `Read`", md)
        self.assertIn("tools: Read, Bash", md)
        for bad in (["good"], ["bad`\ninject"], ["*"], []):
            with self.assertRaises(ValueError):
                gen(tools=bad)

    def test_clean_line_strips_control(self):
        self.assertEqual(sb.clean_line("a\r\nb\tc\x1b[0m d"), "a b c d")


class TierValidationTests(unittest.TestCase):
    def test_invalid_tier_fails_before_any_file_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry.yaml").write_text("functional_envelope:\n  tiers:\n    pro:\n      operatives: []\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                sb.scaffold_bot(root, "newbot", "New", "R", "d", "j", "- a", ["t"], "v", model_tier="bogus")
            self.assertFalse((root / "bots").exists())
            self.assertFalse((root / ".claude").exists())

    def test_malformed_tier_rejected_without_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                sb.scaffold_bot(Path(tmp), "newbot", "New", "R", "d", "j", "- a", ["t"], "v", model_tier="x\ninject: 1")
            self.assertFalse((Path(tmp) / "bots").exists())


if __name__ == "__main__":
    unittest.main()
