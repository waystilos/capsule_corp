#!/usr/bin/env python3
"""
Capsule Corp Check-In Room & Timeclock Engine
Manages multi-AI agent check-ins, active shift tracking, file collision warnings,
and automatic log pruning.
"""

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple, Any

try:
    from .runtime import configure_utf8_stdio
except ImportError:
    from runtime import configure_utf8_stdio

configure_utf8_stdio()

# Max history entries retained to keep logs concise
MAX_HISTORY_ENTRIES = 15
# Shifts older than this are considered stale/abandoned and auto-expired
STALE_SHIFT_HOURS = 2


def detect_environment() -> Dict[str, str]:
    """Auto-detect the active AI agent, provider, and model from environment variables."""
    env = os.environ
    if env.get("CLAUDE_CODE"):
        return {
            "agent_id": "claude",
            "agent_name": "Claude Code",
            "provider": "Anthropic",
            "model": env.get("CLAUDE_MODEL", "Claude 3.7 Sonnet"),
        }
    if env.get("GEMINI_CLI") or env.get("ANTIGRAVITY"):
        return {
            "agent_id": "gemini",
            "agent_name": "Antigravity / Gemini",
            "provider": "Google",
            "model": env.get("GEMINI_MODEL", "Gemini 2.5 Pro"),
        }
    if env.get("CODEX"):
        return {
            "agent_id": "codex",
            "agent_name": "OpenAI Codex",
            "provider": "OpenAI",
            "model": env.get("CODEX_MODEL", "o3-mini / GPT-4o"),
        }
    if env.get("CURSOR_AGENT") or env.get("CURSOR_VERSION"):
        return {
            "agent_id": "cursor",
            "agent_name": "Cursor IDE",
            "provider": "Cursor",
            "model": "Composer Agent",
        }
    if env.get("WINDSURF_AGENT"):
        return {
            "agent_id": "windsurf",
            "agent_name": "Windsurf IDE",
            "provider": "Codeium",
            "model": "Cascade Agent",
        }
    return {
        "agent_id": env.get("USER", "developer"),
        "agent_name": env.get("USER", "Developer"),
        "provider": "Local",
        "model": "Interactive Session",
    }


def get_room_paths(target_dir: Path) -> Tuple[Path, Path]:
    capsule_dir = target_dir / ".capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)
    return capsule_dir / "room.json", capsule_dir / "CONFERENCE.md"


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


def prune_stale_shifts(data: Dict[str, Any]) -> bool:
    """Move shifts older than STALE_SHIFT_HOURS to history with auto-expired notice."""
    now = datetime.now(timezone.utc)
    active = data.get("active_shifts", {})
    stale_keys = []
    changed = False

    for agent_id, shift in active.items():
        clocked_in_str = shift.get("clocked_in_at")
        if not clocked_in_str:
            continue
        try:
            clocked_in = datetime.fromisoformat(clocked_in_str.replace("Z", "+00:00"))
            if now - clocked_in > timedelta(hours=STALE_SHIFT_HOURS):
                stale_keys.append(agent_id)
        except Exception:
            pass

    for key in stale_keys:
        stale_shift = active.pop(key)
        stale_shift["clocked_out_at"] = now.isoformat()
        stale_shift["summary"] = "[Auto-Expired] Shift exceeded 2-hour activity limit without clock-out."
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
        for agent_id, shift in active.items():
            lines.append(f"### {shift.get('agent_name', agent_id)} (`{shift.get('provider', 'Unknown')}` / `{shift.get('model', 'Unknown')}`)")
            lines.append(f"- **Role:** {shift.get('role', 'Builder')}")
            lines.append(f"- **Task:** {shift.get('task', 'No task description')}")
            files = shift.get("files", [])
            if files:
                lines.append(f"- **Active Files (Caution):** `{', '.join(files)}`")
            lines.append(f"- **Clocked In At:** {shift.get('clocked_in_at', 'Unknown')}")
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
    md_path.write_text("\n".join(lines), encoding="utf-8")


