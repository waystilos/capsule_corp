#!/usr/bin/env python3
"""
Trunks' Verification Sentinel (Capsule Corp)
Implements Capsule Corp's deterministic verification gate.

Automated verification harness:
  1. Auto-detects project ecosystem & test runners
  2. Executes unit/integration test suites
  3. Audits git diff for secrets, merge conflicts, leftover debug statements, and trash files
  4. Returns deterministic exit code: 0 on Green (verified), 1 on Red (failed)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

try:
    from .runtime import configure_utf8_stdio
    from ._config import load_toml, split_command
    from . import secret_patterns as sp
except ImportError:
    from runtime import configure_utf8_stdio
    from _config import load_toml, split_command
    import secret_patterns as sp

configure_utf8_stdio()

MAX_UNTRACKED_READ_BYTES = 1024 * 1024
FILE_SCAN_BUDGET_SECONDS = 20.0
_HIDDEN_FLAGS = ("h", "s", "S")  # git ls-files -v: assume-unchanged / skip-worktree

MERGE_START_RE = re.compile(r"^\+<{7}(?:\s.*)?$", re.MULTILINE)
MERGE_MID_RE = re.compile(r"^\+={7}\r?$", re.MULTILINE)
MERGE_END_RE = re.compile(r"^\+>{7}(?:\s.*)?$", re.MULTILINE)

# Merge markers plus the SHARED secret patterns (scripts/secret_patterns.py), so the
# diff gate covers exactly what `capsule security` covers (AWS, Stripe, Google, sk-proj...).
SUSPICIOUS_DIFF_PATTERNS = [
    (MERGE_START_RE, "Git merge conflict marker (start)"),
    (MERGE_MID_RE, "Git merge conflict marker (mid)"),
    (MERGE_END_RE, "Git merge conflict marker (end)"),
] + list(sp.DIFF_SECRET_PATTERNS)

PROJECT_CODE_NOTICE = (
    "SECURITY NOTICE: `capsule check` and `capsule verify` EXECUTE code and commands defined by the "
    "target project (test/lint/typecheck commands from capsule.json, .capsulerc.json, pyproject "
    "[tool.capsule], package.json scripts, conftest.py, build hooks). Run them only on repositories "
    "you trust, or inside a container/sandbox. The project's own virtualenv interpreter is NOT used "
    "unless you opt in with CAPSULE_USE_PROJECT_VENV=1. Capsule warns when the gate configuration "
    "in the working tree differs from git HEAD."
)

TRUST_HELP = (
    "Project-defined commands: --trust (or CAPSULE_TRUST=1) runs them silently; --strict (or "
    "CAPSULE_TRUST=0) refuses them (reported SKIPPED); with neither, they still run this release "
    "but a WARN names them, and the default becomes --strict next release."
)

TRUST_ENV = "CAPSULE_TRUST"


def resolve_trust_mode(trust_flag: bool = False, strict_flag: bool = False) -> str:
    """Return 'trust', 'strict' or 'default'. CLI flags beat the CAPSULE_TRUST env (1=trust, 0=strict)."""
    if trust_flag and strict_flag:
        raise ValueError("--trust and --strict are mutually exclusive")
    if trust_flag:
        return "trust"
    if strict_flag:
        return "strict"
    env = os.environ.get(TRUST_ENV, "").strip()
    if env == "1":
        return "trust"
    if env == "0":
        return "strict"
    return "default"


# Config files that decide which commands the gates execute.
CONFIG_FILES = ("capsule.json", ".capsulerc.json", ".capsule.json", "package.json")


def config_drift_warnings(root_dir: Path) -> List[str]:
    """Warn (never fail) when gate-command config in the working tree differs from HEAD
    (modified, staged, or newly added/untracked). Empty outside a git repo."""
    names = [n for n in CONFIG_FILES if (root_dir / n).exists()]
    pyproject = root_dir / "pyproject.toml"
    try:
        if pyproject.exists() and "[tool.capsule" in pyproject.read_text(encoding="utf-8", errors="ignore"):
            names.append("pyproject.toml")
    except OSError as exc:
        print(f"WARN: could not read {pyproject} for gate-config drift check: {exc}", file=sys.stderr)
    if not names:
        return []
    warnings = []
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--"] + names,
            cwd=str(root_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if res.returncode != 0:
        return []
    for line in res.stdout.decode("utf-8", errors="replace").splitlines():
        if line.strip():
            warnings.append(line[3:].strip() + " differs from git HEAD (" + line[:2].strip() + ")")
    # `git status` never lists ignored files: an ignored config silently defines gate commands.
    try:
        ign = subprocess.run(
            ["git", "check-ignore", "--"] + names,
            cwd=str(root_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        if ign.returncode == 0:
            for name in ign.stdout.decode("utf-8", errors="replace").splitlines():
                if name.strip():
                    warnings.append(name.strip() + " is gitignored yet defines gate commands (not tracked by git)")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return warnings


def load_project_config(root_dir: Path) -> Dict[str, Any]:
    """Load explicit check/verification commands from capsule.json, .capsulerc.json, or pyproject.toml."""
    # 1. capsule.json or .capsulerc.json
    for candidate in ("capsule.json", ".capsulerc.json", ".capsule.json"):
        cfg_file = root_dir / candidate
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
                return {"_error": f"Config {candidate} must be a JSON object, got {type(data).__name__}"}
            except Exception as exc:
                return {"_error": f"Malformed {candidate}: {exc}"}

    # 2. pyproject.toml [tool.capsule]
    pyproject = root_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            data = load_toml(pyproject).get("tool", {}).get("capsule", {})
            if isinstance(data, dict) and data:
                return data
        except Exception as exc:
            return {"_error": f"Malformed pyproject.toml [tool.capsule]: {exc}"}

    return {}


def _tool(name: str) -> str:
    """Resolve an executable via PATH (finds .cmd shims on Windows), else the bare name."""
    return shutil.which(name) or name


def project_python(root_dir: Path) -> str:
    """Interpreter for tests. Defaults to the running interpreter: a target repo's own
    .venv/bin/python is attacker-controlled code, so it is used only when the operator
    opts in with CAPSULE_USE_PROJECT_VENV=1."""
    if os.environ.get("CAPSULE_USE_PROJECT_VENV") != "1":
        return sys.executable
    for rel in (".venv/bin/python", ".venv/Scripts/python.exe", "venv/bin/python", "venv/Scripts/python.exe"):
        candidate = root_dir / rel
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _has_pytest(python: str, cwd: Path) -> bool:
    try:
        probe = subprocess.run(
            [python, "-m", "pytest", "--version"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return probe.returncode == 0
    except Exception:
        return False


def detect_test_command(root_dir: Path) -> Optional[List[str]]:
    """Detect the test command. Raises ValueError for an unparsable configured command."""
    # Project config override (capsule.json, pyproject.toml)
    cfg = load_project_config(root_dir)
    for key in ("test", "test_cmd"):
        if cfg.get(key):
            try:
                return split_command(cfg[key])
            except ValueError as exc:
                raise ValueError(f"Invalid '{key}' command in project config: {exc}")

    # Capsule Corp Project
    if (root_dir / "bin" / "capsule").exists():
        return [sys.executable, str(root_dir / "bin" / "capsule"), "test"]

    # Rust
    if (root_dir / "Cargo.toml").exists():
        return ["cargo", "test"]

    # Go
    if (root_dir / "go.mod").exists():
        return ["go", "test", "./..."]

    # Node / TypeScript
    if (root_dir / "package.json").exists():
        try:
            pkg = json.loads((root_dir / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "test" in scripts and "no test specified" not in scripts["test"]:
                if (root_dir / "pnpm-lock.yaml").exists() and shutil.which("pnpm"):
                    return [_tool("pnpm"), "test"]
                if ((root_dir / "bun.lockb").exists() or (root_dir / "bun.lock").exists()) and shutil.which("bun"):
                    return [_tool("bun"), "test"]
                if (root_dir / "yarn.lock").exists() and shutil.which("yarn"):
                    return [_tool("yarn"), "test"]
                return [_tool("npm"), "test"]
        except Exception:
            pass

    # Python (pytest or unittest discovery)
    tests_dir = root_dir / "tests"
    test_dir = root_dir / "test"
    if tests_dir.exists() or test_dir.exists() or (root_dir / "pytest.ini").exists():
        py = project_python(root_dir)
        if _has_pytest(py, root_dir):
            return [py, "-m", "pytest", "-v"]

        active_dir = tests_dir if tests_dir.exists() else test_dir
        if active_dir.exists():
            return [py, "-m", "unittest", "discover", "-s", str(active_dir), "-p", "test_*.py"]

    # Dart / Flutter
    if (root_dir / "pubspec.yaml").exists():
        return ["flutter", "test"]

    return None


def run_tests(cmd: List[str], cwd: Path, timeout: int = 180) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout} seconds."
    except Exception as e:
        return 1, "", str(e)


class NotAGitRepository(Exception):
    """Raised when the audit target is not inside a git work tree."""


_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*)$", re.MULTILINE)
_MERGE_PATTERNS = (MERGE_START_RE, MERGE_MID_RE, MERGE_END_RE)


def _secret_label(desc: str) -> str:
    return "Private Key block" if desc == "Private Key Block" else "Exposed " + desc


def _incomplete_issue(rel: str, why: str) -> Dict[str, str]:
    return {"severity": "INCOMPLETE", "file": rel, "description": why, "snippet": ""}


def _added_lines(diff_chunk: str) -> List[str]:
    """Added-line payloads of ONE file's diff chunk. Split on "\\n" only (str.splitlines also
    splits on \\x0b/\\x0c/\\x1c/\\x85 and would hide secrets), and skip the file header by
    position (everything before the first '@@' hunk) rather than by '+++' line prefix, so an
    added line whose content starts with '++' is still scanned."""
    lines = diff_chunk.split("\n")
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            start = i + 1
            break
    else:
        return []  # no hunks: mode change, rename, or binary marker; content scan covers it
    return [ln[1:] for ln in lines[start:] if ln.startswith("+")]


def _scan_text(text: str, filename: str, issues: List[Dict[str, str]]) -> None:
    """Scan diff text: merge markers, plus secrets on added ('+') lines only."""
    has_start = bool(MERGE_START_RE.search(text))
    for pattern, description in SUSPICIOUS_DIFF_PATTERNS[:3]:
        # Mid/end markers only count when paired with a start marker in the same file.
        if pattern in _MERGE_PATTERNS and not has_start:
            continue
        match = pattern.search(text)
        if match:
            issues.append({
                "severity": "CRITICAL",
                "file": filename,
                "description": description,
                "snippet": match.group(0)[:120]
            })
    added = "\n".join(_added_lines(text))
    reported = set()
    for start, end, desc in sp.find_secrets(added):
        if desc in reported:
            continue
        reported.add(desc)
        issues.append({
            "severity": "CRITICAL",
            "file": filename,
            "description": _secret_label(desc),
            "snippet": sp.snippet_for(added, start, end)[:120],
        })


def scan_file_content(path: Path, rel: str, root_real: str, issues: List[Dict[str, str]],
                      time_budget: float = FILE_SCAN_BUDGET_SECONDS) -> None:
    """Scan an untracked file as pure additions. Big files are read in overlapping
    chunks; anything not fully scanned yields an INCOMPLETE issue (fail closed)."""
    if path.is_symlink():
        target = os.path.realpath(str(path))
        if os.path.lexists(target) and not (target == root_real or target.startswith(root_real + os.sep)):
            issues.append(_incomplete_issue(rel, "Symlink to a location outside the repository was not scanned"))
        return  # in-repo targets are scanned directly; dangling links hold no content
    if not path.is_file():
        return
    info: Dict[str, Any] = {}
    markers = {"start": None, "mid": None, "end": None}
    reported = set()
    deadline = time.monotonic() + time_budget
    try:
        for _first, text in sp.iter_text_chunks(path, info, chunk_bytes=MAX_UNTRACKED_READ_BYTES):
            if time.monotonic() > deadline:
                info["truncated"] = True
                break
            plus = "\n".join("+" + line for line in text.split("\n"))
            for key, rx in (("start", MERGE_START_RE), ("mid", MERGE_MID_RE), ("end", MERGE_END_RE)):
                if markers[key] is None:
                    m = rx.search(plus)
                    if m:
                        markers[key] = m.group(0)[:120]
            for start, end, desc in sp.find_secrets(text):
                if desc in reported:
                    continue
                reported.add(desc)
                issues.append({
                    "severity": "CRITICAL",
                    "file": rel,
                    "description": _secret_label(desc),
                    "snippet": sp.snippet_for(text, start, end)[:120],
                })
    except OSError:
        issues.append(_incomplete_issue(rel, "Unreadable file was not scanned"))
        return
    if markers["start"] is not None:
        for key, desc in (("start", "Git merge conflict marker (start)"),
                          ("mid", "Git merge conflict marker (mid)"),
                          ("end", "Git merge conflict marker (end)")):
            if markers[key] is not None:
                issues.append({"severity": "CRITICAL", "file": rel, "description": desc, "snippet": markers[key]})
    if info.get("truncated"):
        issues.append(_incomplete_issue(rel, "File exceeds the scan cap or time budget; remainder not scanned"))


def _scan_diff(diff: str, issues: List[Dict[str, str]]) -> None:
    headers = list(_DIFF_HEADER_RE.finditer(diff))
    if not headers:
        if diff.strip():
            _scan_text(diff, "(diff)", issues)
        return
    for i, m in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(diff)
        _scan_text(diff[m.start():end], m.group(2), issues)


def audit_git_diff(root_dir: Path) -> List[Dict[str, str]]:
    """Audit the git diff. Raises NotAGitRepository if root_dir is not a git work tree."""
    issues: List[Dict[str, str]] = []
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return [{
            "severity": "HIGH",
            "file": "",
            "description": "Unable to inspect git diff",
            "snippet": str(exc)[:120]
        }]
    if inside.returncode != 0 or inside.stdout.strip() != b"true":
        raise NotAGitRepository(str(root_dir))

    for diff_command in (
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--text", "--"],
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--text", "--cached", "--"],
    ):
        try:
            res = subprocess.run(
                diff_command,
                cwd=str(root_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
        except OSError as exc:
            return [{
                "severity": "HIGH",
                "file": "",
                "description": "Unable to inspect git diff",
                "snippet": str(exc)[:120]
            }]
        if res.returncode != 0:
            return [{
                "severity": "HIGH",
                "file": "",
                "description": "Unable to inspect git diff",
                "snippet": res.stderr.strip()[:120] or "git diff failed"
            }]
        _scan_diff(res.stdout, issues)

    # Git diffs do not include untracked files. Scan those files as additions
    # so a new secret cannot bypass the verification gate.
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=str(root_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if untracked.returncode != 0:
        issues.append({
            "severity": "HIGH",
            "file": "",
            "description": "Unable to inspect untracked files",
            "snippet": untracked.stderr.decode(errors="replace")[:120] or "git ls-files failed"
        })
    else:
        root_real = os.path.realpath(str(root_dir))
        for raw_path in untracked.stdout.split(b"\0"):
            if not raw_path:
                continue
            rel = os.fsdecode(raw_path)
            scan_file_content(root_dir / rel, rel, root_real, issues)

    # Files hidden by non-.gitignore exclude sources (info/exclude, core.excludesFile, global)
    # are invisible to the scan above; scan them too. .gitignore-ignored files stay skipped.
    all_ign = subprocess.run(["git", "ls-files", "-o", "-i", "-z", "--exclude-standard"],
                             cwd=str(root_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gi_ign = subprocess.run(["git", "ls-files", "-o", "-i", "-z", "--exclude-per-directory=.gitignore"],
                            cwd=str(root_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if all_ign.returncode != 0 or gi_ign.returncode != 0:
        issues.append(_incomplete_issue("", "Unable to enumerate files hidden by info/exclude or core.excludesFile"))
    else:
        gi_set = {p for p in gi_ign.stdout.split(b"\0") if p}
        root_real2 = os.path.realpath(str(root_dir))
        for raw_path in all_ign.stdout.split(b"\0"):
            if raw_path and raw_path not in gi_set:
                rel = os.fsdecode(raw_path)
                scan_file_content(root_dir / rel, rel, root_real2, issues)

    # Never trust diff text alone: also scan the full content of every changed file
    # (covers binary-looking/NUL files, `-diff` attributes, odd hunks) ...
    changed = set()
    for extra in ([], ["--cached"]):
        res = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", "--relative"] + extra + ["--"],
            cwd=str(root_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if res.returncode != 0:
            issues.append(_incomplete_issue("", "Unable to list changed files for content scan"))
            continue
        changed.update(os.fsdecode(p) for p in res.stdout.split(b"\0") if p)
    # ... and flag files git has been told to ignore changes in (they never show in diffs).
    hidden = subprocess.run(
        ["git", "ls-files", "-v", "-z"], cwd=str(root_dir),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if hidden.returncode != 0:
        issues.append(_incomplete_issue("", "Unable to inspect assume-unchanged/skip-worktree flags"))
    else:
        for entry in hidden.stdout.split(b"\0"):
            if len(entry) > 2 and chr(entry[0]) in _HIDDEN_FLAGS:
                rel = os.fsdecode(entry[2:])
                issues.append(_incomplete_issue(
                    rel, "File is marked assume-unchanged/skip-worktree; git diff cannot see its changes"))
                changed.add(rel)
    root_real = os.path.realpath(str(root_dir))
    for rel in sorted(changed):
        scan_file_content(root_dir / rel, rel, root_real, issues)

    seen = set()
    unique = []
    for i in issues:  # diff scan and content scan can report the same finding
        key = (i.get("severity"), i.get("file"), i.get("description"))
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique


def main():
    parser = argparse.ArgumentParser(
        description="Trunks' Verification Sentinel (Capsule Corp)",
        epilog=PROJECT_CODE_NOTICE + "\n\n" + TRUST_HELP,
    )
    parser.add_argument("target_dir", nargs="?", default=".", help="Target project root directory")
    parser.add_argument("--trust", action="store_true", help="Explicitly trust project-defined commands (also CAPSULE_TRUST=1)")
    parser.add_argument("--strict", action="store_true", help="Refuse project-defined commands, report SKIPPED (also CAPSULE_TRUST=0)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests, only check git diff/safety")
    parser.add_argument("--test-cmd", help="Override test command string")
    parser.add_argument("--timeout", type=int, default=120, help="Test timeout in seconds")
    parser.add_argument("--grill", action="store_true", help="Include Lord Beerus' code inquisition audit")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    project_dir = Path(args.target_dir).resolve()
    if not project_dir.exists():
        print(f"Error: Target directory {project_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    try:
        from .check_project import run_project_checks
    except ImportError:
        from check_project import run_project_checks

    try:
        trust_mode = resolve_trust_mode(args.trust, args.strict)
    except ValueError as exc:
        parser.error(str(exc))

    check_report = run_project_checks(
        project_dir,
        trust_mode=trust_mode,
        test_cmd_override=args.test_cmd,
        skip_tests=args.skip_tests,
        check_grill=args.grill,
        timeout=args.timeout,
    )

    verdict = check_report["verdict"]
    passed = (verdict == "PASS")

    if args.json:
        payload = {
            "verdict": "PASS" if passed else ("INCOMPLETE" if verdict == "INCOMPLETE" else "FAIL"),
            "project_dir": str(project_dir),
            "checks": check_report["checks"],
        }
        print(json.dumps(payload, indent=2))
        sys.exit(0 if passed else 1)

    print("==================================================================")
    print(" 🗡️  TRUNKS' TIMELINE SENTINEL REPORT (CAPSULE CORP)")
    print("==================================================================")
    print(f"Target Directory: {project_dir}")
    print(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}")
    print("------------------------------------------------------------------")
    print("Verification Checks:")
    for check in check_report["checks"]:
        name = check["name"]
        status = check["status"]
        summary = check["summary"]
        badge = {"PASSED": "[PASS]", "SKIPPED": "[SKIP]", "WARNING": "[WARN]", "INCOMPLETE": "[INCP]"}.get(status, "[FAIL]")
        print(f"  {badge:<7} {name:<16} {summary}")
        if status in ("FAILED", "WARNING", "INCOMPLETE") and check.get("output"):
            for l in check["output"].strip().splitlines()[-10:]:
                print(f"         | {l}")

    print("==================================================================")
    if verdict == "PASS":
        print(" VERDICT: GREEN (Approved for merge/handoff. Zero regressions.)")
        print("==================================================================")
        sys.exit(0)
    elif verdict == "INCOMPLETE":
        print(" VERDICT: INCOMPLETE (Zero test suites or checks configured/detected. Cannot verify without test evidence.)")
        print("==================================================================")
        sys.exit(1)
    else:
        print(" VERDICT: RED (Rejected. Verification checks failed. Fix before handoff.)")
        print("==================================================================")
        sys.exit(1)


if __name__ == "__main__":
    main()
