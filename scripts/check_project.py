#!/usr/bin/env python3
"""
Capsule Corp Project Check Engine (`capsule check`)
Executes project-specific verification checks and reports factual, unix-style results:
  - Tests (passed / failed / skipped)
  - Linters (passed / failed / skipped)
  - Typecheckers (passed / failed / skipped)
  - Build manifests (passed / failed / skipped)
  - Secrets & Diff Audit (passed / failed / skipped)

Honors project-level config (capsule.json, .capsulerc.json, or pyproject.toml [tool.capsule])
with intelligent fallback to ecosystem detection.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from .runtime import configure_utf8_stdio
    from .verify_project import audit_git_diff, detect_test_command, load_project_config
except ImportError:
    from runtime import configure_utf8_stdio
    from verify_project import audit_git_diff, detect_test_command, load_project_config

configure_utf8_stdio()


def detect_lint_command(root_dir: Path) -> Optional[List[str]]:
    """Auto-detect project linter if available."""
    # Node.js
    pkg_file = root_dir / "package.json"
    if pkg_file.exists():
        try:
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "lint" in scripts:
                if (root_dir / "pnpm-lock.yaml").exists() and shutil.which("pnpm"):
                    return ["pnpm", "run", "lint"]
                if ((root_dir / "bun.lockb").exists() or (root_dir / "bun.lock").exists()) and shutil.which("bun"):
                    return ["bun", "run", "lint"]
                if (root_dir / "yarn.lock").exists() and shutil.which("yarn"):
                    return ["yarn", "run", "lint"]
                return ["npm", "run", "lint"]
        except Exception:
            pass

    # Python
    if (root_dir / "ruff.toml").exists() or (root_dir / ".ruff.toml").exists():
        if shutil.which("ruff"):
            return ["ruff", "check", "."]
    if (root_dir / ".flake8").exists() and shutil.which("flake8"):
        return ["flake8", "."]

    # Rust
    if (root_dir / "Cargo.toml").exists() and shutil.which("cargo"):
        return ["cargo", "clippy", "--", "-D", "warnings"]

    return None


def detect_typecheck_command(root_dir: Path) -> Optional[List[str]]:
    """Auto-detect project typechecker if available."""
    # TypeScript
    if (root_dir / "tsconfig.json").exists():
        pkg_file = root_dir / "package.json"
        if pkg_file.exists():
            try:
                pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
                scripts = pkg.get("scripts", {})
                if "typecheck" in scripts:
                    return ["npm", "run", "typecheck"]
            except Exception:
                pass
        if shutil.which("tsc"):
            return ["tsc", "--noEmit"]
        if shutil.which("npx"):
            return ["npx", "tsc", "--noEmit"]

    # Python MyPy
    if (root_dir / "mypy.ini").exists() or (root_dir / ".mypy.ini").exists():
        if shutil.which("mypy"):
            return ["mypy", "."]

    return None


def execute_check(cmd: List[str], cwd: Path, timeout: int = 120) -> Tuple[int, str, float]:
    """Execute a single check command and return exit code, output, and duration."""
    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout
        )
        duration = round(time.time() - start_time, 2)
        return proc.returncode, proc.stdout.strip(), duration
    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 2)
        return 124, f"Timed out after {timeout}s", duration
    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        return 1, str(exc), duration


def run_project_checks(
    root_dir: Path,
    test_cmd_override: Optional[str] = None,
    lint_cmd_override: Optional[str] = None,
    typecheck_cmd_override: Optional[str] = None,
    skip_secrets: bool = False,
    check_drift: bool = False,
    check_grill: bool = False,
) -> Dict[str, Any]:
    """Run all configured and detected checks for a project."""
    root_dir = root_dir.resolve()
    config = load_project_config(root_dir)

    results = []
    has_failure = False

    # Configuration Error Check
    if "_error" in config:
        has_failure = True
        results.append({
            "name": "Configuration",
            "status": "FAILED",
            "command": "load_project_config",
            "duration": 0.0,
            "summary": config["_error"],
            "output": config["_error"],
        })

    # 1. Tests
    test_cmd_str = test_cmd_override or config.get("test")
    test_cmd = shlex.split(test_cmd_str) if test_cmd_str else detect_test_command(root_dir)
    if test_cmd:
        code, output, duration = execute_check(test_cmd, root_dir)
        status = "PASSED" if code == 0 else "FAILED"
        if code != 0:
            has_failure = True
        summary = f"{' '.join(test_cmd)} ({duration}s)"
        results.append({
            "name": "Tests",
            "status": status,
            "command": " ".join(test_cmd),
            "duration": duration,
            "summary": summary,
            "output": output,
        })
    else:
        results.append({
            "name": "Tests",
            "status": "SKIPPED",
            "command": None,
            "summary": "No test suite configured or detected",
            "output": "",
        })

    # 2. Linters
    lint_cmd_str = lint_cmd_override or config.get("lint")
    lint_cmd = shlex.split(lint_cmd_str) if lint_cmd_str else detect_lint_command(root_dir)
    if lint_cmd:
        code, output, duration = execute_check(lint_cmd, root_dir)
        status = "PASSED" if code == 0 else "FAILED"
        if code != 0:
            has_failure = True
        results.append({
            "name": "Lint",
            "status": status,
            "command": " ".join(lint_cmd),
            "duration": duration,
            "summary": f"{' '.join(lint_cmd)} ({duration}s)",
            "output": output,
        })
    else:
        results.append({
            "name": "Lint",
            "status": "SKIPPED",
            "command": None,
            "summary": "No linter configured or detected",
            "output": "",
        })

    # 3. Typecheck
    typecheck_cmd_str = typecheck_cmd_override or config.get("typecheck")
    typecheck_cmd = shlex.split(typecheck_cmd_str) if typecheck_cmd_str else detect_typecheck_command(root_dir)
    if typecheck_cmd:
        code, output, duration = execute_check(typecheck_cmd, root_dir)
        status = "PASSED" if code == 0 else "FAILED"
        if code != 0:
            has_failure = True
        results.append({
            "name": "Typecheck",
            "status": status,
            "command": " ".join(typecheck_cmd),
            "duration": duration,
            "summary": f"{' '.join(typecheck_cmd)} ({duration}s)",
            "output": output,
        })
    else:
        results.append({
            "name": "Typecheck",
            "status": "SKIPPED",
            "command": None,
            "summary": "No typechecker configured or detected",
            "output": "",
        })

    # 4. Secrets & Diff Audit
    if not skip_secrets:
        try:
            issues = audit_git_diff(root_dir)
            if issues:
                has_failure = True
                summary = f"{len(issues)} suspicious pattern(s) or exposed secret(s) in diff"
                output = "\n".join(f"- {issue.get('file', '')}: {issue.get('description', '')}" for issue in issues)
                status = "FAILED"
            else:
                summary = "0 exposed credentials or merge markers in diff"
                output = ""
                status = "PASSED"
            results.append({
                "name": "Secrets & Diff",
                "status": status,
                "command": "git diff audit",
                "summary": summary,
                "output": output,
            })
        except Exception as exc:
            results.append({
                "name": "Secrets & Diff",
                "status": "SKIPPED",
                "command": "git diff audit",
                "summary": f"Skipped: {exc}",
                "output": "",
            })

    # 5. Agent Alignment & Drift Audit (King Kai's Watchdog)
    # Automatically activates when an active agent shift exists in the Check-In Room,
    # or when explicitly requested via check_drift=True (--check-drift).
    auto_drift = False
    try:
        try:
            from .room import get_room_paths, load_room_data
        except ImportError:
            from room import get_room_paths, load_room_data
        room_json, _, _ = get_room_paths(root_dir)
        if room_json.exists():
            rdata = load_room_data(room_json)
            if rdata.get("active_shifts"):
                auto_drift = True
    except Exception:
        pass

    if check_drift or auto_drift:
        try:
            try:
                from .spy_watchdog import audit_agent_drift
            except ImportError:
                from spy_watchdog import audit_agent_drift

            drift_report = audit_agent_drift(root_dir)
            issue_lines = []
            for i in drift_report.get("issues", []):
                msg = f"- {i['type']}: {i['message']}"
                files = i.get("unclaimed_files") or i.get("files")
                if files:
                    msg += f" (Off-path files: {', '.join(files)})"
                issue_lines.append(msg)
            output = "\n".join(issue_lines)

            if drift_report["verdict"] == "FAIL":
                has_failure = True
                status = "FAILED"
                summary = f"{len(drift_report['issues'])} agent drift / rogue issue(s) detected"
            elif drift_report["verdict"] == "WARN":
                status = "WARNING"
                summary = f"Drift warning: {len(drift_report['issues'])} minor issue(s)"
            else:
                status = "PASSED"
                summary = "Agent shifts aligned with claimed scope"
                output = ""

            results.append({
                "name": "Agent Alignment",
                "status": status,
                "command": "capsule spy",
                "summary": summary,
                "output": output,
            })
        except Exception as exc:
            results.append({
                "name": "Agent Alignment",
                "status": "SKIPPED",
                "command": "capsule spy",
                "summary": f"Skipped: {exc}",
                "output": "",
            })

    # 6. Lord Beerus' Architectural Inquisition (Code Griller)
    # Runs when explicitly requested via check_grill=True (--grill) or config "grill": true
    if check_grill or (config and config.get("grill")):
        try:
            try:
                from .grill_code import run_grill_audit
            except ImportError:
                from grill_code import run_grill_audit

            grill_report = run_grill_audit(root_dir)
            threat = grill_report["threat_level"]
            issues = grill_report.get("issues", [])
            output_lines = []
            for item in issues:
                output_lines.append(f"- [{item['severity']}] {item['category']} in {item['file']}:{item['line']}")
                output_lines.append(f"  Beerus: \"{item['beerus_question']}\"")
                if item.get("defended"):
                    output_lines.append(f"  Defense: \"{item.get('defense')}\"")
            output = "\n".join(output_lines)

            if grill_report["verdict"] == "FAIL":
                has_failure = True
                status = "FAILED"
                summary = f"Hakai Threat: {threat} ({grill_report['summary']['critical']} critical inquisition failure(s))"
            elif grill_report["verdict"] == "WARN":
                status = "WARNING"
                summary = f"Hakai Threat: {threat} ({len(issues)} inquisition item(s) flagged)"
            else:
                status = "PASSED"
                summary = "Hakai Threat: DIVINE APPROVAL (Zero critical flaws)"
                output = ""

            results.append({
                "name": "Beerus Inquisition",
                "status": status,
                "command": "capsule grill",
                "summary": summary,
                "output": output,
            })
        except Exception as exc:
            results.append({
                "name": "Beerus Inquisition",
                "status": "SKIPPED",
                "command": "capsule grill",
                "summary": f"Skipped: {exc}",
                "output": "",
            })

    executed_checks = [c for c in results if c["name"] in ("Tests", "Lint", "Typecheck") and c["status"] in ("PASSED", "FAILED")]
    if has_failure:
        verdict = "FAIL"
    elif not executed_checks:
        verdict = "INCOMPLETE"
    else:
        verdict = "PASS"

    return {
        "target": str(root_dir),
        "target_name": root_dir.name,
        "config_loaded": bool(config and "_error" not in config),
        "verdict": verdict,
        "checks": results,
    }


def format_check_report(report: Dict[str, Any], verbose: bool = False) -> str:
    """Render check results as a clean, unix-style status report."""
    lines = []
    lines.append("=" * 72)
    lines.append(f" CAPSULE CHECK: {report['target_name']}")
    lines.append("=" * 72)
    if report.get("config_loaded"):
        lines.append(" (Loaded explicit project configuration)")

    for check in report["checks"]:
        name = check["name"]
        status = check["status"]
        summary = check["summary"]
        if status == "PASSED":
            badge = " [PASS] "
        elif status == "FAILED":
            badge = " [FAIL] "
        else:
            badge = " [SKIP] "

        lines.append(f"{badge} {name:<16} {summary}")
        if (status == "FAILED" or verbose) and check.get("output"):
            out = check["output"]
            if len(out) > 800 and not verbose:
                out = out[:800] + "\n... (truncated, use --verbose to see full output)"
            for subline in out.splitlines():
                lines.append(f"        | {subline}")

    lines.append("-" * 72)
    if report["verdict"] == "PASS":
        lines.append(" VERDICT: PASS (All active project checks succeeded)")
    elif report["verdict"] == "INCOMPLETE":
        lines.append(" VERDICT: INCOMPLETE (Zero test suites or checks configured/detected)")
    else:
        lines.append(" VERDICT: FAIL (One or more active project checks failed)")
    lines.append("=" * 72)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Capsule Corp Project Verification Checker")
    parser.add_argument("target_dir", nargs="?", default=".", help="Directory to check (defaults to CWD)")
    parser.add_argument("--json", action="store_true", help="Output check results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full command outputs")
    parser.add_argument("--test-cmd", help="Explicit test command override")
    parser.add_argument("--lint-cmd", help="Explicit lint command override")
    parser.add_argument("--typecheck-cmd", help="Explicit typecheck command override")
    parser.add_argument("--skip-secrets", action="store_true", help="Skip git diff secret scanner")
    parser.add_argument("--check-drift", action="store_true", help="Run King Kai's agent drift watchdog audit")
    parser.add_argument("--grill", action="store_true", help="Run Lord Beerus' architectural inquisition & code griller")
    args = parser.parse_args()

    target = Path(args.target_dir).resolve()
    if not target.exists():
        print(f"Error: Target directory {target} does not exist.", file=sys.stderr)
        sys.exit(1)

    report = run_project_checks(
        target,
        test_cmd_override=args.test_cmd,
        lint_cmd_override=args.lint_cmd,
        typecheck_cmd_override=args.typecheck_cmd,
        skip_secrets=args.skip_secrets,
        check_drift=args.check_drift,
        check_grill=args.grill,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_check_report(report, verbose=args.verbose))

    sys.exit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
