import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "config" / "sync_all_ais.sh"


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "requires bash")
class SyncDryRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.dev = self.tmp / "dev"
        self.home.mkdir()
        self.dev.mkdir()

    def run_sync(self, *args):
        env = dict(os.environ, HOME=str(self.home), DEV_ROOT=str(self.dev))
        return subprocess.run(["bash", str(SCRIPT), *args], env=env,
                              capture_output=True, text=True, timeout=120)

    def test_already_synced_dry_run_exits_zero(self):
        first = self.run_sync()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_sync("--dry-run")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotIn("Sync incomplete", second.stderr)
        self.assertNotIn("Preserved", second.stdout)

    def test_real_conflict_exits_one_without_banner(self):
        self.assertEqual(self.run_sync().returncode, 0)
        (self.home / ".cursorrules").write_text("user content\n")
        res = self.run_sync("--dry-run")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("Sync incomplete", res.stderr)
        self.assertNotIn("ALL AIs ARE NOW SYNCHRONIZED", res.stdout)

    def test_conflicting_symlink_exits_one(self):
        self.assertEqual(self.run_sync().returncode, 0)
        link = next((self.home / ".agents" / "skills").iterdir())
        link.unlink()
        link.symlink_to(self.tmp)
        res = self.run_sync("--dry-run")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(os.readlink(link), str(self.tmp))


if __name__ == "__main__":
    unittest.main()
