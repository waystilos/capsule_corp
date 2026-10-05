"""F-086: every bot holding the abstract `send_message` tool maps to real `capsule send/inbox/ack` commands."""
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MESSAGING = ROOT / "scripts" / "messaging.py"


def parse_registry():
    """Dependency-free scan: ({bot: [allowed_tools]}, messaging-map-lines)."""
    bots, key, in_bots, in_tools, section = {}, None, False, False, None
    mapping = []
    for line in (ROOT / "registry.yaml").read_text(encoding="utf-8").splitlines():
        if re.match(r"^[A-Za-z_]+:", line):
            section = line.split(":")[0]
            in_bots = section == "bots"
            continue
        if section == "messaging":
            mapping.append(line)
        if not in_bots:
            continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            key, in_tools = m.group(1), False
            bots[key] = []
            continue
        if re.match(r"^    allowed_tools:\s*$", line):
            in_tools = True
            continue
        m = re.match(r'^      - "?([^"]+)"?\s*$', line)
        if in_tools and m and key:
            bots[key].append(m.group(1))
        elif in_tools and not line.startswith("      "):
            in_tools = False
    return bots, "\n".join(mapping)


def run(*args):
    env = dict(os.environ)
    return subprocess.run([sys.executable, str(MESSAGING)] + list(args), capture_output=True, text=True, env=env)


class TestRegistryMessaging(unittest.TestCase):
    def test_holders_exist_and_registry_documents_the_mapping(self):
        bots, mapping = parse_registry()
        holders = sorted(b for b, tools in bots.items() if "send_message" in tools)
        self.assertIn("piccolo", holders)
        self.assertIn("king_kai", holders)
        self.assertIn("send_message:", mapping)
        for cmd in ("capsule send", "capsule inbox", "capsule ack"):
            self.assertIn(cmd, mapping)

    def test_mapped_cli_commands_exist(self):
        for sub in ("send", "inbox", "ack"):
            res = run(sub, "--help")
            self.assertEqual(res.returncode, 0, f"{sub}: {res.stderr}")
            self.assertIn("usage", res.stdout.lower())

    def test_documented_flags_exist(self):
        self.assertIn("--to", run("send", "--help").stdout)
        self.assertIn("--unread", run("inbox", "--help").stdout)


if __name__ == "__main__":
    unittest.main()
