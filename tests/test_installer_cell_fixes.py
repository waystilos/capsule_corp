import json
import subprocess
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import install_elixir as ie  # noqa: E402

NO_ELIXIR = {"elixir": None, "erlang": None, "path": None}
BAD = ["--help", "1.17\n   $ brew install harmless\x1b[2K", "1.17\n", "\x1b[2K1", "", " 1.0", "-1", "1;rm"]


def run(**k):
    out, err = StringIO(), StringIO()
    with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err), \
            mock.patch.object(ie, "get_installed_versions", return_value=NO_ELIXIR), \
            mock.patch.object(ie, "safe_which", side_effect=lambda n: "/usr/bin/" + n):
        rc = ie.run_install(**k)
    return rc, out.getvalue(), err.getvalue()


class VersionTests(unittest.TestCase):
    def test_injected_versions_rejected(self):
        for v in BAD:
            for js in (False, True):
                rc, out, err = run(dry_run=True, manager="asdf", version=v, json_mode=js)
                self.assertNotEqual(rc, 0, repr(v))
                self.assertNotIn("\x1b", out + err)
                self.assertFalse(any(l.lstrip().startswith("$") for l in (out + err).splitlines()))

    def test_valid_version_ok(self):
        rc, out, _ = run(dry_run=True, manager="asdf", version="1.17.3-otp_27+x")
        self.assertEqual(rc, 0)
        self.assertIn("asdf install elixir 1.17.3-otp_27+x", out)

    def test_sanitize(self):
        self.assertEqual(ie.sanitize_text("a\nb\x1b[2Kc\x07"), "abc")

    def test_wrapper_rejects(self):
        sh = ROOT / "scripts" / "install_elixir.sh"
        for arg in (["--version", "--help"], ["--version=--help"], ["--version", "1\n2"]):
            r = subprocess.run(["bash", str(sh), "--dry-run"] + arg, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, arg)


class SudoPathTests(unittest.TestCase):
    def test_sudo_plans_use_absolute_manager(self):
        for mgr, binary in (("apt", "apt-get"), ("dnf", "dnf"), ("pacman", "pacman"),
                            ("apk", "apk"), ("zypper", "zypper")):
            with mock.patch.object(ie, "safe_which", side_effect=lambda n: "/usr/bin/" + n), \
                    mock.patch("platform.system", return_value="Linux"):
                _, cmds, _ = ie.detect_installer(mgr)
            for c in cmds:
                self.assertEqual(c[0], "sudo")
                self.assertEqual(c[1], "/usr/bin/" + binary, c)

    def test_dry_run_output_absolute(self):
        with mock.patch.object(ie, "safe_which", side_effect=lambda n: "/usr/bin/" + n), \
                mock.patch("platform.system", return_value="Linux"), \
                mock.patch("os.geteuid", return_value=1000):
            rc, out, _ = run(dry_run=True, manager="apt", json_mode=True)
        self.assertEqual(rc, 0)
        cmds = json.loads(out)["commands"]
        self.assertEqual(cmds[0], "/usr/bin/sudo /usr/bin/apt-get update")

    def test_cwd_manager_rejected(self):
        with mock.patch("shutil.which", return_value=str(Path.cwd() / "apt-get")):
            self.assertIsNone(ie.safe_which("apt-get"))


if __name__ == "__main__":
    unittest.main()
