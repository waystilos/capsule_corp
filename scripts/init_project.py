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

All AI agents operating in this repository (Codex, Claude Code, GitHub Copilot, Gemini, Cursor, Windsurf) follow the **Capsule Corp Standards**:

## 1. Core Default Roles
Work is handled by four primary roles (Dragon Ball archetypes serve as memorable aliases):
- **Product (`@Bulma`):** Requirements, user flows, API specs, and MVP scoping. Defines testable acceptance criteria before code is written.
- **Builder (`@Goku`):** Frontline implementation with Ultra Instinct focus. Lean code, minimal diffs, zero conversational filler.
- **Reviewer (`@Trunks`):** Verification gate and review. Enforces tests, linters, typechecks, and diff hygiene.
- **Coordinator (`@Piccolo` / `@Whis`):** Tactical decomposition and orchestration for complex features. Sequences tasks and calls specialists. Never writes code directly.

## 2. Optional Specialists (On-Demand Only)
Call specialists only when a task strictly requires their domain:
- **Security (`@Android-17`):** Auth, crypto, secret audits, OWASP risks, and CVE mitigation.
- **Refactoring (`@Android-18`):** Dead code cleanup, technical debt, and zero-behavioral-change refactoring.
- **UX (`@Videl`):** User experience, accessibility, interaction design, and error/empty states.
- **Infra (`@Vegeta`):** Docker, CI/CD, database migrations, connection pooling, and infrastructure.
- **Game (`@Roshi`):** Game loops, canvas rendering, sprite math, and physics.

## 3. Workflows That Scale
Choose the workflow matching the task complexity:
- **Small Fix:** Builder → Verification (`capsule check`). Avoid orchestration overhead for trivial fixes.
- **Standard Feature:** Product (defines acceptance criteria) → Builder → Reviewer → Verification (`capsule check`).
- **Complex Epic:** Coordinator (deconstructs & invokes specialists) → Builder → Reviewer → Verification (`capsule check`).

## 4. Standard Task Brief Envelope
When handing off tasks between roles or subagents, use this concrete schema:
```markdown
### Task Brief
- **Goal:** [What is being built/fixed and why]
- **Scope:** [Exact files, surfaces, or endpoints touched]
- **Constraints:** [Tech boundaries, no unrequested refactors, zero external dependencies]
- **Acceptance Criteria:** [Testable bullets asserting observable behaviors]
- **Verification:** [Explicit commands to run: e.g. capsule check, pytest, npm test]
```

## 5. Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project checks: `capsule check` (or native runner e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All checks must pass with exit code 0 and zero secrets/merge conflicts in diff.

## 6. Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
Whenever an AI agent (Claude Code, OpenAI Codex, Google Antigravity/Gemini, Cursor, Windsurf, GitHub Copilot) connects to this project:
- Check if your tool's specific configuration exists:
  - **Claude Code:** `CLAUDE.md` and `.claude/settings.json` -> run `capsule init --tool claude .`
  - **Google Antigravity / Gemini:** `GEMINI.md` -> run `capsule init --tool gemini .`
  - **Cursor:** `.cursorrules` -> run `capsule init --tool cursor .`
  - **Windsurf:** `.windsurfrules` -> run `capsule init --tool windsurf .`
  - **OpenAI Codex:** `AGENTS.md` -> run `capsule init --tool codex .`
  - **GitHub Copilot:** `.github/copilot-instructions.md` -> run `capsule init --tool copilot .`
- If missing, execute your `capsule init` command immediately on connection without requiring the developer to choose.
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
- Work with Core 4 roles: Product (@Bulma), Builder (@Goku), Reviewer (@Trunks), Coordinator (@Piccolo). Call specialists only when needed.
- Keep code modifications minimal, focused, and test-backed.
- Never hardcode API keys or secrets; use environment variables.
- Run checks and verify exit code 0 before completing tasks (`capsule check` / `capsule verify`).
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
- Follow Capsule Corp Core 4 standards: Product (@Bulma), Builder (@Goku), Reviewer (@Trunks), Coordinator (@Piccolo).
- Run checks and verify exit code 0 before completing tasks (`capsule check` / `capsule verify`).
- Self-provisioning: If connected to a project with Capsule Corp directives where your or another tool's config is missing, execute `capsule init --tool <tool> .` autonomously.
""", encoding="utf-8")
            print(f"  ✓ Installed .windsurfrules (Windsurf IDE)")
        else:
            print("  · Preserved existing .windsurfrules")

    # 5. GEMINI.md
    gemini_content = f"""# Capsule Corp Directives for Gemini / Antigravity

