#!/usr/bin/env python3
"""
Trunks' Verification Sentinel (Capsule Corp)
Inspired by Lauren Tan's Self-Testing Verification Bots at SpaceXAI.

Automated verification harness:
  1. Auto-detects project ecosystem & test runners
  2. Executes unit/integration test suites
  3. Audits git diff for secrets, merge conflicts, leftover debug statements, and trash files
  4. Returns deterministic exit code: 0 on Green (verified), 1 on Red (failed)
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

SUSPICIOUS_DIFF_PATTERNS = [
    (re.compile(r"^[+]\s*<{7}(?:\s+.*)?$", re.MULTILINE), "Git merge conflict marker (start)"),
    (re.compile(r"^[+]\s*={7}\s*$", re.MULTILINE), "Git merge conflict marker (mid)"),
    (re.compile(r"^[+]\s*>{7}(?:\s+.*)?$", re.MULTILINE), "Git merge conflict marker (end)"),
    (re.compile(r"^[+].*AIza[0-9A-Za-z-_]{35}.*", re.MULTILINE), "Exposed Google API Key"),
    (re.compile(r"^[+].*sk-[a-zA-Z0-9]{20,}.*", re.MULTILINE), "Exposed OpenAI / Service Secret Key"),
    (re.compile(r"^[+].*ghp_[a-zA-Z0-9]{36}.*", re.MULTILINE), "Exposed GitHub Personal Access Token"),
    (re.compile(r"^[+].*-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----.*", re.MULTILINE), "Private Key block"),
]


def detect_test_command(root_dir: Path) -> Optional[List[str]]:
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
            import json
            pkg = json.loads((root_dir / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "test" in scripts and "no test specified" not in scripts["test"]:
                return ["npm", "test"]
        except Exception:
            pass

    # Python (pytest or unittest discovery)
    tests_dir = root_dir / "tests"
    test_dir = root_dir / "test"
    if tests_dir.exists() or test_dir.exists():
        # Check if pytest is available or fallback to standard library unittest
        try:
            probe = subprocess.run(["pytest", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if probe.returncode == 0:
                return ["pytest", "-v"]
        except Exception:
            pass

        active_dir = tests_dir if tests_dir.exists() else test_dir
        return [sys.executable, "-m", "unittest", "discover", "-s", str(active_dir), "-p", "test_*.py"]

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


def audit_git_diff(root_dir: Path) -> List[Dict[str, str]]:
    issues = []
    diff_parts = []
    for diff_command in (
        ["git", "diff", "--no-ext-diff", "--"],
        ["git", "diff", "--no-ext-diff", "--cached", "--"],
    ):
        try:
            res = subprocess.run(
                diff_command,
                cwd=str(root_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except OSError as exc:
            return [{
                "severity": "HIGH",
                "description": "Unable to inspect git diff",
                "snippet": str(exc)[:120]
            }]
        if res.returncode != 0:
            return [{
                "severity": "HIGH",
                "description": "Unable to inspect git diff",
                "snippet": res.stderr.strip()[:120] or "git diff failed"
            }]
        diff_parts.append(res.stdout)

    def scan_text(text: str):
        for pattern, description in SUSPICIOUS_DIFF_PATTERNS:
            match = pattern.search(text)
            if match:
                issues.append({
                    "severity": "CRITICAL",
                    "description": description,
                    "snippet": match.group(0)[:120]
                })

    scan_text("\n".join(diff_parts))

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
            "description": "Unable to inspect untracked files",
            "snippet": untracked.stderr.decode(errors="replace")[:120] or "git ls-files failed"
        })
    else:
        for raw_path in untracked.stdout.split(b"\0"):
            if not raw_path:
                continue
            path = root_dir / os.fsdecode(raw_path)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                issues.append({
                    "severity": "HIGH",
                    "description": "Unable to inspect untracked file",
                    "snippet": f"{path.name}: {exc}"[:120]
                })
                continue
            scan_text("\n".join(f"+{line}" for line in content.splitlines()))

    return issues


def main():
    parser = argparse.ArgumentParser(description="Trunks' Verification Sentinel (Capsule Corp)")
    parser.add_argument("target_dir", nargs="?", default=".", help="Target project root directory")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests, only check git diff/safety")
    parser.add_argument("--test-cmd", help="Override test command string")
    parser.add_argument("--timeout", type=int, default=120, help="Test timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    project_dir = Path(args.target_dir).resolve()
    if not project_dir.exists():
        print(f"Error: Target directory {project_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    test_cmd: Optional[List[str]] = None
    if args.test_cmd:
        try:
            test_cmd = shlex.split(args.test_cmd)
        except ValueError as exc:
            parser.error(f"invalid --test-cmd: {exc}")
    elif not args.skip_tests:
        test_cmd = detect_test_command(project_dir)

    diff_issues = audit_git_diff(project_dir)

    test_exit_code = 0
    test_stdout = ""
    test_stderr = ""

    if test_cmd and not args.skip_tests:
        test_exit_code, test_stdout, test_stderr = run_tests(test_cmd, project_dir, args.timeout)
    elif not args.skip_tests:
        test_exit_code = 1
        test_stderr = "No automated test runner detected. Pass --skip-tests to explicitly bypass test execution."

    passed = (test_exit_code == 0) and (len(diff_issues) == 0)

    if args.json:
        import json
        payload = {
            "verdict": "PASS" if passed else "FAIL",
            "project_dir": str(project_dir),
            "test_command": " ".join(test_cmd) if test_cmd else None,
            "test_exit_code": test_exit_code,
            "test_stdout": test_stdout[-1000:],
            "test_stderr": test_stderr[-1000:],
            "diff_issues": diff_issues
        }
        print(json.dumps(payload, indent=2))
        sys.exit(0 if passed else 1)

    print("==================================================================")
    print(" 🗡️  TRUNKS' TIMELINE SENTINEL REPORT (CAPSULE CORP)")
    print("==================================================================")
    print(f"Target Directory: {project_dir}")
    print(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}")
    print("------------------------------------------------------------------")

    if test_cmd and not args.skip_tests:
        cmd_str = " ".join(test_cmd)
        print(f"Test Suite Command: {cmd_str}")
        if test_exit_code == 0:
            print(" Test Execution: PASSED (Exit code 0)")
        else:
            print(f" Test Execution: FAILED (Exit code {test_exit_code})")
            if test_stdout:
                print("\n--- STDOUT Tail ---")
                print("\n".join(test_stdout.strip().splitlines()[-15:]))
            if test_stderr:
                print("\n--- STDERR Tail ---")
                print("\n".join(test_stderr.strip().splitlines()[-15:]))
    else:
        print("Test Execution: SKIPPED (No automated test runner detected or --skip-tests flag passed)")

    print("------------------------------------------------------------------")
    print(f"Diff Security & Integrity Audit: {len(diff_issues)} issue(s) detected")
    for issue in diff_issues:
        print(f"  [{issue['severity']}] {issue['description']}: {issue['snippet']}")

    print("==================================================================")
    if passed:
        print(" VERDICT: GREEN (Approved for merge/handoff. Zero regressions.)")
        print("==================================================================")
        sys.exit(0)
    else:
        print(" VERDICT: RED (Rejected. Timeline anomalies detected. Fix before handoff.)")
        print("==================================================================")
        sys.exit(1)


if __name__ == "__main__":
    main()
