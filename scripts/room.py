#!/usr/bin/env python3
"""
Capsule Corp Check-In Room & Timeclock Engine
Manages multi-AI agent check-ins, active shift tracking, file collision warnings,
heartbeat tracking, concurrency locking, and automatic log pruning.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple, Any
import uuid

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    from .runtime import configure_utf8_stdio
except ImportError:
    from runtime import configure_utf8_stdio

configure_utf8_stdio()

# Max history entries retained to keep logs concise
MAX_HISTORY_ENTRIES = 15
# Shifts older than this without heartbeat or activity are considered stale and auto-expired
STALE_SHIFT_HOURS = 2


@contextmanager
def room_lock(target_dir: Path):
    """Acquire an exclusive cross-process file lock for room state changes."""
    capsule_dir = target_dir / ".capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)
    lock_file = capsule_dir / "room.lock"
    with open(lock_file, "a+") as f:
        if fcntl:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except (AttributeError, OSError):
                pass
        try:
            yield
        finally:
            if fcntl:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except (AttributeError, OSError):
                    pass


def atomic_write_json(path: Path, data: Any) -> None:
    """Write data to temporary file and atomically replace target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f".tmp.{os.getpid()}_{uuid.uuid4().hex[:6]}")
    temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def detect_environment() -> Dict[str, str]:
    """Auto-detect active AI agent and provider. Return 'Unknown' for model if unspecified."""
    env = os.environ
    if env.get("CLAUDE_CODE"):
        return {
            "agent_id": "claude",
            "agent_name": "Claude Code",
            "provider": "Anthropic",
            "model": env.get("CLAUDE_MODEL", "Unknown"),
        }
    if env.get("GEMINI_CLI") or env.get("ANTIGRAVITY"):
        return {
            "agent_id": "gemini",
            "agent_name": "Antigravity / Gemini",
            "provider": "Google",
            "model": env.get("GEMINI_MODEL") or env.get("ANTIGRAVITY_MODEL") or "Unknown",
        }
    if env.get("CODEX"):
        return {
            "agent_id": "codex",
            "agent_name": "OpenAI Codex",
            "provider": "OpenAI",
            "model": env.get("CODEX_MODEL", "Unknown"),
        }
    if env.get("CURSOR_AGENT") or env.get("CURSOR_VERSION"):
        return {
            "agent_id": "cursor",
            "agent_name": "Cursor IDE",
            "provider": "Cursor",
            "model": env.get("CURSOR_MODEL", "Unknown"),
        }
    if env.get("WINDSURF_AGENT"):
        return {
            "agent_id": "windsurf",
            "agent_name": "Windsurf IDE",
            "provider": "Codeium",
            "model": env.get("WINDSURF_MODEL", "Unknown"),
        }
    return {
        "agent_id": env.get("USER", "developer"),
        "agent_name": env.get("USER", "Developer"),
        "provider": "Local",
        "model": env.get("MODEL", "Interactive Session"),
    }


def get_room_paths(target_dir: Path) -> Tuple[Path, Path, Path]:
    capsule_dir = target_dir / ".capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)
    return capsule_dir / "room.json", capsule_dir / "CONFERENCE.md", capsule_dir / "session.json"


