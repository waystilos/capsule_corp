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
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from .runtime import configure_utf8_stdio
    from ._config import load_toml, split_command
    from .verify_project import (
        NotAGitRepository, PROJECT_CODE_NOTICE, TRUST_HELP, _tool, resolve_trust_mode, audit_git_diff, config_drift_warnings,
        detect_test_command, load_project_config,
    )
except ImportError:
    from runtime import configure_utf8_stdio
    from _config import load_toml, split_command
    from verify_project import (
        NotAGitRepository, PROJECT_CODE_NOTICE, TRUST_HELP, _tool, resolve_trust_mode, audit_git_diff, config_drift_warnings,
        detect_test_command, load_project_config,
    )

configure_utf8_stdio()


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _pyproject_tools(root_dir: Path) -> Dict[str, Any]:
    pp = root_dir / "pyproject.toml"
    if not pp.exists():
        return {}
    try:
        tool = load_toml(pp).get("tool", {})
        return tool if isinstance(tool, dict) else {}
    except Exception:
        return {}


def _has_ini_section(path: Path, section: str) -> bool:
    return ("[%s]" % section) in _read_file(path)


def _pm_run(root_dir: Path, script: str) -> List[str]:
    """Package-manager invocation of a package.json script, honoring lockfiles."""
    if (root_dir / "pnpm-lock.yaml").exists() and shutil.which("pnpm"):
        return [_tool("pnpm"), "run", script]
    if ((root_dir / "bun.lockb").exists() or (root_dir / "bun.lock").exists()) and shutil.which("bun"):
        return [_tool("bun"), "run", script]
    if (root_dir / "yarn.lock").exists() and shutil.which("yarn"):
        return [_tool("yarn"), "run", script]
    return [_tool("npm"), "run", script]


