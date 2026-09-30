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
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

try:
    from .runtime import configure_utf8_stdio
except ImportError:
    from runtime import configure_utf8_stdio

configure_utf8_stdio()

SUSPICIOUS_DIFF_PATTERNS = [
    (re.compile(r"^[+]\s*<{7}(?:\s+.*)?$", re.MULTILINE), "Git merge conflict marker (start)"),
    (re.compile(r"^[+]\s*={7}\s*$", re.MULTILINE), "Git merge conflict marker (mid)"),
    (re.compile(r"^[+]\s*>{7}(?:\s+.*)?$", re.MULTILINE), "Git merge conflict marker (end)"),
    (re.compile(r"^[+].*AIza[0-9A-Za-z-_]{35}.*", re.MULTILINE), "Exposed Google API Key"),
    (re.compile(r"^[+].*sk-[a-zA-Z0-9]{20,}.*", re.MULTILINE), "Exposed OpenAI / Service Secret Key"),
    (re.compile(r"^[+].*sk-ant-api\d{2}-[a-zA-Z0-9_\-]{80,}.*", re.MULTILINE), "Exposed Anthropic API Key"),
    (re.compile(r"^[+].*ghp_[a-zA-Z0-9]{36}.*", re.MULTILINE), "Exposed GitHub Personal Access Token"),
    (re.compile(r"^[+].*github_pat_[a-zA-Z0-9_]{82}.*", re.MULTILINE), "Exposed GitHub Fine-Grained Personal Access Token"),
    (re.compile(r"^[+].*xox[baprs]-[0-9a-zA-Z]{10,48}.*", re.MULTILINE), "Exposed Slack Token"),
    (re.compile(r"^[+].*hf_[a-zA-Z0-9]{34,}.*", re.MULTILINE), "Exposed HuggingFace Access Token"),
    (re.compile(r"^[+].*-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----.*", re.MULTILINE), "Private Key block"),
]


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
            content = pyproject.read_text(encoding="utf-8")
            in_section = False
            data = {}
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    in_section = (line == "[tool.capsule]")
                    continue
                if in_section and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    data[k] = v
            if data:
                return data
        except Exception as exc:
            return {"_error": f"Malformed pyproject.toml [tool.capsule]: {exc}"}

    return {}


def detect_test_command(root_dir: Path) -> Optional[List[str]]:
    # Project config override (capsule.json, pyproject.toml)
    cfg = load_project_config(root_dir)
    if "test" in cfg and cfg["test"]:
        return shlex.split(cfg["test"])
    if "test_cmd" in cfg and cfg["test_cmd"]:
        return shlex.split(cfg["test_cmd"])

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
                if (root_dir / "pnpm-lock.yaml").exists() and shutil.which("pnpm"):
                    return ["pnpm", "test"]
                if ((root_dir / "bun.lockb").exists() or (root_dir / "bun.lock").exists()) and shutil.which("bun"):
                    return ["bun", "test"]
                if (root_dir / "yarn.lock").exists() and shutil.which("yarn"):
                    return ["yarn", "test"]
                return ["npm", "test"]
        except Exception:
            pass

    # Python (pytest or unittest discovery)
    tests_dir = root_dir / "tests"
    test_dir = root_dir / "test"
    if tests_dir.exists() or test_dir.exists() or (root_dir / "pytest.ini").exists():
        try:
            probe = subprocess.run(["pytest", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if probe.returncode == 0:
                return ["pytest", "-v"]
        except Exception:
            pass

        active_dir = tests_dir if tests_dir.exists() else test_dir
        if active_dir.exists():
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
            if path.is_dir():
                continue
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

    try:
        from .check_project import run_project_checks
    except ImportError:
        from check_project import run_project_checks

    check_report = run_project_checks(
        project_dir,
        test_cmd_override=args.test_cmd,
        skip_secrets=args.skip_tests,
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
        badge = "[PASS]" if status == "PASSED" else ("[SKIP]" if status == "SKIPPED" else "[FAIL]")
        print(f"  {badge:<7} {name:<16} {summary}")
        if status == "FAILED" and check.get("output"):
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