def load_room_data(room_path: Path) -> Dict[str, Any]:
    if room_path.exists():
        try:
            data = json.loads(room_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("active_shifts", {})
                data.setdefault("history", [])
                return data
        except Exception:
            pass
    return {"active_shifts": {}, "history": []}


def check_file_conflicts(
    active_shifts: Dict[str, Any],
    files: List[str],
    current_shift_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Detect if any requested files are already claimed by an active shift."""
    conflicts = []
    norm_files = {os.path.normpath(f.strip()) for f in files if f.strip()}
    if not norm_files:
        return []

    for shift_id, shift in active_shifts.items():
        if shift_id == current_shift_id:
            continue
        claimed_norm = {os.path.normpath(f.strip()) for f in shift.get("files", []) if f.strip()}
        overlap = norm_files.intersection(claimed_norm)
        if overlap:
            conflicts.append({
                "shift_id": shift_id,
                "agent_id": shift.get("agent_id", "unknown"),
                "owner_agent": shift.get("agent_id", "unknown"),
                "agent_name": shift.get("agent_name", shift_id),
                "role": shift.get("role", "Worker"),
                "task": shift.get("task", ""),
                "files": sorted(list(overlap)),
            })
    return conflicts


def prune_stale_shifts(data: Dict[str, Any]) -> bool:
    """Move shifts inactive for STALE_SHIFT_HOURS to history with auto-expired notice."""
    now = datetime.now(timezone.utc)
    active = data.get("active_shifts", {})
    stale_keys = []
    changed = False

    for shift_id, shift in active.items():
        last_active_str = shift.get("last_seen_at") or shift.get("clocked_in_at")
        if not last_active_str:
            continue
        try:
            last_active = datetime.fromisoformat(last_active_str.replace("Z", "+00:00"))
            if now - last_active > timedelta(hours=STALE_SHIFT_HOURS):
                stale_keys.append(shift_id)
        except Exception:
            pass

    for key in stale_keys:
        stale_shift = active.pop(key)
        stale_shift["clocked_out_at"] = now.isoformat()
        stale_shift["summary"] = "[Auto-Expired] Inactivity exceeded 2 hours without heartbeat or clock-out."
        data.setdefault("history", []).insert(0, stale_shift)
        changed = True

    # Trim history to MAX_HISTORY_ENTRIES
    if len(data.get("history", [])) > MAX_HISTORY_ENTRIES:
        data["history"] = data["history"][:MAX_HISTORY_ENTRIES]
        changed = True

    return changed


def render_conference_markdown(data: Dict[str, Any], md_path: Path) -> None:
    """Render human-readable Markdown view of the Check-In Room."""
    lines = [
        "# 🏛️ Capsule Corp Check-In Room & Timeclock",
        f"**Last Sync:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## 🟢 Active Shifts (Currently On Shift)",
    ]

    active = data.get("active_shifts", {})
    if not active:
        lines.append("*(No active agents currently clocked in. The workspace is idle.)*")
    else:
        for shift_id, shift in active.items():
            lines.append(f"### {shift.get('agent_name', shift_id)} (`{shift_id}`)")
            lines.append(f"- **Company / Model:** {shift.get('provider', 'Unknown')} ({shift.get('model', 'Unknown')})")
            lines.append(f"- **Role:** {shift.get('role', 'Builder')}")
            lines.append(f"- **Task:** {shift.get('task', 'No task description')}")
            files = shift.get("files", [])
            if files:
                lines.append(f"- **Active Files:** `{', '.join(files)}`")
            lines.append(f"- **Clocked In At:** {shift.get('clocked_in_at', 'Unknown')}")
            lines.append(f"- **Last Seen:** {shift.get('last_seen_at', 'Unknown')}")
            lines.append("")

    lines.extend([
        "",
        "## 🏁 Recent Clock-Outs & Handoffs",
    ])

    history = data.get("history", [])
    if not history:
        lines.append("*(No recent shift history.)*")
    else:
        for entry in history[:10]:
            lines.append(f"- **{entry.get('agent_name', 'Agent')}** ({entry.get('provider', 'Local')} | {entry.get('role', 'Worker')})")
            lines.append(f"  - **Summary:** {entry.get('summary', 'Finished task')}")
            lines.append(f"  - **Time:** {entry.get('clocked_out_at', 'Unknown')}")

    lines.append("")
    atomic_write_json(md_path.with_suffix(".tmp.md"), "\n".join(lines))
    os.replace(md_path.with_suffix(".tmp.md"), md_path)


def clock_in(
    target_dir: Path,
    agent: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    role: Optional[str] = None,
    task: Optional[str] = None,
    files: Optional[List[str]] = None,
    session: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Clock in an agent session to the check-in room."""
    with room_lock(target_dir):
        detected = detect_environment()
        agent_id = (agent or detected["agent_id"]).lower()
        agent_name = agent or detected["agent_name"]
        provider_name = provider or detected["provider"]
        model_name = model or detected["model"]
        role_name = role or "Builder (@Goku)"
        task_desc = task or "General task implementation"
        files_list = [f.strip() for f in files if f.strip()] if files else []

        room_json, conf_md, session_file = get_room_paths(target_dir)
        data = load_room_data(room_json)
        prune_stale_shifts(data)

        # Check for conflicting file claims
        conflicts = check_file_conflicts(data.get("active_shifts", {}), files_list)
        if conflicts and not force:
            return {
                "error": "file_conflict",
                "conflicts": conflicts,
                "message": "One or more files are actively claimed by another shift. Use --force to override."
            }

        shift_id = session or f"shift_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        shift_info = {
            "shift_id": shift_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "provider": provider_name,
            "model": model_name,
            "role": role_name,
            "task": task_desc,
            "files": files_list,
            "clocked_in_at": now_iso,
            "last_seen_at": now_iso,
            "forced_override": bool(conflicts and force),
        }

        data["active_shifts"][shift_id] = shift_info
        atomic_write_json(room_json, data)
        render_conference_markdown(data, conf_md)

        # Record active local session
        try:
            atomic_write_json(session_file, {"shift_id": shift_id, "agent_id": agent_id})
        except Exception:
            pass

        return shift_info


def clock_out(
    target_dir: Path,
    session: Optional[str] = None,
    agent: Optional[str] = None,
    summary: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Clock out an agent from the check-in room requiring an exact session or agent match."""
    with room_lock(target_dir):
        detected = detect_environment()
        target_agent_id = (agent or detected["agent_id"]).lower() if agent or not session else None
        summary_text = summary or "Task completed and verified."

        room_json, conf_md, session_file = get_room_paths(target_dir)
        data = load_room_data(room_json)
        prune_stale_shifts(data)

        active = data.get("active_shifts", {})
        target_shift_id = None

        session = session or os.environ.get("CAPSULE_SESSION")
        if session:
            if session in active:
                target_shift_id = session
            else:
                return None
        else:
            if target_agent_id:
                # Find shifts matching agent_id
                matching_shifts = [sid for sid, s in active.items() if s.get("agent_id") == target_agent_id]
                if len(matching_shifts) == 1:
                    target_shift_id = matching_shifts[0]
                elif len(matching_shifts) > 1:
                    return {
                        "error": "ambiguous_session",
                        "matches": matching_shifts,
                        "message": f"Multiple active shifts for agent '{target_agent_id}'. Specify --session <id>."
                    }
            elif session_file.exists():
                try:
                    s_data = json.loads(session_file.read_text(encoding="utf-8"))
                    cand_id = s_data.get("shift_id")
                    if cand_id in active:
                        target_shift_id = cand_id
                except Exception:
                    pass

        if not target_shift_id:
            # NO silent fallback to clocking out an unrelated agent!
            return None

        shift = active.pop(target_shift_id)
        shift["clocked_out_at"] = datetime.now(timezone.utc).isoformat()
        shift["summary"] = summary_text

        data.setdefault("history", []).insert(0, shift)
        if len(data["history"]) > MAX_HISTORY_ENTRIES:
            data["history"] = data["history"][:MAX_HISTORY_ENTRIES]

        atomic_write_json(room_json, data)
        render_conference_markdown(data, conf_md)

        # Clear session file if matching
        if session_file.exists():
            try:
                s_data = json.loads(session_file.read_text(encoding="utf-8"))
                if s_data.get("shift_id") == target_shift_id:
                    session_file.unlink(missing_ok=True)
            except Exception:
                pass

        return shift


def heartbeat(
    target_dir: Path,
    session: Optional[str] = None,
    agent: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Send a heartbeat to update the last_seen_at timestamp and prevent stale expiration."""
    with room_lock(target_dir):
        detected = detect_environment()
        target_agent_id = (agent or detected["agent_id"]).lower() if agent or not session else None

        room_json, conf_md, session_file = get_room_paths(target_dir)
        data = load_room_data(room_json)
        prune_stale_shifts(data)

        active = data.get("active_shifts", {})
        target_shift_id = None

        if session and session in active:
            target_shift_id = session
        elif session_file.exists():
            try:
                s_data = json.loads(session_file.read_text(encoding="utf-8"))
                cand_id = s_data.get("shift_id")
                if cand_id in active:
                    target_shift_id = cand_id
            except Exception:
                pass

        if not target_shift_id and target_agent_id:
            matching = [sid for sid, s in active.items() if s.get("agent_id") == target_agent_id]
            if len(matching) == 1:
                target_shift_id = matching[0]

        if not target_shift_id or target_shift_id not in active:
            return None

        shift = active[target_shift_id]
        shift["last_seen_at"] = datetime.now(timezone.utc).isoformat()
        shift["ok"] = True
        atomic_write_json(room_json, data)
        render_conference_markdown(data, conf_md)
        return shift


def clear_room(target_dir: Path) -> None:
    """Clear all active shifts and reset the room."""
    with room_lock(target_dir):
        room_json, conf_md, session_file = get_room_paths(target_dir)
        data = load_room_data(room_json)
        data["active_shifts"] = {}
        atomic_write_json(room_json, data)
        render_conference_markdown(data, conf_md)
        session_file.unlink(missing_ok=True)


def print_room(target_dir: Path, as_json: bool = False) -> int:
    """Display the Check-In Room status."""
    with room_lock(target_dir):
        room_json, conf_md, _ = get_room_paths(target_dir)
        data = load_room_data(room_json)
        pruned = prune_stale_shifts(data)
        if pruned:
            atomic_write_json(room_json, data)
            render_conference_markdown(data, conf_md)

    if as_json:
        print(json.dumps(data, indent=2))
        return 0

    print("=" * 72)
    print(" 🏛️  CAPSULE CORP CHECK-IN ROOM & TIMECLOCK")
    print("=" * 72)

    active = data.get("active_shifts", {})
    if not active:
        print(" ON SHIFT: None (Workspace is idle)")
    else:
        print(f" ON SHIFT ({len(active)} active session{'s' if len(active) > 1 else ''}):")
        for shift_id, shift in active.items():
            print(f"   🟢 {shift.get('agent_name', shift_id)} (Session: {shift_id})")
            print(f"      • Company / Model: {shift.get('provider')} ({shift.get('model')})")
            print(f"      • Role:            {shift.get('role')}")
            print(f"      • Task:            {shift.get('task')}")
            files = shift.get("files", [])
            if files:
                print(f"      • Active Files:    {', '.join(files)}")
            print(f"      • Clocked In At:   {shift.get('clocked_in_at')}")
            print(f"      • Last Activity:   {shift.get('last_seen_at')}")

    # File collision analysis
    all_claimed = {}
    collisions = []
    for shift_id, shift in active.items():
        for f in shift.get("files", []):
            norm = os.path.normpath(f.strip())
            all_claimed.setdefault(norm, []).append((shift_id, shift.get("agent_name", shift_id)))

    for f, claimers in all_claimed.items():
        if len(claimers) > 1:
            collisions.append((f, claimers))

    if collisions:
        print("-" * 72)
        print(" ⚠️  FILE COLLISION ALERT:")
        for f, claimers in collisions:
            holder_str = ", ".join(f"{name} ({sid})" for sid, name in claimers)
            print(f"   Conflict on: {f}")
            print(f"      Overlapping owners: {holder_str}")
    elif all_claimed:
        print("-" * 72)
        print(f" 📂 Claimed Active Files ({len(all_claimed)}): {', '.join(sorted(all_claimed.keys()))}")

    # History
    history = data.get("history", [])
    if history:
        print("-" * 72)
        print(" RECENT LOGS (Last Clock-Outs):")
        for entry in history[:5]:
            print(f"   🏁 {entry.get('agent_name')} ({entry.get('provider')} | {entry.get('role', 'Worker')})")
            print(f"      • {entry.get('summary')}")
            print(f"      • Time: {entry.get('clocked_out_at')}")

    print("=" * 72)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Capsule Corp Check-In Room & Timeclock")
    subparsers = parser.add_subparsers(dest="action")

    # room / status
    room_parser = subparsers.add_parser("status", help="View active shifts and recent handoffs")
    room_parser.add_argument("target_dir", nargs="?", default=".", help="Project directory")
    room_parser.add_argument("--json", action="store_true", help="Output JSON results")
    room_parser.add_argument("--clean", action="store_true", help="Clear all active shifts")

    # clock-in
    in_parser = subparsers.add_parser("clock-in", help="Clock in to an active work shift")
    in_parser.add_argument("target_dir", nargs="?", default=".", help="Project directory")
    in_parser.add_argument("--session", help="Session identifier (auto-generated if omitted)")
    in_parser.add_argument("--agent", help="Agent identifier (auto-detected if omitted)")
    in_parser.add_argument("--provider", help="AI provider / company (auto-detected if omitted)")
    in_parser.add_argument("--model", help="Model name (auto-detected if omitted)")
    in_parser.add_argument("--role", help="Assumed role (e.g. Builder, Product, Reviewer)")
    in_parser.add_argument("--task", required=True, help="Task description")
    in_parser.add_argument("--files", help="Comma-separated files or surfaces claimed")
    in_parser.add_argument("--force", action="store_true", help="Override active file claim conflicts")

    # clock-out
    out_parser = subparsers.add_parser("clock-out", help="Clock out from active work shift")
    out_parser.add_argument("target_dir", nargs="?", default=".", help="Project directory")
    out_parser.add_argument("--session", help="Session identifier to clock out")
    out_parser.add_argument("--agent", help="Agent identifier (auto-detected if omitted)")
    out_parser.add_argument("--summary", help="Summary of work completed and verification status")

    # heartbeat
    hb_parser = subparsers.add_parser("heartbeat", help="Send heartbeat to keep shift alive")
    hb_parser.add_argument("target_dir", nargs="?", default=".", help="Project directory")
    hb_parser.add_argument("--session", help="Session identifier")

    args = parser.parse_args(argv)
    action = args.action or "status"
    target_dir = Path(getattr(args, "target_dir", ".")).resolve()

    if action == "status":
        if getattr(args, "clean", False):
            clear_room(target_dir)
            print("✓ Check-in room cleared. All active shifts reset.")
            return 0
        return print_room(target_dir, as_json=getattr(args, "json", False))

    if action == "clock-in":
        files_list = [f.strip() for f in args.files.split(",")] if args.files else []
        res = clock_in(
            target_dir=target_dir,
            agent=args.agent,
            provider=args.provider,
            model=args.model,
            role=args.role,
            task=args.task,
            files=files_list,
            session=args.session,
            force=args.force,
        )
        if "error" in res and res["error"] == "file_conflict":
            print("Error: Conflicting file claim(s) detected:", file=sys.stderr)
            for c in res["conflicts"]:
                print(f"  • {', '.join(c['files'])} claimed by {c['agent_name']} ({c['shift_id']})", file=sys.stderr)
                print(f"    Role: {c['role']} | Task: {c['task']}", file=sys.stderr)
            print("Pass --force to override ownership.", file=sys.stderr)
            return 1

        print(f"✓ Clocked in: {res['agent_name']} (Session: {res['shift_id']})")
        print(f"  Company / Model: {res['provider']} ({res['model']})")
        print(f"  Role: {res['role']} | Task: {res['task']}")
        if res.get("files"):
            print(f"  Claimed files: {', '.join(res['files'])}")
        if res.get("forced_override"):
            print("  ⚠️ Claimed with forced conflict override.")
        return 0

    if action == "clock-out":
        res = clock_out(
            target_dir=target_dir,
            session=args.session,
            agent=args.agent,
            summary=args.summary,
        )
        if isinstance(res, dict) and "error" in res:
            print(f"Error: {res['message']}", file=sys.stderr)
            return 1
        if res:
            print(f"✓ Clocked out: {res['agent_name']} (Session: {res['shift_id']})")
            print(f"  Summary: {res.get('summary', 'Done')}")
            return 0
        else:
            print("Notice: No matching active shift found to clock out.", file=sys.stderr)
            return 1

    if action == "heartbeat":
        res = heartbeat(target_dir=target_dir, session=args.session)
        if res:
            print(f"✓ Heartbeat recorded: {res['agent_name']} (Session: {res['shift_id']}) at {res['last_seen_at']}")
            return 0
        else:
            print("Notice: No active shift found for heartbeat.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