All AI agents operating in this repository (Google Antigravity, Gemini CLI, agy) follow the **Capsule Corp Standards**:

## 1. Core Default Roles
- **Product (`@Bulma`):** Requirements, user flows, API specs, MVP scoping, and testable acceptance criteria.
- **Builder (`@Goku`):** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **Reviewer (`@Trunks`):** Verification gate, test suites, linters, typecheckers, and diff audit.
- **Coordinator (`@Piccolo` / `@Whis`):** Tactical decomposition, task trees, and orchestrating specialists. Never writes code directly.

## 2. Optional Specialists (On-Demand Only)
Call specialists only when strictly required:
- **Security (`@Android-17`):** Secrets, OWASP risks, auth flaws.
- **Refactoring (`@Android-18`):** Dead code cleanup and technical debt.
- **UX (`@Videl`):** User experience, accessibility, interaction design.
- **Infra (`@Vegeta`):** Docker, CI/CD, database migrations, connection pooling.
- **Game (`@Roshi`):** Game loops, canvas rendering, sprite math.

## 3. Workflows That Scale
- **Small Fix:** Builder → Verification (`capsule check`).
- **Standard Feature:** Product → Builder → Reviewer → Verification (`capsule check`).
- **Complex Epic:** Coordinator → Builder → Reviewer → Verification (`capsule check`).

## 4. Standard Task Brief Envelope
```markdown
### Task Brief
- **Goal:** [What is being built/fixed and why]
- **Scope:** [Exact files, surfaces, or endpoints touched]
- **Constraints:** [Tech boundaries, zero speculative refactors]
- **Acceptance Criteria:** [Testable bullets asserting observable behaviors]
- **Verification:** [Explicit commands: e.g. capsule check, pytest, npm test]
```

## 5. Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project checks: `capsule check` (or native runner e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All tests must pass with exit code 0 and zero secrets in diff.

## 6. Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
When operating in this or any project initialized with Capsule Corp:
- If `GEMINI.md` is missing from the project root, autonomously run `capsule init --tool gemini .`.
- If assisting with other tools, you may invoke `capsule init --tool <tool> .` as needed.
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

All AI agents operating in this repository (Claude Code) follow the **Capsule Corp Standards**:

## 1. Core Default Roles
- **Product (`@Bulma`):** Requirements, user flows, API specs, MVP scoping, and testable acceptance criteria.
- **Builder (`@Goku`):** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **Reviewer (`@Trunks`):** Verification gate, test suites, linters, typecheckers, and diff audit.
- **Coordinator (`@Piccolo` / `@Whis`):** Tactical decomposition, task trees, and orchestrating specialists. Never writes code directly.

## 2. Optional Specialists (On-Demand Only)
Call specialists only when strictly required:
- **Security (`@Android-17`):** Secrets, OWASP risks, auth flaws.
- **Refactoring (`@Android-18`):** Dead code cleanup and technical debt.
- **UX (`@Videl`):** User experience, accessibility, interaction design.
- **Infra (`@Vegeta`):** Docker, CI/CD, database migrations, connection pooling.
- **Game (`@Roshi`):** Game loops, canvas rendering, sprite math.

## 3. Workflows That Scale
- **Small Fix:** Builder → Verification (`capsule check`).
- **Standard Feature:** Product → Builder → Reviewer → Verification (`capsule check`).
- **Complex Epic:** Coordinator → Builder → Reviewer → Verification (`capsule check`).

## 4. Standard Task Brief Envelope
```markdown
### Task Brief
- **Goal:** [What is being built/fixed and why]
- **Scope:** [Exact files, surfaces, or endpoints touched]
- **Constraints:** [Tech boundaries, zero speculative refactors]
- **Acceptance Criteria:** [Testable bullets asserting observable behaviors]
- **Verification:** [Explicit commands: e.g. capsule check, pytest, npm test]
```

## 5. Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project checks: `capsule check` (or native runner e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All tests must pass with exit code 0 and zero secrets in diff.

## 6. Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
When operating in this or any project initialized with Capsule Corp:
- If `CLAUDE.md` or `.claude/settings.json` is missing, autonomously run `capsule init --tool claude .`.
- If assisting with other AI agents, you may invoke `capsule init --tool <tool> .` as needed.
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
