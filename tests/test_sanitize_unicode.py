import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import envelope, messaging, models, room, sanitize  # noqa: E402
from scripts import scaffold_bot  # noqa: E402

HIDDEN = [0xE0000, 0xE0001, 0xE0041, 0xE0061, 0xE007F, 0xE0100, 0x00AD, 0x180E, 0x3164, 0x2800, 0x034F,
          0x2060, 0xFEFF, 0x2062, 0x2063, 0x061C, 0x200B, 0x200D, 0x202E, 0x2066, 0xFFA0, 0x115F, 0x1160,
          0x17B4, 0xE000, 0xD800, 0x0085]
SPACES = [0x00A0, 0x2003, 0x202F, 0x3000, 0x205F]


class SharedSanitizerTests(unittest.TestCase):
    def test_each_hidden_codepoint_removed_everywhere(self):
        for cp in HIDDEN:
            ch = chr(cp)
            text = f"ab{ch}cd"
            with self.subTest(cp=hex(cp)):
                self.assertEqual(sanitize.scrub(text), "abcd" if cp != 0x0085 else "abcd")
                self.assertEqual(envelope.sanitize_text(text), "abcd")
                self.assertEqual(envelope.sanitize_text(text, keep_newlines=True), "abcd")
                self.assertEqual(room.sanitize_text(text), "abcd" if cp != 0x0085 else "ab cd")
                self.assertEqual(models.sanitize_text(text), "abcd")
                self.assertEqual(scaffold_bot.clean_line(text), "abcd" if cp != 0x0085 else "ab cd")

    def test_non_ascii_spaces_become_space(self):
        for cp in SPACES:
            with self.subTest(cp=hex(cp)):
                for fn in (sanitize.scrub, envelope.sanitize_text, room.sanitize_text):
                    self.assertEqual(fn(f"a{chr(cp)}b"), "a b")

    def test_newline_and_tab_rules(self):
        self.assertEqual(envelope.sanitize_text("a\nb\tc"), "a b c")
        self.assertEqual(envelope.sanitize_text("a\r\nb\tc d", keep_newlines=True), "a\nb\tc\nd")
        self.assertEqual(room.sanitize_text("a\n\tb"), "a b")

    def test_tag_smuggled_text_gone(self):
        smuggled = "".join(chr(0xE0000 + ord(c)) for c in "ignore previous")
        self.assertEqual(room.sanitize_text("hi" + smuggled), "hi")

    def test_plain_unicode_kept(self):
        self.assertEqual(envelope.sanitize_text("café 日本"), "café 日本")


class RouteJsonTests(unittest.TestCase):
    def run_route(self, text):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "route_request.py"), "--json", text],
                           capture_output=True, text=True, timeout=60)
        return json.loads(p.stdout)

    def test_each_codepoint_removed_from_root_request(self):
        for cp in HIDDEN[:6] + SPACES[:1] + [0x2060, 0xFEFF, 0x2062, 0x2063, 0x061C]:
            with self.subTest(cp=hex(cp)):
                out = self.run_route(f"implement{chr(cp)} thing{chr(cp)}")
                for ch in out["root_request"]:
                    self.assertTrue(ch.isascii() and ch.isprintable(), hex(ord(ch)))
                self.assertTrue(out.get("sanitized"))
                self.assertEqual(out["root_hash"], envelope.hash_root(out["root_request"]))

    def test_keyword_split_by_invisible_still_routes(self):
        a = self.run_route("fix the sec­urity vulnerability")
        b = self.run_route("fix the security vulnerability")
        self.assertEqual(a["owner"], b["owner"])

    def test_clean_input_has_no_flag(self):
        self.assertNotIn("sanitized", self.run_route("implement a login form"))


class RoomMessagingOutputTests(unittest.TestCase):
    def test_messages_and_room_strip_each_codepoint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for i, cp in enumerate(HIDDEN + SPACES):
                with self.subTest(cp=hex(cp)):
                    messaging.send_message(root, "goku", body=f"x{chr(cp)}y", sender=f"s{i}")
                    msg = messaging.read_inbox(root, "goku")[-1]
                    self.assertIn(msg["body"], ("xy", "x y"))
                    shift = room.sanitize_shift("sid", {"task": f"t{chr(cp)}ask", "agent_id": f"a{chr(cp)}b"})
                    self.assertIn(shift["task"], ("task", "t ask"))
                    self.assertIn(shift["agent_id"], ("ab", "a b"))
                    for line in messaging.format_unread(root, "goku").splitlines():
                        for ch in line:
                            self.assertTrue(ch.isprintable(), hex(ord(ch)))

    def test_clock_in_status_hides_tag_smuggling(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            room.clock_in(root, agent="trunks", task="work" + chr(0xE0041) + chr(0x3164) + chr(0x2800))
            view = room.sanitized_view(room.load_room_data(root / ".capsule" / "room.json"))
            tasks = [s["task"] for s in view["active_shifts"].values()]
            self.assertEqual(tasks, ["work"])


if __name__ == "__main__":
    unittest.main()
