#!/usr/bin/env python3
"""Trust modes (--trust / --strict / default WARN), gitignored gate config, corrupt room.json."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CAPSULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))

import check_project
import verify_project

CHECK = str(CAPSULE_ROOT / "scripts" / "check_project.py")
OK_CMD = "%s -c pass" % sys.executable


def git(root, *args):
    subprocess.run(["git", *args], cwd=str(root), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_project(root, cfg=None):
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / "README").write_text("x\n")
    if cfg is not None:
        (root / "capsule.json").write_text(json.dumps(cfg))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")


def names(res):
    return {c["name"]: c for c in res["checks"]}


class TestTrustModes(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("CAPSULE_TRUST", None)

    def tearDown(self):
        self.env.stop()

    def test_resolve_mode(self):
        r = verify_project.resolve_trust_mode
        self.assertEqual(r(), "default")
        self.assertEqual(r(trust_flag=True), "trust")
        self.assertEqual(r(strict_flag=True), "strict")
        os.environ["CAPSULE_TRUST"] = "1"
        self.assertEqual(r(), "trust")
        self.assertEqual(r(strict_flag=True), "strict")  # flag beats env
        os.environ["CAPSULE_TRUST"] = "0"
        self.assertEqual(r(), "strict")
        with self.assertRaises(ValueError):
            r(True, True)

    def test_default_runs_with_warning_naming_commands(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_project(root, {"test": OK_CMD})
            res = check_project.run_project_checks(root, skip_secrets=True)
            c = names(res)
            self.assertEqual(c["Tests"]["status"], "PASSED")
            warn = c["Project Code Trust"]
            self.assertEqual(warn["status"], "WARNING")
            self.assertIn(OK_CMD, warn["output"])
            self.assertIn("strict", warn["summary"])
            self.assertEqual(res["verdict"], "PASS")

    def test_trust_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_project(root, {"test": OK_CMD})
            res = check_project.run_project_checks(root, skip_secrets=True, trust_mode="trust")
            self.assertNotIn("Project Code Trust", names(res))
            self.assertEqual(res["verdict"], "PASS")
            os.environ["CAPSULE_TRUST"] = "1"
            res = check_project.run_project_checks(root, skip_secrets=True)
            self.assertNotIn("Project Code Trust", names(res))

    def test_strict_skips_project_commands_and_is_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            marker = root / "ran.txt"
            cmd = "%s -c \"open('ran.txt','w').write('x')\"" % sys.executable
            make_project(root, {"test": cmd})
            res = check_project.run_project_checks(root, skip_secrets=True, trust_mode="strict")
            c = names(res)
            self.assertEqual(c["Tests"]["status"], "SKIPPED")
            self.assertIn("strict", c["Tests"]["summary"].lower())
            self.assertFalse(marker.exists())
            self.assertNotEqual(res["verdict"], "PASS")

    def test_strict_via_env_and_override_not_project_defined(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_project(root, {"test": "false"})
            os.environ["CAPSULE_TRUST"] = "0"
            res = check_project.run_project_checks(root, skip_secrets=True, test_cmd_override=OK_CMD)
            self.assertEqual(names(res)["Tests"]["status"], "PASSED")  # operator-supplied command
            self.assertNotIn("Project Code Trust", names(res))

    def test_cli_flags_and_help(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_project(root, {"test": OK_CMD})
            env = {k: v for k, v in os.environ.items() if k != "CAPSULE_TRUST"}
            def run(*a):
                return subprocess.run([sys.executable, CHECK, str(root), "--skip-secrets", *a],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            p = run("--trust")
            self.assertEqual(p.returncode, 0, p.stdout)
            self.assertNotIn("Project Code Trust", p.stdout)
            p = run()
            self.assertEqual(p.returncode, 0)
            self.assertIn("Project Code Trust", p.stdout)
            p = run("--strict")
            self.assertEqual(p.returncode, 1)
            self.assertIn("SKIP", p.stdout)
            self.assertNotEqual(run("--trust", "--strict").returncode, 0)
            h = run("--help").stdout
            self.assertIn("--trust", h)
            self.assertIn("CAPSULE_TRUST", h)


class TestIgnoredConfig(unittest.TestCase):
    def test_gitignored_config_warns(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_project(root)
            (root / ".gitignore").write_text("capsule.json\n")
            git(root, "add", ".gitignore")
            git(root, "commit", "-q", "-m", "ignore")
            (root / "capsule.json").write_text(json.dumps({"test": OK_CMD}))
            warns = verify_project.config_drift_warnings(root)
            self.assertEqual(len(warns), 1, warns)
            self.assertIn("gitignored", warns[0])
            res = check_project.run_project_checks(root, skip_secrets=True, trust_mode="trust")
            self.assertIn("Config Integrity", names(res))


class TestCorruptRoom(unittest.TestCase):
    def test_check_warns_on_corrupt_room_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_project(root, {"test": OK_CMD})
            (root / ".capsule").mkdir()
            (root / ".capsule" / "room.json").write_text("{not json")
            res = check_project.run_project_checks(root, skip_secrets=True, trust_mode="trust")
            room = names(res)["Check-In Room"]
            self.assertEqual(room["status"], "WARNING")
            self.assertIn("CORRUPT", room["summary"])
            self.assertEqual(res["verdict"], "PASS")

    def test_room_command_still_fails_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule").mkdir()
            (root / ".capsule" / "room.json").write_text("{not json")
            p = subprocess.run([str(CAPSULE_ROOT / "bin" / "capsule"), "room", str(root)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("room.json", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
