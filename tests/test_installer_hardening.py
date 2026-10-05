import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import install_elixir as ie  # noqa: E402

NO_ELIXIR = {"elixir": None, "erlang": None, "path": None}


def quiet(fn, *a, **k):
    out, err = StringIO(), StringIO()
    with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
        rc = fn(*a, **k)
    return rc, out.getvalue(), err.getvalue()


def fake_which(present):
    return lambda name: ("/usr/bin/" + name) if name in present else None


class ManagerPreferenceTests(unittest.TestCase):
    def test_os_manager_preferred_over_asdf_and_mise(self):
        with mock.patch.object(ie.platform, "system", return_value="Darwin"), \
                mock.patch.object(ie.shutil, "which", side_effect=fake_which({"brew", "asdf", "mise"})):
            manager, cmds, _ = ie.detect_installer()
        self.assertEqual(manager, "homebrew")
        self.assertTrue(cmds[0][0].endswith("brew"))

    def test_explicit_manager_with_version(self):
        with mock.patch.object(ie.platform, "system", return_value="Darwin"), \
                mock.patch.object(ie.shutil, "which", side_effect=fake_which({"brew", "asdf"})):
            manager, cmds, _ = ie.detect_installer("asdf", "1.17.3")
        self.assertEqual(manager, "asdf")
        self.assertIn(["asdf", "install", "elixir", "1.17.3"], [[os.path.basename(c[0])] + c[1:] for c in cmds])
        self.assertFalse(any("latest" == c[-1] and "elixir" in c for c in cmds))

    def test_asdf_without_version_refuses_latest(self):
        with mock.patch.object(ie.platform, "system", return_value="Darwin"), \
                mock.patch.object(ie.shutil, "which", side_effect=fake_which({"asdf"})):
            manager, cmds, msg = ie.detect_installer("asdf")
        self.assertEqual(manager, "unsupported")
        self.assertIn("--version", msg)
        self.assertEqual(cmds, [])

    def test_version_unsupported_for_brew(self):
        with mock.patch.object(ie.platform, "system", return_value="Darwin"), \
                mock.patch.object(ie.shutil, "which", side_effect=fake_which({"brew"})):
            manager, _, msg = ie.detect_installer(None, "1.17.3")
        self.assertEqual(manager, "unsupported")
        self.assertIn("--version", msg)


class CwdBinaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.realpath(self.tmp.name)
        self.old = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, self.old)

    def test_safe_which_rejects_cwd_binary(self):
        local = os.path.join(self.dir, "elixir")
        with mock.patch.object(ie.shutil, "which", return_value=local):
            self.assertIsNone(ie.safe_which("elixir"))
        with mock.patch.object(ie.shutil, "which", return_value="/usr/bin/elixir"):
            self.assertEqual(ie.safe_which("elixir"), "/usr/bin/elixir")

    def test_detection_never_executes_cwd_binary(self):
        local = os.path.join(self.dir, "elixir")
        with mock.patch.object(ie.shutil, "which", return_value=local), \
                mock.patch.object(ie.subprocess, "check_output") as co:
            info = ie.get_installed_versions()
        co.assert_not_called()
        self.assertIsNone(info["elixir"])

    def test_cwd_package_manager_is_ignored(self):
        local = os.path.join(self.dir, "brew")
        with mock.patch.object(ie.platform, "system", return_value="Darwin"), \
                mock.patch.object(ie.shutil, "which", return_value=local):
            manager, cmds, _ = ie.detect_installer()
        self.assertEqual(manager, "unsupported")
        self.assertEqual(cmds, [])

    def test_cwd_sudo_is_rejected(self):
        local = os.path.join(self.dir, "sudo")
        with mock.patch.object(ie.shutil, "which", return_value=local), \
                mock.patch.object(ie.os, "geteuid", create=True, return_value=1000):
            cmds, err = ie.adjust_for_privileges([["sudo", "apt-get", "update"]])
        self.assertIsNotNone(err)


class PlanOutputTests(unittest.TestCase):
    def _run(self, **kw):
        with mock.patch.object(ie, "get_installed_versions", return_value=NO_ELIXIR), \
                mock.patch.object(ie, "detect_installer", return_value=("apt", [["sudo", "apt-get", "update"]], "plan")), \
                mock.patch.object(ie, "adjust_for_privileges", side_effect=lambda c: (c, None)):
            return quiet(ie.run_install, **kw)

    def test_dry_run_warns_sudo_and_not_runtime(self):
        rc, out, _ = self._run(dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("sudo", out.lower())
        self.assertIn("WARNING", out)
        self.assertIn("installer only", out)

    def test_dry_run_json_flags_sudo(self):
        rc, out, _ = self._run(dry_run=True, json_mode=True)
        data = json.loads(out)
        self.assertTrue(data["uses_sudo"])

    def test_no_actor_model_claim(self):
        text = (ROOT / "scripts" / "install_elixir.py").read_text(encoding="utf-8")
        self.assertNotIn("Actor model", text)

    def test_already_installed_not_runtime_claim(self):
        with mock.patch.object(ie, "get_installed_versions", return_value={"elixir": "Elixir 1", "erlang": "E", "path": "/x"}):
            rc, out, _ = quiet(ie.run_install)
        self.assertEqual(rc, 0)
        self.assertIn("installer only", out)


@unittest.skipUnless(shutil.which("bash"), "bash required")
class ShellFallbackTests(unittest.TestCase):
    SH = str(ROOT / "scripts" / "install_elixir.sh")

    def _run(self, *args):
        env = dict(os.environ, CAPSULE_INSTALL_FORCE_FALLBACK="1")
        return subprocess.run(["bash", self.SH] + list(args), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=30)

    def test_syntax(self):
        self.assertEqual(subprocess.run(["bash", "-n", self.SH]).returncode, 0)

    def test_refuses_without_yes(self):
        r = self._run("--force")
        if "Unsupported" in r.stderr or "Homebrew is required" in r.stderr:
            self.skipTest("no supported package manager on this host")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--yes", r.stderr)

    def test_dry_run_exits_zero_without_installing(self):
        r = self._run("--force", "--dry-run")
        if "Unsupported" in r.stderr or "Homebrew is required" in r.stderr:
            self.skipTest("no supported package manager on this host")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Dry run", r.stdout)

    def test_unknown_flag_rejected(self):
        self.assertEqual(self._run("--bogus").returncode, 2)

    def test_already_installed_short_circuits(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "elixir"
            fake.write_text("#!/bin/sh\necho Elixir fake\n")
            fake.chmod(0o755)
            env = dict(os.environ, CAPSULE_INSTALL_FORCE_FALLBACK="1", PATH=d + os.pathsep + os.environ["PATH"])
            r = subprocess.run(["bash", self.SH], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertIn("already installed", r.stdout)


class PowerShellStaticTests(unittest.TestCase):
    def test_fallback_gates(self):
        text = (ROOT / "scripts" / "install_elixir.ps1").read_text(encoding="utf-8")
        for needle in ("[switch]$Json", "$DryRun", "-not $Yes", "Refusing to install without -Yes",
                       "ConvertTo-Json", "Get-Command elixir"):
            self.assertIn(needle, text)
        self.assertNotIn("Actor", text)


if __name__ == "__main__":
    unittest.main()
