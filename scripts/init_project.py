#!/usr/bin/env python3
"""
Capsule Corp Startup Project Initializer
Sets up any new startup codebase with multi-AI agent configuration:
  - .github/copilot-instructions.md (GitHub Copilot Chat & Workspace)
  - AGENTS.md (Universal standard loaded by Codex, Claude, Cursor, Windsurf, Copilot)
  - .cursorrules (Cursor IDE)
  - .windsurfrules (Windsurf IDE)
  - GEMINI.md (Google Antigravity / Gemini CLI / agy)

By default, only the Copilot integration is installed. Other integrations must
be selected explicitly with --tool, --tools, or --all-tools.
"""

import argparse
import os
import sys
import shutil
from pathlib import Path

try:
    from .runtime import configure_utf8_stdio
except ImportError:
    from runtime import configure_utf8_stdio

configure_utf8_stdio()

CAPSULE_ROOT = Path(os.environ.get("CAPSULE_RESOURCE_ROOT", Path(__file__).resolve().parent.parent)).resolve()
SUPPORTED_TOOLS = {"copilot", "agents", "codex", "cursor", "windsurf", "gemini", "agy", "claude", "claudecode", "auto"}
ALL_TOOLS = {"copilot", "agents", "cursor", "windsurf", "gemini", "claude"}


def detect_tools(target_dir: Path) -> set:
    """Auto-detect which AI agents or tools are active or installed."""
    detected = set()

    # 1. Environment variables set by active AI agent/IDE process
    if any(k in os.environ for k in ("CLAUDE_CODE", "CLAUDE_SESSION_ID", "CLAUDE_AGENT")):
        detected.add("claude")
    if any(k in os.environ for k in ("GEMINI_CLI", "ANTIGRAVITY_AGENT", "ANTIGRAVITY")):
        detected.add("gemini")
    if any(k in os.environ for k in ("CURSOR_AGENT", "CURSOR_SESSION")):
        detected.add("cursor")
    if any(k in os.environ for k in ("WINDSURF_AGENT", "WINDSURF_SESSION")):
        detected.add("windsurf")
    if any(k in os.environ for k in ("CODEX_CLI", "CODEX_SESSION")):
        detected.add("agents")

    # 2. Existing configurations present in target project
    if (target_dir / "CLAUDE.md").exists() or (target_dir / ".claude").exists():
        detected.add("claude")
    if (target_dir / "GEMINI.md").exists():
        detected.add("gemini")
    if (target_dir / ".cursorrules").exists() or (target_dir / ".cursor").exists():
        detected.add("cursor")
    if (target_dir / ".windsurfrules").exists() or (target_dir / ".windsurf").exists():
        detected.add("windsurf")
    if (target_dir / "AGENTS.md").exists():
        detected.add("agents")
    if (target_dir / ".github").exists() or (target_dir / ".git").exists():
        detected.add("copilot")

    # 3. Installed AI tools in user home directory if no active agent or project files matched
    if not detected:
        if (Path.home() / ".claude").exists() or shutil.which("claude"):
            detected.add("claude")
        if (Path.home() / ".gemini").exists() or shutil.which("agy"):
            detected.add("gemini")
        if (Path.home() / ".codex").exists() or shutil.which("codex"):
            detected.add("agents")
        if (Path.home() / ".cursorrules").exists():
            detected.add("cursor")
        if (Path.home() / ".windsurfrules").exists():
            detected.add("windsurf")
        detected.add("copilot")

    return detected or {"copilot", "agents"}


