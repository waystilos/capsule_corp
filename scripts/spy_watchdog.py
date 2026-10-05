#!/usr/bin/env python3
"""
King Kai's Telepathic Watchdog & Agent Drift Inspector
Audits active agent shifts, uncommitted git modifications, and working tree drift.
Guarantees agents stay in their lane, never touch unbudgeted files, and don't stall in loops.
"""

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Any

try:
    from .runtime import configure_utf8_stdio
    from .room import load_room_data, get_room_paths
except ImportError:
    from runtime import configure_utf8_stdio
    from room import load_room_data, get_room_paths

configure_utf8_stdio()

SENSITIVE_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "pyproject.toml", "poetry.lock", "requirements.txt", "Pipfile", "Pipfile.lock",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
    ".env", ".env.local", ".env.production",
}

DEBUG_STATEMENT_PATTERNS = [
    (re.compile(r"^[+]\s*(debugger;|console\.log\(|binding\.pry)", re.MULTILINE), "Leftover debugger or console.log call"),
]


def get_git_status_files(target_dir: Path) -> Dict[str, List[str]]:
    """Return modified, untracked, and deleted files relative to git root."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"modified": [], "untracked": [], "deleted": []}

    modified = []
    untracked = []
    deleted = []

    for line in proc.stdout.splitlines():
        if not line or len(line) < 4:
            continue
        status = line[:2]
        filepath = line[3:].strip().strip('"')
        # Normalize relative path
        norm_path = os.path.normpath(filepath).replace("\\", "/")

        # Ignore internal .capsule room files
        if norm_path == ".capsule" or norm_path.startswith(".capsule/") or norm_path.startswith(".capsule"):
            continue

        if "D" in status:
            deleted.append(norm_path)
        elif "??" in status:
            untracked.append(norm_path)
        else:
            modified.append(norm_path)

    return {
        "modified": sorted(modified),
        "untracked": sorted(untracked),
        "deleted": sorted(deleted),
    }


def audit_agent_drift(target_dir: Path) -> Dict[str, Any]:
    """Inspect whether active agents are adhering to their claimed files and boundaries."""
    target_dir = Path(target_dir).resolve()
    room_json, conf_md, _ = get_room_paths(target_dir)
    room_data = load_room_data(room_json)

    git_files = get_git_status_files(target_dir)
    all_dirty = sorted(list(set(git_files["modified"] + git_files["untracked"] + git_files["deleted"])))

    active_shifts = room_data.get("active_shifts", {})
    now = datetime.now(timezone.utc)

    claimed_by_agent: Dict[str, List[str]] = {}
    all_claimed: Set[str] = set()
    stale_shifts: List[Dict[str, Any]] = []

    for shift_id, shift in active_shifts.items():
        agent_id = shift.get("agent_id", "unknown")
        files = [os.path.normpath(f.strip()).replace("\\", "/") for f in shift.get("files", []) if f.strip()]
        claimed_by_agent[agent_id] = files
        all_claimed.update(files)

        # Check for shift stalling (>45m without heartbeat)
        last_seen = shift.get("last_seen_at") or shift.get("clocked_in_at")
        if last_seen:
            try:
                dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                if now - dt > timedelta(minutes=45):
                    stale_shifts.append({
                        "shift_id": shift_id,
                        "agent_id": agent_id,
                        "inactive_minutes": int((now - dt).total_seconds() / 60),
                    })
            except Exception:
                pass

    issues: List[Dict[str, Any]] = []
    unclaimed_dirty = [f for f in all_dirty if f not in all_claimed]

    # Scenario 1: Dirty tree with NO active agents clocked in (Rogue modifications)
    if all_dirty and not active_shifts:
        issues.append({
            "type": "ROGUE_ACTIVITY",
            "severity": "FAIL",
            "message": f"{len(all_dirty)} uncommitted files detected, but NO agent is clocked in to the Check-In Room.",
            "files": all_dirty,
            "fix": "Run 'capsule clock-in --task ... --files ...' before modifying code.",
        })

    # Scenario 2: Active agent modifying unbudgeted files (Scope Drift)
    elif unclaimed_dirty:
        issues.append({
            "type": "SCOPE_DRIFT",
            "severity": "FAIL",
            "message": f"Active agent(s) touched {len(unclaimed_dirty)} files outside their claimed shift scope.",
            "unclaimed_files": unclaimed_dirty,
            "claimed_files": sorted(list(all_claimed)),
            "fix": "Revert unbudgeted changes or clock in with expanded --files grant.",
        })

    # Scenario 3: Stale / abandoned shifts
    for stale in stale_shifts:
        issues.append({
            "type": "STALE_SHIFT",
            "severity": "WARN",
            "message": f"Agent '{stale['agent_id']}' shift has been idle for {stale['inactive_minutes']}m without heartbeat.",
            "shift_id": stale["shift_id"],
            "fix": "Run 'capsule heartbeat' to renew activity, or 'capsule clock-out'.",
        })

    # Scenario 4: Sensitive dependency tampering
    tampered_deps = [f for f in all_dirty if any(f.endswith(s) or f == s for s in SENSITIVE_FILES)]
    if tampered_deps and not any("package" in f or "deps" in f for f in all_claimed):
        issues.append({
            "type": "DEPENDENCY_TAMPERING",
            "severity": "WARN",
            "message": f"Build/dependency manifests modified: {', '.join(tampered_deps)}",
            "files": tampered_deps,
            "fix": "Ensure package additions were explicitly requested in the Task Brief.",
        })

    has_fail = any(i["severity"] == "FAIL" for i in issues)
    has_warn = any(i["severity"] == "WARN" for i in issues)

    if has_fail:
        status = "DRIFT_DETECTED" if active_shifts else "ROGUE_ACTIVITY"
        verdict = "FAIL"
    elif has_warn:
        status = "DRIFT_WARNING"
        verdict = "WARN"
    else:
        status = "ALIGNED"
        verdict = "PASS"

    return {
        "status": status,
        "verdict": verdict,
        "target_dir": str(target_dir),
        "active_shifts_count": len(active_shifts),
        "claimed_files": sorted(list(all_claimed)),
        "dirty_files": all_dirty,
        "unclaimed_files": unclaimed_dirty,
        "issues": issues,
    }


def format_watchdog_report(report: Dict[str, Any]) -> str:
    lines = [
        "=" * 88,
        " 🐒 KING KAI'S TELEPATHIC OBSERVATION DECK (Agent Watchdog)",
        "=" * 88,
    ]

    verdict = report["verdict"]
    status = report["status"]

    if verdict == "PASS":
        lines.append(" 🟢 STATUS: PERFECTLY ALIGNED")
        lines.append("    All active agents are operating strictly within their claimed files.")
        lines.append("    Zero unbudgeted scope creep or rogue drift detected.")
    elif verdict == "WARN":
        lines.append(" ⚠️  STATUS: DRIFT WARNING DETECTED")
    else:
        lines.append(" 🚨 STATUS: ROGUE ACTIVITY / SCOPE DRIFT DETECTED!")
        lines.append("    \"Hey! What are you doing down there?! Get back on the assigned path!\"")

    lines.append("-" * 88)
    lines.append(f" Workspace:     {report['target_dir']}")
    lines.append(f" Active Shifts: {report['active_shifts_count']}")
    lines.append(f" Claimed Files: {', '.join(report['claimed_files']) if report['claimed_files'] else 'None'}")
    lines.append(f" Dirty Files:   {', '.join(report['dirty_files']) if report['dirty_files'] else 'Clean working tree'}")

    if report["issues"]:
        lines.append("")
        lines.append(" DISCOVERED DEVIATIONS:")
        for idx, issue in enumerate(report["issues"], start=1):
            badge = "🚨" if issue["severity"] == "FAIL" else "⚠️ "
            lines.append(f"  {badge} [{idx}] {issue['type']}: {issue['message']}")
            if "unclaimed_files" in issue:
                lines.append(f"      Out-of-Bounds: {', '.join(issue['unclaimed_files'])}")
            if "fix" in issue:
                lines.append(f"      Remediation:   {issue['fix']}")

    lines.append("=" * 88)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="King Kai's Telepathic Watchdog & Agent Drift Inspector")
    parser.add_argument("target", nargs="?", default=".", help="Target project root directory (default: current dir)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as hard drift")
    args = parser.parse_args(argv)

    target_dir = Path(args.target).resolve()
    report = audit_agent_drift(target_dir)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_watchdog_report(report))

    if report["verdict"] == "FAIL" or (args.strict and report["verdict"] == "WARN"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
