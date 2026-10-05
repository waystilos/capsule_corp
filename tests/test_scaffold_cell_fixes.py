"""C22/C23: scaffold keyword steering, concurrency lock, enforced tools allowlist."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import scaffold_bot as sb  # noqa: E402

WORKER = """
import sys
sys.path.insert(0, {scripts!r})
import scaffold_bot as sb
n = sys.argv[1]
sb.scaffold_bot({root!r}, n, n.capitalize() + "x (T)", "R", "d", "j", "- none", ["Read"], "v", "inherit")
"""


class ScaffoldCellFixes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        (self.tmp / "config").mkdir()
        shutil.copy(str(ROOT / "registry.yaml"), str(self.tmp / "registry.yaml"))
        shutil.copy(str(ROOT / "config" / "routing.yaml"), str(self.tmp / "config" / "routing.yaml"))

    def scaffold(self, name="gohan", alias="Gohan (A)", tools=("Read",)):
        return sb.scaffold_bot(self.tmp, name, alias, "R", "d", "j", "- n", list(tools), "v", "inherit")

    def test_generic_name_rejected(self):
        for n in ("fix", "test", "build", "security"):
            with self.assertRaises(ValueError):
                self.scaffold(name=n, alias="Zed (A)")
            self.assertFalse((self.tmp / "bots" / (n + ".md")).exists())

    def test_generic_alias_rejected(self):
        with self.assertRaises(ValueError):
            self.scaffold(name="zed", alias="Fix (Fixer)")

    def test_route_strong_keyword_collision_rejected(self):
        with self.assertRaises(ValueError):
            self.scaffold(name="zed", alias="Vulnerability (x)")
        with self.assertRaises(ValueError):
            self.scaffold(name="cve", alias="Zed (x)")

    def test_wildcard_tool_rejected_and_nothing_written(self):
        before = (self.tmp / "registry.yaml").read_bytes()
        with self.assertRaises(ValueError):
            self.scaffold(tools=["*"])
        self.assertEqual((self.tmp / "registry.yaml").read_bytes(), before)
        self.assertFalse((self.tmp / "bots").exists())

    def test_frontmatter_has_tools(self):
        self.scaffold(tools=["Read", "Grep"])
        md = (self.tmp / ".claude" / "agents" / "gohan.md").read_text(encoding="utf-8")
        fm = yaml.safe_load(md.split("---\n")[1])
        self.assertEqual(fm["tools"], "Read, Grep")

    def test_stale_lock_is_broken(self):
        import os, time
        lock = self.tmp / ".scaffold.lock"
        lock.write_text("1")
        old = time.time() - 600
        os.utime(str(lock), (old, old))
        self.scaffold()
        self.assertFalse(lock.exists())

    def test_concurrent_scaffold_no_lost_updates(self):
        names = ["bot%d" % i for i in range(8)]
        code = WORKER.format(scripts=str(ROOT / "scripts"), root=str(self.tmp))
        procs = [subprocess.Popen([sys.executable, "-c", code, n], stderr=subprocess.PIPE) for n in names]
        for p in procs:
            _, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, err.decode())
        self.assertEqual(len(list((self.tmp / "bots").glob("bot*.md"))), 8)
        reg = yaml.safe_load((self.tmp / "registry.yaml").read_text(encoding="utf-8"))["bots"]
        self.assertEqual(sum(1 for n in names if n in reg), 8)
        routes = yaml.safe_load((self.tmp / "config" / "routing.yaml").read_text(encoding="utf-8"))["routes"]
        self.assertEqual(sum(1 for r in routes if r["owner"] in names), 8)
        self.assertEqual(list(self.tmp.rglob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
