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
    from .room import (
        RoomCorruptError, load_room_data, get_room_paths,
        normalize_claim, claim_covers, fs_is_case_insensitive, shift_inactive_seconds,
        sanitize_text, MAX_CLAIMS, MAX_CLAIM_LEN,
    )
    from .messaging import unacked_messages, UNACKED_WARN_SECONDS
except ImportError:
    from runtime import configure_utf8_stdio
    from room import (
        RoomCorruptError, load_room_data, get_room_paths,
        normalize_claim, claim_covers, fs_is_case_insensitive, shift_inactive_seconds,
        sanitize_text, MAX_CLAIMS, MAX_CLAIM_LEN,
    )
    from messaging import unacked_messages, UNACKED_WARN_SECONDS

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


def _git(target_dir: Path, args: List[str]) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return proc.stdout


def _is_manifest(path: str) -> bool:
    return path.rsplit("/", 1)[-1] in SENSITIVE_FILES


_GLOB_ONLY = re.compile(r"^[\s*?/\\.]*$")


def is_overbroad_claim(raw: str, norm: str) -> bool:
    """True for claims that cover the whole tree ('.', '*', '**', '/', './', root path)."""
    return norm == "." or norm == "/" or bool(_GLOB_ONLY.match(raw or "x")) or bool(_GLOB_ONLY.match(norm))


def _is_capsule_internal(path: str) -> bool:
    """True only for the .capsule/ state directory (not e.g. .capsulerc.json)."""
    return path == ".capsule" or path.startswith(".capsule/")


def get_git_status_files(target_dir: Path) -> Dict[str, List[str]]:
    """Return modified, untracked, and deleted files as paths relative to target_dir."""
    # "errors" non-empty means the view is incomplete (callers must fail closed, never treat as clean).
    empty: Dict[str, List[str]] = {"modified": [], "untracked": [], "deleted": [], "errors": [], "hidden": [], "excluded": []}
    top = _git(target_dir, ["rev-parse", "--show-toplevel"])
    out = _git(target_dir, ["status", "--porcelain", "-z", "-uall"])
    if top is None or out is None:
        empty["errors"].append("git is unavailable or this is not a usable git work tree (git status failed)")
        return empty
    git_root = os.path.realpath(top.strip())
    base = os.path.realpath(str(target_dir))

    modified: List[str] = []
    untracked: List[str] = []
    deleted: List[str] = []

    def to_target_rel(git_rel: str) -> Optional[str]:
        # Porcelain paths are relative to the git root, not to target_dir.
        rel = os.path.relpath(os.path.join(git_root, git_rel), base)
        if rel == ".." or rel.startswith(".." + os.sep):
            return None
        norm = os.path.normpath(rel).replace("\\", "/")
        return None if _is_capsule_internal(norm) else norm

    entries = out.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        status, filepath = entry[:2], entry[3:]
        orig = None
        if "R" in status or "C" in status:
            # -z rename/copy records are "XY new\0old\0"
            orig = entries[i] if i < len(entries) else None
            i += 1

        path = to_target_rel(filepath)
        if path is not None:
            if "D" in status:
                deleted.append(path)
            elif status == "??":
                untracked.append(path)
            else:
                modified.append(path)
        if orig and "R" in status:
            old = to_target_rel(orig)
            if old is not None:
                deleted.append(old)

    errors: List[str] = []
    hidden: List[str] = []
    excluded: List[str] = []

    # Files hidden from `git status` via assume-unchanged (lowercase tag) or skip-worktree (S/s).
    lsv = _git(target_dir, ["ls-files", "-v", "-z"])
    if lsv is None:
        errors.append("git ls-files -v failed; hidden (assume-unchanged / skip-worktree) files cannot be ruled out")
    else:
        for rec in lsv.split("\0"):
            if len(rec) > 2 and (rec[0].islower() or rec[0] in "Ss"):
                p = os.path.normpath(rec[2:]).replace("\\", "/")
                if not _is_capsule_internal(p):
                    hidden.append(f"{p} [{rec[0]}]")

    # Untracked files hidden by .git/info/exclude (invisible to `git status` and not reviewable in git).
    exc_path = _git(target_dir, ["rev-parse", "--git-path", "info/exclude"])
    if exc_path is None:
        errors.append("could not locate .git/info/exclude")
    else:
        exc_file = os.path.join(str(target_dir), exc_path.strip())
        try:
            has_rules = os.path.isfile(exc_file) and any(
                ln.strip() and not ln.lstrip().startswith("#")
                for ln in open(exc_file, encoding="utf-8", errors="replace"))
        except OSError:
            has_rules = True
        if has_rules:
            ign = _git(target_dir, ["ls-files", "-o", "-i", "-z", "--exclude-from=" + exc_file])
            if ign is None:
                errors.append("could not enumerate files hidden by .git/info/exclude")
            else:
                for p in ign.split("\0"):
                    p = os.path.normpath(p).replace("\\", "/") if p else ""
                    if p and not _is_capsule_internal(p):
                        excluded.append(p)
                        untracked.append(p)

    # Any other exclude source (core.excludesFile, global ignore) hides files the same way.
    # Files ignored only via .gitignore files stay as today (reviewable in git).
    all_ign = _git(target_dir, ["ls-files", "-o", "-i", "-z", "--exclude-standard"])
    gi_ign = _git(target_dir, ["ls-files", "-o", "-i", "-z", "--exclude-per-directory=.gitignore"])
    if all_ign is None or gi_ign is None:
        errors.append("could not enumerate files hidden by core.excludesFile / global excludes")
    else:
        gi_set = {os.path.normpath(p).replace("\\", "/") for p in gi_ign.split("\0") if p}
        for p in all_ign.split("\0"):
            p = os.path.normpath(p).replace("\\", "/") if p else ""
            if p and p not in gi_set and not _is_capsule_internal(p):
                excluded.append(p)
                untracked.append(p)

    return {
        "modified": sorted(set(modified)),
        "untracked": sorted(set(untracked)),
        "deleted": sorted(set(deleted)),
        "errors": errors,
        "hidden": sorted(set(hidden)),
        "excluded": sorted(set(excluded)),
    }


