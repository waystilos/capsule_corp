#!/usr/bin/env python3
"""
Capsule Corp Startup Project Initializer
Sets up any new startup codebase with multi-AI agent configuration:
  - .github/copilot-instructions.md (GitHub Copilot Chat & Workspace)
  - AGENTS.md (Universal standard loaded by Codex, Claude, Cursor, Windsurf, Copilot)
  - .cursorrules (Cursor IDE)
  - .windsurfrules (Windsurf IDE)
"""

import argparse
import sys
import shutil
from pathlib import Path

CAPSULE_ROOT = Path(__file__).resolve().parent.parent


def init_project(target_dir: Path, force: bool = False):
    if not target_dir.exists():
        print(f"Error: Target directory {target_dir} does not exist.", file=sys.stderr)
        sys.exit(1)
    if not target_dir.is_dir():
        print(f"Error: Target path {target_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"🚀 Initializing Capsule Corp Multi-AI Directives in: {target_dir}")

    # 1. GitHub Copilot Instructions
    github_dir = target_dir / ".github"
    github_dir.mkdir(parents=True, exist_ok=True)
    copilot_src = CAPSULE_ROOT / ".github" / "copilot-instructions.md"
    copilot_dest = github_dir / "copilot-instructions.md"
    if copilot_src.exists() and (force or not copilot_dest.exists()):
        shutil.copy(copilot_src, github_dir / "copilot-instructions.md")
        print(f"  ✓ Installed .github/copilot-instructions.md (GitHub Copilot)")
    elif copilot_dest.exists():
        print("  · Preserved existing .github/copilot-instructions.md")

    # 2. Universal AGENTS.md
    agents_content = f"""# Capsule Corp Directives for this Project

All AI agents operating in this repository (Codex, Claude Code, GitHub Copilot, Gemini, Cursor, Windsurf) must follow the **Capsule Corp Standards**:

## Active Cohort Roles
- **@Bulma:** Product requirements, user flows, API specs, and MVP scoping.
- **@Piccolo:** Tactical decomposition and subagent orchestration. Never writes code directly.
- **@Goku:** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **@Android-17:** Security sentinel. Audits for secrets, OWASP risks, and CVEs.
- **@Trunks:** Verification gate. Runs test suite, linters, and typecheckers before changes are accepted.
- **@Android-18:** Refactoring specialist. Dead code elimination and technical debt cleanup.
- **@Vegeta:** Infrastructure commander. Docker, database migrations, CI/CD, and indexing.

## Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project test runner (e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All tests must pass with exit code 0 and zero secrets in diff.
"""
    agents_file = target_dir / "AGENTS.md"
    if force or not agents_file.exists():
        agents_file.write_text(agents_content, encoding="utf-8")
        print(f"  ✓ Installed AGENTS.md (Codex, Claude, Cursor, Windsurf)")
    else:
        print("  · Preserved existing AGENTS.md")

    # 3. .cursorrules
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
    windsurf_file = target_dir / ".windsurfrules"
    if force or not windsurf_file.exists():
        windsurf_file.write_text("""# Capsule Corp Directives for Windsurf
- Follow Capsule Corp standards: @Bulma (spec), @Piccolo (plan), @Goku (code), @Android-17 (security), @Trunks (tests).
- Run tests and verify exit code 0 before completing tasks.
        """, encoding="utf-8")
        print(f"  ✓ Installed .windsurfrules (Windsurf IDE)")
    else:
        print("  · Preserved existing .windsurfrules")

    print(f"\n🎉 Project is now fully wired into the Capsule Corp Agent Cohort!")
    print(f"You can now use GitHub Copilot, Codex, Claude Code, Cursor, and Windsurf seamlessly here.")


def main():
    parser = argparse.ArgumentParser(description="Capsule Corp Project Initializer")
    parser.add_argument("target_dir", nargs="?", default=".", help="Directory to initialize (defaults to CWD)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing directive files")
    args = parser.parse_args()

    target = Path(args.target_dir).resolve()
    init_project(target, force=args.force)


if __name__ == "__main__":
    main()