def clock_in(
    target_dir: Path,
    agent: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    role: Optional[str] = None,
    task: Optional[str] = None,
    files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Clock in an agent to the check-in room."""
    detected = detect_environment()
    agent_id = (agent or detected["agent_id"]).lower()
    agent_name = agent or detected["agent_name"]
    provider_name = provider or detected["provider"]
    model_name = model or detected["model"]
    role_name = role or "Builder (@Goku)"
    task_desc = task or "General task implementation"
    files_list = files or []

    room_json, conf_md = get_room_paths(target_dir)
    data = load_room_data(room_json)
    prune_stale_shifts(data)

    now_iso = datetime.now(timezone.utc).isoformat()
    shift_info = {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "provider": provider_name,
        "model": model_name,
        "role": role_name,
        "task": task_desc,
        "files": files_list,
        "clocked_in_at": now_iso,
    }

    data["active_shifts"][agent_id] = shift_info
    room_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    render_conference_markdown(data, conf_md)
    return shift_info


def clock_out(
    target_dir: Path,
    agent: Optional[str] = None,
    summary: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Clock out an agent from the check-in room."""
    detected = detect_environment()
    agent_id = (agent or detected["agent_id"]).lower()
    summary_text = summary or "Task completed and verified."

    room_json, conf_md = get_room_paths(target_dir)
    data = load_room_data(room_json)
    prune_stale_shifts(data)

    active = data.get("active_shifts", {})
    if agent_id not in active:
        # Check if there is only 1 active shift; clock it out
        if len(active) == 1:
            agent_id = next(iter(active.keys()))
        else:
            return None

    shift = active.pop(agent_id)
    shift["clocked_out_at"] = datetime.now(timezone.utc).isoformat()
    shift["summary"] = summary_text

    data.setdefault("history", []).insert(0, shift)
    if len(data["history"]) > MAX_HISTORY_ENTRIES:
        data["history"] = data["history"][:MAX_HISTORY_ENTRIES]

    room_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    render_conference_markdown(data, conf_md)
    return shift


def clear_room(target_dir: Path) -> None:
    """Clear all active shifts and reset the room."""
    room_json, conf_md = get_room_paths(target_dir)
    data = load_room_data(room_json)
    data["active_shifts"] = {}
    room_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    render_conference_markdown(data, conf_md)


def print_room(target_dir: Path, as_json: bool = False) -> int:
    """Display the Check-In Room status."""
    room_json, conf_md = get_room_paths(target_dir)
    data = load_room_data(room_json)
    pruned = prune_stale_shifts(data)
    if pruned:
        room_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
        print(f" ON SHIFT ({len(active)} active agent{'s' if len(active) > 1 else ''}):")
        for agent_id, shift in active.items():
            print(f"   🟢 {shift.get('agent_name', agent_id)}")
            print(f"      • Company / Model: {shift.get('provider')} ({shift.get('model')})")
            print(f"      • Role:            {shift.get('role')}")
            print(f"      • Task:            {shift.get('task')}")
            files = shift.get("files", [])
            if files:
                print(f"      • Active Files:    {', '.join(files)}")
            print(f"      • Clocked In At:   {shift.get('clocked_in_at')}")

    # File collision warning
    hot_files = []
    for shift in active.values():
        hot_files.extend(shift.get("files", []))
    if hot_files:
        print("-" * 72)
        print(" ⚠️  ACTIVE FILE CAUTION:")
        print(f"   Currently modified by active shift: {', '.join(set(hot_files))}")

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
    in_parser.add_argument("--agent", help="Agent identifier (auto-detected if omitted)")
    in_parser.add_argument("--provider", help="AI provider / company (auto-detected if omitted)")
    in_parser.add_argument("--model", help="Model name (auto-detected if omitted)")
    in_parser.add_argument("--role", help="Assumed role (e.g. Builder, Product, Reviewer)")
    in_parser.add_argument("--task", required=True, help="Task description")
    in_parser.add_argument("--files", help="Comma-separated files or surfaces claimed")

    # clock-out
    out_parser = subparsers.add_parser("clock-out", help="Clock out from active work shift")
    out_parser.add_argument("target_dir", nargs="?", default=".", help="Project directory")
    out_parser.add_argument("--agent", help="Agent identifier (auto-detected if omitted)")
    out_parser.add_argument("--summary", help="Summary of work completed and verification status")

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
        shift = clock_in(
            target_dir=target_dir,
            agent=args.agent,
            provider=args.provider,
            model=args.model,
            role=args.role,
            task=args.task,
            files=files_list,
        )
        print(f"✓ Clocked in: {shift['agent_name']} ({shift['provider']} / {shift['model']})")
        print(f"  Role: {shift['role']} | Task: {shift['task']}")
        if shift["files"]:
            print(f"  Claimed files: {', '.join(shift['files'])}")
        return 0

    if action == "clock-out":
        shift = clock_out(
            target_dir=target_dir,
            agent=args.agent,
            summary=args.summary,
        )
        if shift:
            print(f"✓ Clocked out: {shift['agent_name']} ({shift['provider']})")
            print(f"  Summary: {shift.get('summary', 'Done')}")
            return 0
        else:
            print("Notice: No matching active shift found to clock out.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