def detect_lint_command(root_dir: Path) -> Optional[List[str]]:
    """Auto-detect project linter if available."""
    # Node.js
    pkg_file = root_dir / "package.json"
    if pkg_file.exists():
        try:
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            if "lint" in pkg.get("scripts", {}):
                return _pm_run(root_dir, "lint")
        except Exception:
            pass

    # Python
    tools = _pyproject_tools(root_dir)
    if (root_dir / "ruff.toml").exists() or (root_dir / ".ruff.toml").exists() or "ruff" in tools:
        if shutil.which("ruff"):
            return [_tool("ruff"), "check", "."]
    if (
        (root_dir / ".flake8").exists()
        or _has_ini_section(root_dir / "setup.cfg", "flake8")
        or _has_ini_section(root_dir / "tox.ini", "flake8")
    ) and shutil.which("flake8"):
        return [_tool("flake8"), "."]

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
                if "typecheck" in pkg.get("scripts", {}):
                    return _pm_run(root_dir, "typecheck")
            except Exception:
                pass
        if shutil.which("tsc"):
            return [_tool("tsc"), "--noEmit"]
        if shutil.which("npx"):
            return [_tool("npx"), "tsc", "--noEmit"]

    # Python MyPy
    if (
        (root_dir / "mypy.ini").exists()
        or (root_dir / ".mypy.ini").exists()
        or _has_ini_section(root_dir / "setup.cfg", "mypy")
        or "mypy" in _pyproject_tools(root_dir)
    ) and shutil.which("mypy"):
        return [_tool("mypy"), "."]

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
    skip_tests: bool = False,
    timeout: int = 120,
    trust_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all configured and detected checks for a project.

    trust_mode: 'trust' (silent), 'strict' (project-defined commands SKIPPED), 'default'
    (run + deprecation WARN). None resolves from CAPSULE_TRUST."""
    root_dir = root_dir.resolve()
    if trust_mode is None:
        trust_mode = resolve_trust_mode()
    project_cmds: List[str] = []
    config = load_project_config(root_dir)

    results = []
    has_failure = False
    has_incomplete = False

    # Gate commands run project-controlled code: warn when config differs from HEAD.
    drift = config_drift_warnings(root_dir)
    if drift:
        results.append({
            "name": "Config Integrity",
            "status": "WARNING",
            "command": "git status (gate config)",
            "duration": 0.0,
            "summary": f"{len(drift)} gate config file(s) differ from git HEAD; review before trusting results",
            "output": "\n".join("- " + w for w in drift),
        })

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

    def is_project_defined(cmd: List[str], from_config: bool) -> bool:
        """True when the command executes code the target project controls."""
        if from_config:
            return True
        base = Path(cmd[0]).name.lower().split(".")[0]
        if base in ("npm", "pnpm", "yarn", "bun") and (root_dir / "package.json").exists():
            return True
        if "pytest" in cmd and any((root_dir / d / "conftest.py").exists() for d in (".", "tests", "test")):
            return True
        return False

    project_flags: Dict[str, bool] = {}

    def resolve_cmd(label: str, override: Optional[str], key: str, detect) -> Optional[List[str]]:
        """Resolve a command; invalid config is reported as Configuration FAILED, not a traceback."""
        nonlocal has_failure
        try:
            raw = override or config.get(key)
            cmd = split_command(raw) if raw else detect(root_dir)
            if cmd and not override:
                cfg_defined = bool(config.get(key)) or (key == "test" and bool(config.get("test_cmd")))
                project_flags[key] = is_project_defined(cmd, cfg_defined)
            return cmd
        except (ValueError, AttributeError, TypeError) as exc:
            has_failure = True
            msg = f"Invalid {label} command: {exc}"
            results.append({
                "name": "Configuration",
                "status": "FAILED",
                "command": key,
                "duration": 0.0,
                "summary": msg,
                "output": msg,
            })
            return None

    def run_step(name: str, cmd: Optional[List[str]], skipped_summary: str, key: str = "") -> None:
        nonlocal has_failure
        if cmd and project_flags.get(key):
            if trust_mode == "strict":
                results.append({
                    "name": name,
                    "status": "SKIPPED",
                    "command": " ".join(cmd),
                    "summary": "Refused (strict mode): project-defined command not executed; use --trust or CAPSULE_TRUST=1",
                    "output": "",
                })
                return
            if trust_mode != "trust":
                project_cmds.append(f"{name}: {' '.join(cmd)}")
        if not cmd:
            results.append({
                "name": name,
                "status": "SKIPPED",
                "command": None,
                "summary": skipped_summary,
                "output": "",
            })
            return
        code, output, duration = execute_check(cmd, root_dir, timeout=timeout)
        if code != 0:
            has_failure = True
        results.append({
            "name": name,
            "status": "PASSED" if code == 0 else "FAILED",
            "command": " ".join(cmd),
            "duration": duration,
            "summary": f"{' '.join(cmd)} ({duration}s)",
            "output": output,
        })

    # 1. Tests
    if skip_tests:
        results.append({
            "name": "Tests",
            "status": "SKIPPED",
            "command": None,
            "summary": "Skipped by --skip-tests",
            "output": "",
        })
    else:
        test_cmd = resolve_cmd("test", test_cmd_override, "test", detect_test_command)
        run_step("Tests", test_cmd, "No test suite configured or detected", "test")

    # 2. Linters
    lint_cmd = resolve_cmd("lint", lint_cmd_override, "lint", detect_lint_command)
    run_step("Lint", lint_cmd, "No linter configured or detected", "lint")

    # 3. Typecheck
    typecheck_cmd = resolve_cmd("typecheck", typecheck_cmd_override, "typecheck", detect_typecheck_command)
    run_step("Typecheck", typecheck_cmd, "No typechecker configured or detected", "typecheck")

    if project_cmds:
        results.insert(0, {
            "name": "Project Code Trust",
            "status": "WARNING",
            "command": "trust policy",
            "duration": 0.0,
            "summary": f"{len(project_cmds)} project-defined command(s) executed WITHOUT explicit trust; default becomes --strict next release",
            "output": "\n".join("- " + c for c in project_cmds)
            + "\nPass --trust (or set CAPSULE_TRUST=1) to accept, or --strict (CAPSULE_TRUST=0) to refuse.",
        })

    # 4. Secrets & Diff Audit
    if not skip_secrets:
        try:
            issues = audit_git_diff(root_dir)
            only_incomplete = bool(issues) and all(i.get("severity") == "INCOMPLETE" for i in issues)
            if issues:
                if only_incomplete:
                    has_incomplete = True
                    summary = f"{len(issues)} file(s) could not be fully scanned (INCOMPLETE, not PASS)"
                else:
                    has_failure = True
                    summary = f"{len(issues)} suspicious pattern(s) or exposed secret(s) in diff"
                output = "\n".join(
                    f"- {issue.get('file') or '(repository)'}: {issue.get('description', '')}"
                    + (f" [{issue['snippet']}]" if issue.get("snippet") and not issue.get("file") else "")
                    for issue in issues
                )
                status = "INCOMPLETE" if only_incomplete else "FAILED"
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
        except NotAGitRepository:
            results.append({
                "name": "Secrets & Diff",
                "status": "SKIPPED",
                "command": "git diff audit",
                "summary": "Skipped: target is not a git repository (use --skip-secrets to silence)",
                "output": "",
            })
        except Exception as exc:
            has_failure = True
            results.append({
                "name": "Secrets & Diff",
                "status": "FAILED",
                "command": "git diff audit",
                "summary": f"Secrets audit crashed: {exc}",
                "output": str(exc),
            })

    # 5. Agent Alignment & Drift Audit (King Kai's Watchdog)
    # Automatically activates when an active agent shift exists in the Check-In Room,
    # or when explicitly requested via check_drift=True (--check-drift).
    auto_drift = False
    try:
        try:
            from .room import load_room_data
        except ImportError:
            from room import load_room_data
        # Read-only probe: never create .capsule/ in the target.
        room_json = root_dir / ".capsule" / "room.json"
        if room_json.exists():
            rdata = load_room_data(room_json)
            if rdata.get("active_shifts"):
                auto_drift = True
    except Exception as exc:
        corrupt = type(exc).__name__ == "RoomCorruptError"
        results.append({
            "name": "Check-In Room",
            "status": "WARNING",
            "command": "load_room_data",
            "duration": 0.0,
            "summary": ("room.json is CORRUPT; run `capsule room` for details" if corrupt
                        else f"Could not read room state: {type(exc).__name__}"),
            "output": f"{type(exc).__name__}: {exc}",
        })

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
                "status": "WARNING",
                "command": "capsule spy",
                "summary": f"Check crashed: {exc}",
                "output": f"{type(exc).__name__}: {exc}",
            })

    # 6. Lord Beerus' Architectural Inquisition (Code Griller)
    # Runs when explicitly requested via check_grill=True (--grill) or config "grill": true
    if check_grill or (config and config.get("grill") is True):
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
            elif grill_report["verdict"] == "INCOMPLETE":
                has_incomplete = True
                status = "INCOMPLETE"
                summary = "Beerus scan INCOMPLETE (some changes could not be inspected; not an approval)"
            elif grill_report["verdict"] == "WARN":
                status = "WARNING"
                summary = f"Hakai Threat: {threat} ({len(issues)} inquisition item(s) flagged)"
            elif grill_report["verdict"] == "PASS":
                status = "PASSED"
                summary = "Hakai Threat: DIVINE APPROVAL (Zero critical flaws)"
                output = ""
            else:
                has_incomplete = True
                status = "INCOMPLETE"
                summary = f"Unknown grill verdict {grill_report['verdict']!r}; treated as INCOMPLETE"

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
                "status": "WARNING",
                "command": "capsule grill",
                "summary": f"Check crashed: {exc}",
                "output": f"{type(exc).__name__}: {exc}",
            })

    executed_checks = [c for c in results if c["name"] in ("Tests", "Lint", "Typecheck") and c["status"] in ("PASSED", "FAILED")]
    if has_failure:
        verdict = "FAIL"
    elif has_incomplete:
        verdict = "INCOMPLETE"
    elif not executed_checks and not (
        skip_tests and any(c["name"] == "Secrets & Diff" and c["status"] == "PASSED" for c in results)
    ):
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
        elif status == "WARNING":
            badge = " [WARN] "
        elif status == "INCOMPLETE":
            badge = " [INCP] "
        else:
            badge = " [SKIP] "

        lines.append(f"{badge} {name:<16} {summary}")
        if (status in ("FAILED", "WARNING", "INCOMPLETE") or verbose) and check.get("output"):
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
    parser = argparse.ArgumentParser(
        description="Capsule Corp Project Verification Checker",
        epilog=PROJECT_CODE_NOTICE + "\n\n" + TRUST_HELP,
    )
    parser.add_argument("target_dir", nargs="?", default=".", help="Directory to check (defaults to CWD)")
    parser.add_argument("--trust", action="store_true", help="Explicitly trust project-defined commands (also CAPSULE_TRUST=1)")
    parser.add_argument("--strict", action="store_true", help="Refuse project-defined commands, report SKIPPED (also CAPSULE_TRUST=0)")
    parser.add_argument("--json", action="store_true", help="Output check results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full command outputs")
    parser.add_argument("--test-cmd", help="Explicit test command override")
    parser.add_argument("--lint-cmd", help="Explicit lint command override")
    parser.add_argument("--typecheck-cmd", help="Explicit typecheck command override")
    parser.add_argument("--skip-secrets", action="store_true", help="Skip git diff secret scanner")
    parser.add_argument("--check-drift", action="store_true", help="Run King Kai's agent drift watchdog audit")
    parser.add_argument("--timeout", type=int, default=120, help="Per-command timeout in seconds")
    parser.add_argument("--grill", action="store_true", help="Run Lord Beerus' architectural inquisition & code griller")
    args = parser.parse_args()

    target = Path(args.target_dir).resolve()
    if not target.exists():
        print(f"Error: Target directory {target} does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        trust_mode = resolve_trust_mode(args.trust, args.strict)
    except ValueError as exc:
        parser.error(str(exc))

    report = run_project_checks(
        target,
        trust_mode=trust_mode,
        test_cmd_override=args.test_cmd,
        lint_cmd_override=args.lint_cmd,
        typecheck_cmd_override=args.typecheck_cmd,
        skip_secrets=args.skip_secrets,
        check_drift=args.check_drift,
        check_grill=args.grill,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_check_report(report, verbose=args.verbose))

    sys.exit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
