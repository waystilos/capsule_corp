#!/usr/bin/env python3
"""
Capsule Corp Startup Project Initializer
Sets up any new startup codebase with multi-AI agent configuration:
  - .github/copilot-instructions.md (GitHub Copilot Chat & Workspace)
  - AGENTS.md (Universal standard loaded by Codex, Claude, Cursor, Windsurf, Copilot)
  - .cursorrules (Cursor IDE)
  - .windsurfrules (Windsurf IDE)

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
SUPPORTED_TOOLS = {"copilot", "agents", "codex", "cursor", "windsurf"}
ALL_TOOLS = {"copilot", "agents", "cursor", "windsurf"}


def init_project(target_dir: Path, force: bool = False, tools=None):
    if not target_dir.exists():
        print(f"Error: Target directory {target_dir} does not exist.", file=sys.stderr)
        sys.exit(1)
    if not target_dir.is_dir():
        print(f"Error: Target path {target_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"🚀 Initializing Capsule Corp Multi-AI Directives in: {target_dir}")
    selected_tools = set(tools or {"copilot"})
    if "codex" in selected_tools:
        selected_tools.add("agents")

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
- Run tests and verify exit code 0 before completing tasks.
        """, encoding="utf-8")
            print(f"  ✓ Installed .windsurfrules (Windsurf IDE)")
        else:
            print("  · Preserved existing .windsurfrules")

    configured = ", ".join(sorted(selected_tools))
    print(f"\n🎉 Capsule Corp configured for: {configured}")


def main():
    parser = argparse.ArgumentParser(description="Capsule Corp Project Initializer")
    parser.add_argument("target_dir", nargs="?", default=".", help="Directory to initialize (defaults to CWD)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing directive files")
    parser.add_argument("--tool", action="append", choices=sorted(SUPPORTED_TOOLS), help="Install one integration; repeat for multiple tools")
    parser.add_argument("--tools", help="Comma-separated integrations to install")
    parser.add_argument("--all-tools", action="store_true", help="Install all supported project integrations")
    args = parser.parse_args()

    requested_tools = set(args.tool or [])
    if args.tools:
        requested_tools.update(tool.strip().lower() for tool in args.tools.split(",") if tool.strip())
    if args.all_tools:
        requested_tools.update(ALL_TOOLS)
    if requested_tools - SUPPORTED_TOOLS:
        invalid = ", ".join(sorted(requested_tools - SUPPORTED_TOOLS))
        parser.error(f"unsupported tool(s): {invalid}")

    target = Path(args.target_dir).resolve()
    init_project(target, force=args.force, tools=requested_tools or {"copilot"})


if __name__ == "__main__":
    main()
