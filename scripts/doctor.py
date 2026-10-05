#!/usr/bin/env python3
"""
Capsule Corp Doctor & Environment Diagnostics
Inspects system health, multi-AI connections, dependencies, and project setup:
  1. CLI & System PATH integration
  2. Python dependencies (PyYAML, pip-audit)
  3. Global AI connections:
     - Anthropic Claude Code (~/.claude/agents, skills, CLAUDE.md, settings.json)
     - Google Antigravity / Gemini (~/.gemini/config/skills, GEMINI.md)
     - OpenAI Codex (~/.codex/skills, rules)
     - Cursor & Windsurf (~/.cursorrules, ~/.windsurfrules)
     - Universal Workspace Standard (AGENTS.md)
  4. Active Project Health (target directory directives, test runner detection, git status)
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any

try:
    from .runtime import configure_utf8_stdio
except ImportError:
    from runtime import configure_utf8_stdio

configure_utf8_stdio()

CAPSULE_ROOT = Path(os.environ.get("CAPSULE_RESOURCE_ROOT", Path(__file__).resolve().parent.parent)).resolve()


def check_system() -> Dict[str, Any]:
    checks = []
    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 8)
    checks.append({
        "name": "Python Runtime",
        "status": "PASS" if py_ok else "FAIL",
        "detail": f"Python {py_ver} ({sys.executable})",
        "advice": "Python >= 3.8 is required." if not py_ok else None,
    })

    # 2. PyYAML
    try:
        import yaml
        yaml_ok = True
        yaml_detail = f"PyYAML {getattr(yaml, '__version__', 'available')}"
    except ImportError:
        yaml_ok = False
        yaml_detail = "PyYAML not installed"
    checks.append({
        "name": "PyYAML Dependency",
        "status": "PASS" if yaml_ok else "FAIL",
        "detail": yaml_detail,
        "advice": "Run `python3 -m pip install PyYAML`." if not yaml_ok else None,
    })

    # 3. pip-audit (security scanner)
    pip_audit_path = shutil.which("pip-audit")
    checks.append({
        "name": "Security Scanner (pip-audit)",
        "status": "PASS" if pip_audit_path else "WARN",
        "detail": pip_audit_path or "pip-audit not in PATH",
        "advice": "Run `pip install \"capsule-corp[security]\"` for dependency vulnerability auditing." if not pip_audit_path else None,
    })

    # 4. git
    git_path = shutil.which("git")
    checks.append({
        "name": "Git CLI",
        "status": "PASS" if git_path else "FAIL",
        "detail": git_path or "git not in PATH",
        "advice": "Install git for timeline diff and verification auditing." if not git_path else None,
    })

    # 5. capsule in PATH
    capsule_path = shutil.which("capsule")
    checks.append({
        "name": "Capsule CLI in PATH",
        "status": "PASS" if capsule_path else "WARN",
        "detail": capsule_path or "capsule not found in PATH",
        "advice": f"Add `export PATH=\"$PATH:{CAPSULE_ROOT}/bin\"` to ~/.zshrc." if not capsule_path else None,
    })

    return {"category": "System & Runtime", "checks": checks}


def check_ai_connections() -> Dict[str, Any]:
    home = Path.home()
    checks = []

    # Claude Code
    claude_agents = home / ".claude" / "agents"
    claude_skills = home / ".claude" / "skills"
    claude_rules = home / ".claude" / "CLAUDE.md"
    claude_settings = home / ".claude" / "settings.json"
    claude_connected = claude_agents.exists() and claude_skills.exists() and claude_rules.exists()
    claude_detail = []
    if claude_agents.exists():
        count = len(list(claude_agents.glob("*.md")))
        claude_detail.append(f"{count} agents")
    if claude_skills.exists():
        count = len([p for p in claude_skills.iterdir() if p.is_dir() or p.is_symlink()])
        claude_detail.append(f"{count} skills")
    if claude_rules.exists():
        claude_detail.append("rules linked")
    if claude_settings.exists() and "capsule" in claude_settings.read_text(encoding="utf-8", errors="ignore"):
        claude_detail.append("permissions allowed")

    checks.append({
        "name": "Anthropic Claude Code",
        "status": "PASS" if claude_connected else "WARN",
        "detail": ", ".join(claude_detail) if claude_detail else "Not synchronized",
        "advice": "Run `capsule sync --force` to link Claude Code agents, skills, and rules." if not claude_connected else None,
    })

    # Gemini / Antigravity
    gemini_skills = home / ".gemini" / "config" / "skills"
    gemini_rules = home / ".gemini" / "GEMINI.md"
    gemini_connected = gemini_skills.exists() and gemini_rules.exists()
    checks.append({
        "name": "Google Antigravity / Gemini",
        "status": "PASS" if gemini_connected else "WARN",
        "detail": f"{len(list(gemini_skills.iterdir())) if gemini_skills.exists() else 0} skills, rules linked" if gemini_connected else "Not synchronized",
        "advice": "Run `capsule sync --force` to link Gemini skills and rules." if not gemini_connected else None,
    })

    # Codex
    codex_skills = home / ".codex" / "skills"
    codex_rules = home / ".codex" / "rules" / "default.rules"
    codex_connected = codex_skills.exists()
    codex_allowed = codex_rules.exists() and "capsule" in codex_rules.read_text(encoding="utf-8", errors="ignore")
    checks.append({
        "name": "OpenAI Codex",
        "status": "PASS" if codex_connected and codex_allowed else "WARN",
        "detail": "skills linked, execution allowed" if (codex_connected and codex_allowed) else "Not fully configured",
        "advice": "Run `capsule sync --force` to link Codex skills and permissions." if not (codex_connected and codex_allowed) else None,
    })

    # Cursor & Windsurf
    cursor_rules = home / ".cursorrules"
    windsurf_rules = home / ".windsurfrules"
    checks.append({
        "name": "Cursor & Windsurf IDEs",
        "status": "PASS" if (cursor_rules.exists() and windsurf_rules.exists()) else "WARN",
        "detail": "rules installed in ~/.cursorrules and ~/.windsurfrules" if (cursor_rules.exists() and windsurf_rules.exists()) else "Global rules missing",
        "advice": "Run `capsule sync --force` to deploy global rules." if not (cursor_rules.exists() and windsurf_rules.exists()) else None,
    })

    # Universal Workspace Root
    workspace_agents = Path(os.environ.get("DEV_ROOT", CAPSULE_ROOT.parent.parent)) / "AGENTS.md"
    checks.append({
        "name": "Workspace Standard (AGENTS.md)",
        "status": "PASS" if workspace_agents.exists() else "INFO",
        "detail": f"Installed at {workspace_agents}" if workspace_agents.exists() else "No workspace AGENTS.md",
        "advice": "Run `capsule sync --force` to update workspace AGENTS.md." if not workspace_agents.exists() else None,
    })

    return {"category": "Global AI Connections", "checks": checks}


def check_project(project_dir: Path) -> Dict[str, Any]:
    checks = []
    if not project_dir.exists() or not project_dir.is_dir():
        return {"category": "Active Project", "checks": [{"name": "Directory", "status": "FAIL", "detail": f"{project_dir} not found"}]}

    # Git status
    git_dir = project_dir / ".git"
    checks.append({
        "name": "Git Repository",
        "status": "PASS" if git_dir.exists() else "INFO",
        "detail": "Initialized git repository" if git_dir.exists() else "Not a git repository",
    })

    # Directives present
    directives = []
    if (project_dir / "CLAUDE.md").exists():
        directives.append("CLAUDE.md (Claude Code)")
    if (project_dir / "GEMINI.md").exists():
        directives.append("GEMINI.md (Antigravity)")
    if (project_dir / "AGENTS.md").exists():
        directives.append("AGENTS.md (Universal)")
    if (project_dir / ".github" / "copilot-instructions.md").exists():
        directives.append("copilot-instructions.md")
    if (project_dir / ".cursorrules").exists():
        directives.append(".cursorrules")
    if (project_dir / ".windsurfrules").exists():
        directives.append(".windsurfrules")

    checks.append({
        "name": "AI Directives",
        "status": "PASS" if directives else "WARN",
        "detail": ", ".join(directives) if directives else "No AI directives installed in this project",
        "advice": f"Run `capsule init --tool claude {project_dir}` to initialize AI directives." if not directives else None,
    })

    # Test runner detection
    try:
        try:
            from .verify_project import detect_test_command
        except ImportError:
            try:
                from verify_project import detect_test_command
            except ImportError:
                sys.path.insert(0, str(CAPSULE_ROOT / "scripts"))
                from verify_project import detect_test_command
        cmd = detect_test_command(project_dir)
        checks.append({
            "name": "Test Runner Detection",
            "status": "PASS" if cmd else "INFO",
            "detail": f"Command: {' '.join(cmd)}" if cmd else "No standard test suite automatically detected",
            "advice": "Add a test script (package.json, pytest, cargo, go) so Trunks can automatically verify changes." if not cmd else None,
        })
    except Exception as exc:
        checks.append({
            "name": "Test Runner Detection",
            "status": "WARN",
            "detail": str(exc),
        })

    return {"category": f"Project: {project_dir.name}", "checks": checks}


def run_doctor(project_dir: Path) -> Dict[str, Any]:
    categories = [
        check_system(),
        check_ai_connections(),
        check_project(project_dir),
    ]
    has_fail = any(c["status"] == "FAIL" for cat in categories for c in cat["checks"])
    has_warn = any(c["status"] == "WARN" for cat in categories for c in cat["checks"])
    return {
        "status": "FAIL" if has_fail else ("WARN" if has_warn else "HEALTHY"),
        "categories": categories,
    }


def main():
    parser = argparse.ArgumentParser(description="Capsule Corp Environment Doctor & Diagnostic")
    parser.add_argument("target_dir", nargs="?", default=".", help="Project directory to inspect (defaults to CWD)")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    project_dir = Path(args.target_dir).resolve()
    report = run_doctor(project_dir)

    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if report["status"] == "FAIL" else 0

    print("=" * 80)
    print(" 🩺 CAPSULE CORP DOCTOR (MULTI-AI HEALTHCHECK)")
    print("=" * 80)

    for cat in report["categories"]:
        print(f"\n📂 {cat['category']}")
        print("-" * 80)
        for check in cat["checks"]:
            status = check["status"]
            icon = "✓" if status == "PASS" else ("!" if status == "WARN" else ("·" if status == "INFO" else "✗"))
            color = "\033[32m" if status == "PASS" else ("\033[33m" if status in ("WARN", "INFO") else "\033[31m")
            reset = "\033[0m"
            print(f"  {color}{icon}{reset} {check['name']:<32} | {check['detail']}")
            if check.get("advice") and status in ("FAIL", "WARN"):
                print(f"    ↪ Recommendation: {check['advice']}")

    print("\n" + "=" * 80)
    if report["status"] == "HEALTHY":
        print(" 🎉 VERDICT: HEALTHY. All Capsule Corp integrations are ready.")
    elif report["status"] == "WARN":
        print(" ⚠️  VERDICT: OPERATIONAL WITH WARNINGS. Review recommendations above.")
    else:
        print(" 🚨 VERDICT: ATTENTION REQUIRED. Critical dependencies or paths missing.")
    print("=" * 80)

    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
