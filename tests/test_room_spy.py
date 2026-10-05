#!/usr/bin/env python3
"""Regression tests for scripts/room.py and scripts/spy_watchdog.py (all in temp dirs)."""

import contextlib
import io
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

import room  # noqa: E402
import spy_watchdog  # noqa: E402
from room import (  # noqa: E402
    RoomCorruptError, check_file_conflicts, clock_in, clock_out, detect_environment,
    heartbeat, load_room_data, normalize_claim,
)
from spy_watchdog import audit_agent_drift, get_git_status_files  # noqa: E402


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
        cwd=str(cwd), check=True, capture_output=True,
    )


def make_repo(root):
    git(root, "init", "-q")
    (root / "seed.txt").write_text("x", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")


class TestConferenceMarkdown(unittest.TestCase):
    def test_conference_md_is_plain_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            clock_in(root, agent="goku", task="Do thing", files=["a.py"])
            text = (root / ".capsule" / "CONFERENCE.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# "), text[:40])
            self.assertNotIn("\\n", text)
            self.assertIn("Do thing", text)


class TestSessionResolution(unittest.TestCase):
    def test_clock_out_uses_session_slot_without_agent(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPSULE_SESSION", None)
            root = Path(d)
            p = clock_in(root, agent="piccolo", task="t")  # agent differs from detected one
            # intentional change: the last-clock-in slot no longer grants a different detected agent access
            denied = clock_out(root, summary="done")
            self.assertTrue(denied is None or "error" in denied)
            out = clock_out(root, agent="piccolo", summary="done", token=p["session_token"])
            self.assertIsNotNone(out)
            self.assertEqual(out["agent_id"], "piccolo")
            self.assertFalse((root / ".capsule" / "session.json").exists())

    def test_explicit_agent_with_two_shifts_is_still_ambiguous(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            first = clock_in(root, agent="codex", task="1", files=["a"])
            clock_in(root, agent="codex", task="2", files=["b"], token=first["session_token"])
            self.assertEqual(clock_out(root, agent="codex")["error"], "ambiguous_session")
            self.assertEqual(heartbeat(root, agent="codex")["error"], "ambiguous_session")

    def test_heartbeat_and_clock_out_agree_on_env_session(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            s1 = clock_in(root, agent="codex", task="1", files=["a"])
            clock_in(root, agent="codex", task="2", files=["b"], token=s1["session_token"])
            with patch.dict(os.environ, {"CAPSULE_SESSION": s1["shift_id"], "CAPSULE_SESSION_TOKEN": s1["session_token"]}):
                self.assertEqual(heartbeat(root)["shift_id"], s1["shift_id"])
                self.assertEqual(clock_out(root)["shift_id"], s1["shift_id"])

    def test_session_slot_is_last_clock_in(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            clock_in(root, agent="a1", task="1", files=["a"])
            s2 = clock_in(root, agent="a2", task="2", files=["b"])
            slot = json.loads((root / ".capsule" / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(slot["shift_id"], s2["shift_id"])


class TestCorruptRoom(unittest.TestCase):
    def test_corrupt_room_backed_up_and_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            clock_in(root, agent="goku", task="t")
            rj = root / ".capsule" / "room.json"
            rj.write_text("{not json", encoding="utf-8")
            with self.assertRaises(RoomCorruptError):
                clock_in(root, agent="x", task="t2")
            self.assertEqual(rj.read_text(encoding="utf-8"), "{not json")
            backups = list((root / ".capsule").glob("room.json.corrupt-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "{not json")

    def test_active_shifts_must_be_dict(self):
        with tempfile.TemporaryDirectory() as d:
            rj = Path(d) / "room.json"
            rj.write_text(json.dumps({"active_shifts": [], "history": []}), encoding="utf-8")
            with self.assertRaises(RoomCorruptError):
                load_room_data(rj)

    def test_cli_reports_corrupt_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".capsule").mkdir()
            (root / ".capsule" / "room.json").write_text("[]", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = room.main(["status", str(root)])
            self.assertEqual(rc, 1)
            self.assertIn("corrupt", err.getvalue())

    def test_windows_lock_path_uses_msvcrt(self):
        calls = []

        class FakeMsvcrt:
            LK_LOCK, LK_UNLCK = 1, 0

            @staticmethod
            def locking(fd, mode, n):
                calls.append(mode)

        with tempfile.TemporaryDirectory() as d, \
                patch.object(room, "fcntl", None), patch.object(room, "msvcrt", FakeMsvcrt):
            with room.room_lock(Path(d)):
                pass
        self.assertEqual(calls, [1, 0])


class TestReadOnlyNoSideEffects(unittest.TestCase):
    def test_read_commands_do_not_create_capsule_dir(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)  # spy fails closed (exit 2) outside a git work tree
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(room.main(["status", str(root)]), 0)
                self.assertEqual(spy_watchdog.main([str(root)]), 0)
            self.assertFalse((root / ".capsule").exists())

    def test_nonexistent_dir_errors_without_creating(self):
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "nope"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(room.main(["status", str(missing)]), 2)
                self.assertEqual(spy_watchdog.main([str(missing)]), 2)
            self.assertFalse(missing.exists())
            self.assertIn("does not exist", err.getvalue())

    def test_get_room_paths_is_pure(self):
        with tempfile.TemporaryDirectory() as d:
            room.get_room_paths(Path(d))
            self.assertFalse((Path(d) / ".capsule").exists())


class TestEnvironment(unittest.TestCase):
    def test_claudecode_env_var(self):
        with patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual(detect_environment()["agent_id"], "claude")

    def test_specific_agent_wins_over_inherited_claudecode(self):
        with patch.dict(os.environ, {"CLAUDECODE": "1", "GEMINI_CLI": "1"}, clear=True):
            self.assertEqual(detect_environment()["agent_id"], "gemini")

    def test_username_fallback(self):
        with patch.dict(os.environ, {"USERNAME": "winuser"}, clear=True):
            self.assertEqual(detect_environment()["agent_id"], "winuser")


class TestClaimMatching(unittest.TestCase):
    def test_directory_prefix_conflict(self):
        shifts = {"s1": {"files": ["src/"], "agent_id": "a"}}
        self.assertTrue(check_file_conflicts(shifts, ["src/auth.py"]))
        shifts = {"s1": {"files": ["src/auth.py"], "agent_id": "a"}}
        self.assertTrue(check_file_conflicts(shifts, ["src"]))
        self.assertFalse(check_file_conflicts(shifts, ["src2/auth.py"]))
        self.assertFalse(check_file_conflicts(shifts, ["src/auth.pyc"]))

    def test_absolute_vs_relative(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shifts = {"s1": {"files": [str(root / "src" / "a.py")], "agent_id": "a"}}
            self.assertTrue(check_file_conflicts(shifts, ["./src/a.py"], root=root))
            self.assertEqual(normalize_claim(str(root / "x" / "y"), root), "x/y")

    def test_clock_in_blocks_dir_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            clock_in(root, agent="goku", files=["src"])
            res = clock_in(root, agent="vegeta", files=["src/models.py"])
            self.assertEqual(res.get("error"), "file_conflict")

    def test_case_insensitive_when_fs_is(self):
        with patch.object(room, "fs_is_case_insensitive", return_value=True):
            shifts = {"s1": {"files": ["SRC/A.py"], "agent_id": "a"}}
            self.assertTrue(check_file_conflicts(shifts, ["src/a.py"]))
        with patch.object(room, "fs_is_case_insensitive", return_value=False):
            self.assertFalse(check_file_conflicts(shifts, ["src/a.py"]))


class TestSpyGit(unittest.TestCase):
    def test_untracked_files_listed_individually_and_dir_claim_covers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            (root / "pkg").mkdir()
            (root / "pkg" / "a.py").write_text("1", encoding="utf-8")
            (root / "pkg" / "b.py").write_text("1", encoding="utf-8")
            files = get_git_status_files(root)
            self.assertEqual(files["untracked"], ["pkg/a.py", "pkg/b.py"])
            clock_in(root, agent="goku", task="t", files=["pkg"])
            report = audit_agent_drift(root)
            self.assertEqual(report["unclaimed_files"], [])
            self.assertEqual(report["verdict"], "PASS")

    def test_absolute_claim_matches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            (root / "a.py").write_text("1", encoding="utf-8")
            clock_in(root, agent="goku", task="t", files=[str(root / "a.py")])
            self.assertEqual(audit_agent_drift(root)["unclaimed_files"], [])

    def test_rename_handled(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            git(root, "mv", "seed.txt", "moved.txt")
            files = get_git_status_files(root)
            self.assertIn("moved.txt", files["modified"])
            self.assertIn("seed.txt", files["deleted"])
            self.assertNotIn("seed.txt -> moved.txt", files["modified"])

    def test_filenames_with_spaces_unquoted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            (root / "my file.txt").write_text("1", encoding="utf-8")
            self.assertEqual(get_git_status_files(root)["untracked"], ["my file.txt"])

    def test_subdir_target_paths_relative_to_target(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            sub = root / "sub"
            sub.mkdir()
            (sub / "x.py").write_text("1", encoding="utf-8")
            (root / "outside.py").write_text("1", encoding="utf-8")
            files = get_git_status_files(sub)
            self.assertEqual(files["untracked"], ["x.py"])
            clock_in(sub, agent="goku", task="t", files=["x.py"])
            self.assertEqual(audit_agent_drift(sub)["unclaimed_files"], [])

    def test_ignore_is_anchored_to_capsule_dir(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root)
            (root / ".capsulerc.json").write_text("{}", encoding="utf-8")
            (root / ".capsule").mkdir()
            (root / ".capsule" / "room.json").write_text("{}", encoding="utf-8")
            files = get_git_status_files(root)
            self.assertEqual(files["untracked"], [".capsulerc.json"])


if __name__ == "__main__":
    unittest.main()