def audit_agent_drift(target_dir: Path) -> Dict[str, Any]:
    """Inspect whether active agents are adhering to their claimed files and boundaries."""
    target_dir = Path(target_dir).resolve()
    room_json, _, _ = get_room_paths(target_dir)
    room_data = load_room_data(room_json)

    git_files = get_git_status_files(target_dir)
    all_dirty = sorted(list(set(git_files["modified"] + git_files["untracked"] + git_files["deleted"])))

    active_shifts = room_data.get("active_shifts", {})
    now = datetime.now(timezone.utc)

    claimed_by_agent: Dict[str, List[str]] = {}
    all_claimed: Set[str] = set()
    stale_shifts: List[Dict[str, Any]] = []
    overbroad: List[str] = []

    for shift_id, shift in active_shifts.items():
        agent_id = sanitize_text(shift.get("agent_id", "unknown"), 80)
        raw_files = shift.get("files", []) if isinstance(shift.get("files"), list) else []
        files = [normalize_claim(sanitize_text(f, MAX_CLAIM_LEN), target_dir)
                 for f in raw_files[:MAX_CLAIMS] if sanitize_text(f, MAX_CLAIM_LEN)]
        claimed_by_agent[agent_id] = files
        for f in raw_files[:MAX_CLAIMS]:
            raw = sanitize_text(f, MAX_CLAIM_LEN)
            if raw and is_overbroad_claim(raw, normalize_claim(raw, target_dir)):
                overbroad.append(f"{agent_id}: {raw!r}")
        all_claimed.update(files)

        # Check for shift stalling (>45m without heartbeat; far-future timestamps count as stale)
        try:
            idle = shift_inactive_seconds(shift, now)
            if idle is not None and idle > 45 * 60:
                stale_shifts.append({
                    "shift_id": sanitize_text(shift_id, 64),
                    "agent_id": agent_id,
                    "inactive_minutes": None if idle == float("inf") else int(idle / 60),
                })
        except (ValueError, TypeError, AttributeError) as exc:
            print(f"Warning: shift {sanitize_text(shift_id, 64)} has an unreadable timestamp ({exc}).", file=sys.stderr)

    issues: List[Dict[str, Any]] = []
    fold = (lambda x: x.casefold()) if fs_is_case_insensitive(target_dir) else (lambda x: x)
    folded_claims = [fold(c) for c in all_claimed]
    unclaimed_dirty = [f for f in all_dirty if not any(claim_covers(c, fold(f)) for c in folded_claims)]

    # Scenario 0: git view incomplete -> fail closed (never report ALIGNED on an unverified tree)
    incomplete: List[str] = list(git_files.get("errors", []))
    for h in git_files.get("hidden", []):
        incomplete.append(f"file hidden from git status: {h}")
    if incomplete:
        issues.append({
            "type": "INCOMPLETE",
            "severity": "FAIL",
            "message": "Cannot verify the working tree: " + "; ".join(incomplete),
            "files": list(git_files.get("hidden", [])),
            "fix": "Run inside a healthy git work tree (unset GIT_DIR), and clear assume-unchanged/skip-worktree flags "
                   "('git update-index --no-assume-unchanged --no-skip-worktree <file>').",
        })
    if git_files.get("excluded"):
        issues.append({
            "type": "HIDDEN_BY_EXCLUDE",
            "severity": "WARN",
            "message": f"{len(git_files['excluded'])} file(s) are hidden by .git/info/exclude; they are audited as dirty.",
            "files": git_files["excluded"],
            "fix": "Review .git/info/exclude; rogue files can be concealed there.",
        })
    for ob in overbroad:
        issues.append({
            "type": "OVERBROAD_CLAIM",
            "severity": "FAIL",
            "message": f"Claim covers the entire tree ({ob}); scope drift cannot be detected.",
            "fix": "Clock in with explicit files or directories instead of '.', '*' or '/'.",
        })

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
            "message": (f"Agent '{stale['agent_id']}' shift has been idle for {stale['inactive_minutes']}m without heartbeat."
                        if stale["inactive_minutes"] is not None
                        else f"Agent '{stale['agent_id']}' shift has a forged future timestamp and is treated as stale."),
            "shift_id": stale["shift_id"],
            "fix": "Run 'capsule heartbeat' to renew activity, or 'capsule clock-out'.",
        })

    # Scenario 3b: Messages left unacknowledged for too long
    for m in unacked_messages(target_dir, UNACKED_WARN_SECONDS):
        age = "unknown age" if m["age_s"] is None else f"{m['age_s'] // 60}m"
        issues.append({
            "type": "UNACKED_MESSAGE",
            "severity": "WARN",
            "message": f"Message {m['id']} from '{m['from']}' to '{m['to']}' unacknowledged for {age} (untrusted body: {m['body']!r}).",
            "fix": f"Recipient should run 'capsule inbox --agent {m['to']} --unread' and 'capsule ack {m['id']}'.",
        })

    # Scenario 4: Sensitive dependency tampering
    tampered_deps = [f for f in all_dirty if _is_manifest(f)]
    # Only an explicit claim of the exact manifest path counts as authorization (not '.', dirs, or lookalike names).
    if tampered_deps and not all(f in all_claimed for f in tampered_deps):
        issues.append({
            "type": "DEPENDENCY_TAMPERING",
            "severity": "WARN",
            "message": f"Build/dependency manifests modified: {', '.join(tampered_deps)}",
            "files": tampered_deps,
            "fix": "Ensure package additions were explicitly requested in the Task Brief.",
        })

    has_fail = any(i["severity"] == "FAIL" for i in issues)
    has_warn = any(i["severity"] == "WARN" for i in issues)

    if incomplete:
        status = "INCOMPLETE"
        verdict = "FAIL"
    elif has_fail:
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

    if report.get("status") == "INCOMPLETE":
        lines.append(" ❓ STATUS: INCOMPLETE - the working tree could not be fully verified")
    elif verdict == "PASS":
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
    if not target_dir.is_dir():
        print(f"Error: target directory does not exist: {target_dir}", file=sys.stderr)
        return 2
    try:
        report = audit_agent_drift(target_dir)
    except RoomCorruptError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_watchdog_report(report))

    if report["status"] == "INCOMPLETE":
        print("Error: spy is INCOMPLETE (cannot verify working tree); see report.", file=sys.stderr)
        return 2
    if report["verdict"] == "FAIL" or (args.strict and report["verdict"] == "WARN"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