def init_project(target_dir: Path, force: bool = False, tools=None):
    if not target_dir.exists():
        print(f"Error: Target directory {target_dir} does not exist.", file=sys.stderr)
        sys.exit(1)
    if not target_dir.is_dir():
        print(f"Error: Target path {target_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"🚀 Initializing Capsule Corp Multi-AI Directives in: {target_dir}")
    selected_tools = set(tools or {"copilot"})
    if "auto" in selected_tools:
        selected_tools.remove("auto")
        selected_tools.update(detect_tools(target_dir))
    if "codex" in selected_tools:
        selected_tools.add("agents")
    if "agy" in selected_tools:
        selected_tools.add("gemini")
    if "claudecode" in selected_tools:
        selected_tools.add("claude")

    # 1. GitHub Copilot Instructions
    if "copilot" in selected_tools:
        github_dir = target_dir / ".github"
        github_dir.mkdir(parents=True, exist_ok=True)
        copilot_src = CAPSULE_ROOT / ".github" / "copilot-instructions.md"
        copilot_dest = github_dir / "copilot-instructions.md"
        if copilot_src.exists() and (force or not copilot_dest.exists()):
            shutil.copy(copilot_src, copilot_dest)
            print(f"  ✓ Installed .github/copilot-instructions.md (GitHub Copilot)")
        elif copilot_dest.exists():
            print("  · Preserved existing .github/copilot-instructions.md")

    # 2. Universal AGENTS.md
    agents_content = f"""# Capsule Corp Directives for this Project

All AI agents operating in this repository (Codex, Claude Code, GitHub Copilot, Gemini, Cursor, Windsurf) must follow the **Capsule Corp Standards**:

## Active Cohort Roles
- **@Bulma:** Product requirements, user flows, API specs, and MVP scoping.
- **@Videl:** User experience, accessibility, interaction design, and testable experience specifications.
- **@Piccolo:** Tactical decomposition and subagent orchestration. Never writes code directly.
- **@Goku:** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **@Android-17:** Security sentinel. Audits for secrets, OWASP risks, and CVEs.
- **@Trunks:** Verification gate. Runs test suite, linters, and typecheckers before changes are accepted.
- **@Android-18:** Refactoring specialist. Dead code elimination and technical debt cleanup.
- **@Vegeta:** Infrastructure commander. Docker, database migrations, CI/CD, and indexing.

## Routing Rule
If you are unsure who should handle a request, ask **@Whis** first. Never guess between specialists.

## Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
Whenever an AI agent (Claude Code, OpenAI Codex, Google Antigravity/Gemini, Cursor, Windsurf, GitHub Copilot) connects to this project:
- Check if your tool's specific configuration exists:
  - **Claude Code:** `CLAUDE.md` and `.claude/settings.json` -> run `capsule init --tool claude .`
  - **Google Antigravity / Gemini:** `GEMINI.md` -> run `capsule init --tool gemini .`
  - **Cursor:** `.cursorrules` -> run `capsule init --tool cursor .`
  - **Windsurf:** `.windsurfrules` -> run `capsule init --tool windsurf .`
  - **OpenAI Codex:** `AGENTS.md` -> run `capsule init --tool codex .`
  - **GitHub Copilot:** `.github/copilot-instructions.md` -> run `capsule init --tool copilot .`
- If missing, execute your `capsule init` command immediately on connection without requiring the developer to choose.

## Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project test runner (e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All tests must pass with exit code 0 and zero secrets in diff.
"""
    if "agents" in selected_tools:
        agents_file = target_dir / "AGENTS.md"
        if force or not agents_file.exists():
            agents_file.write_text(agents_content, encoding="utf-8")
            print(f"  ✓ Installed AGENTS.md (shared agent standard)")
        else:
            print("  · Preserved existing AGENTS.md")

    # 3. .cursorrules
    if "cursor" in selected_tools:
        cursor_file = target_dir / ".cursorrules"
        if force or not cursor_file.exists():
            cursor_file.write_text("""# Capsule Corp Directives for Cursor
- Adhere to the Capsule Corp cohort roles (@Bulma for specs, @Piccolo for plan, @Goku for code, @Android-17 for security, @Trunks for tests).
- Keep code modifications minimal, focused, and test-backed.
- Never hardcode API keys or secrets; use environment variables.
- Run tests and verify exit code 0 before completing tasks (`capsule verify`).
- Self-provisioning: If connected to a project with Capsule Corp directives where your or another tool's config is missing, execute `capsule init --tool <tool> .` autonomously.
""", encoding="utf-8")
            print(f"  ✓ Installed .cursorrules (Cursor IDE)")
        else:
            print("  · Preserved existing .cursorrules")

    # 4. .windsurfrules
    if "windsurf" in selected_tools:
        windsurf_file = target_dir / ".windsurfrules"
        if force or not windsurf_file.exists():
            windsurf_file.write_text("""# Capsule Corp Directives for Windsurf
- Follow Capsule Corp standards: @Bulma (spec), @Piccolo (plan), @Goku (code), @Android-17 (security), @Trunks (tests).
- Run tests and verify exit code 0 before completing tasks (`capsule verify`).
- Self-provisioning: If connected to a project with Capsule Corp directives where your or another tool's config is missing, execute `capsule init --tool <tool> .` autonomously.
""", encoding="utf-8")
            print(f"  ✓ Installed .windsurfrules (Windsurf IDE)")
        else:
            print("  · Preserved existing .windsurfrules")

    # 5. GEMINI.md
    gemini_content = f"""# Capsule Corp Directives for Gemini / Antigravity

All AI agents operating in this repository (Google Antigravity, Gemini CLI, agy) must follow the **Capsule Corp Standards**:

## Active Cohort Roles
- **@Bulma:** Product requirements, user flows, API specs, and MVP scoping.
- **@Videl:** User experience, accessibility, interaction design, and testable experience specifications.
- **@Piccolo:** Tactical decomposition and subagent orchestration. Never writes code directly.
- **@Goku:** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **@Android-17:** Security sentinel. Audits for secrets, OWASP risks, and CVEs.
- **@Trunks:** Verification gate. Runs test suite, linters, and typecheckers before changes are accepted.
- **@Android-18:** Refactoring specialist. Dead code elimination and technical debt cleanup.
- **@Vegeta:** Infrastructure commander. Docker, database migrations, CI/CD, and indexing.

## Routing Rule
If you are unsure who should handle a request, ask **@Whis** first. Never guess between specialists.

## Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
When operating in this or any project initialized with Capsule Corp:
- If `GEMINI.md` is missing from the project root, autonomously run `capsule init --tool gemini .`.
- If assisting with other tools, you may invoke `capsule init --tool <tool> .` as needed.

## Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project test runner (e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All tests must pass with exit code 0 and zero secrets in diff.
"""
    if "gemini" in selected_tools:
        gemini_file = target_dir / "GEMINI.md"
        if force or not gemini_file.exists():
            gemini_file.write_text(gemini_content, encoding="utf-8")
            print(f"  ✓ Installed GEMINI.md (Google Antigravity / Gemini)")
        else:
            print("  · Preserved existing GEMINI.md")

    # 6. Anthropic Claude Code (CLAUDE.md & .claude/settings.json)
    claude_content = f"""# Capsule Corp Directives for Claude Code

All AI agents operating in this repository (Claude Code) must follow the **Capsule Corp Standards**:

## Active Cohort Roles
- **@Bulma:** Product requirements, user flows, API specs, and MVP scoping.
- **@Videl:** User experience, accessibility, interaction design, and testable experience specifications.
- **@Piccolo:** Tactical decomposition and subagent orchestration. Never writes code directly.
- **@Goku:** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **@Android-17:** Security sentinel. Audits for secrets, OWASP risks, and CVEs.
- **@Trunks:** Verification gate. Runs test suite, linters, and typecheckers before changes are accepted.
- **@Android-18:** Refactoring specialist. Dead code elimination and technical debt cleanup.
- **@Vegeta:** Infrastructure commander. Docker, database migrations, CI/CD, and indexing.

## Routing Rule
If you are unsure who should handle a request, ask **@Whis** first. Never guess between specialists.

## Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
When operating in this or any project initialized with Capsule Corp:
- If `CLAUDE.md` or `.claude/settings.json` is missing, autonomously run `capsule init --tool claude .`.
- If assisting with other AI agents, you may invoke `capsule init --tool <tool> .` as needed.

## Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project test runner (e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All tests must pass with exit code 0 and zero secrets in diff.
"""
    if "claude" in selected_tools:
        claude_file = target_dir / "CLAUDE.md"
        if force or not claude_file.exists():
            claude_file.write_text(claude_content, encoding="utf-8")
            print("  ✓ Installed CLAUDE.md (Anthropic Claude Code)")
        else:
            print("  · Preserved existing CLAUDE.md")

        claude_dir = target_dir / ".claude"
        claude_settings = claude_dir / "settings.json"
        claude_settings_content = """{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(capsule *)",
      "Bash(./bin/capsule *)"
    ]
  }
}
"""
        if force or not claude_settings.exists():
            claude_dir.mkdir(parents=True, exist_ok=True)
            claude_settings.write_text(claude_settings_content, encoding="utf-8")
            print("  ✓ Installed .claude/settings.json (Claude Code permissions)")
        else:
            print("  · Preserved existing .claude/settings.json")

    configured = ", ".join(sorted(selected_tools))
    print(f"\n🎉 Capsule Corp configured for: {configured}")


def main():
    parser = argparse.ArgumentParser(description="Capsule Corp Project Initializer")
    parser.add_argument("target_dir", nargs="?", default=".", help="Directory to initialize (defaults to CWD)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing directive files")
    parser.add_argument("--tool", action="append", choices=sorted(SUPPORTED_TOOLS), help="Install one integration; repeat for multiple tools")
    parser.add_argument("--tools", help="Comma-separated integrations to install")
    parser.add_argument("--auto", action="store_true", help="Auto-detect active agent or installed tools and initialize them")
    parser.add_argument("--all-tools", action="store_true", help="Install all supported project integrations")
    args = parser.parse_args()

    requested_tools = set(args.tool or [])
    if args.tools:
        requested_tools.update(tool.strip().lower() for tool in args.tools.split(",") if tool.strip())
    if args.all_tools:
        requested_tools.update(ALL_TOOLS)
    if args.auto:
        requested_tools.add("auto")
    if requested_tools - SUPPORTED_TOOLS:
        invalid = ", ".join(sorted(requested_tools - SUPPORTED_TOOLS))
        parser.error(f"unsupported tool(s): {invalid}")

    target = Path(args.target_dir).resolve()
    init_project(target, force=args.force, tools=requested_tools or {"copilot"})


if __name__ == "__main__":
    main()
