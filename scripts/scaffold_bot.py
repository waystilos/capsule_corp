#!/usr/bin/env python3
"""
Dr. Gero's Bot Factory (Capsule Corp)
Inspired by Lauren Tan's Dr. Eggbot agent creation tool at SpaceXAI.

Scaffolds a new specialized agent adhering strictly to the 4-part Agent Contract:
  1. Target Persona & Creed
  2. Job To Be Done (JTBD) with strict boundaries
  3. Lean Toolset Allowlist
  4. Deterministic Verification Gate
"""

import argparse
import sys
from pathlib import Path
from typing import List


def generate_bot_markdown(
    name: str,
    alias: str,
    role: str,
    inspiration: str,
    description: str,
    jtbd: str,
    boundaries: str,
    tools: List[str],
    verification: str,
    creed: str
) -> str:
    tools_formatted = "\n".join([f"- `{t}`: Required for {t} operations." for t in tools])

    return f"""---
name: {name}
alias: {alias}
role: {role}
inspiration: {inspiration}
description: {description}
---

# {alias}: {role}

You are **{alias}**, a specialized operative at Capsule Corp.
You have **one job**, **one voice**, a lean tool allowlist, and zero tolerance for bloat.

---

## 1. Job To Be Done (JTBD)
- **Primary Mission:** {jtbd}
- **Boundaries (What you MUST NOT do):**
  {boundaries}

---

## 2. Allowed Tools
{tools_formatted}

---

## 3. Execution Directives (Bias to Act)
1. When input arguments and file targets are clear, execute immediately without preliminary conversational filler.
2. Maintain documentation integrity and do not modify code outside the defined task scope.
3. Once changes are made, run your verification gate before handing off.

---

## 4. Verification Gate (Mandatory)
- **Deterministic Assertion:** {verification}
"""


def update_registry_yaml(
    registry_path: Path,
    name: str,
    alias: str,
    role: str,
    inspiration: str,
    jtbd: str,
    tools: List[str],
    verification: str,
    model_tier: str = "inherit"
):
    entry_lines = [
        f"\n  {name.replace('-', '_')}:",
        f"    name: \"{name}\"",
        f"    alias: \"{alias}\"",
        f"    inspiration: \"{inspiration}\"",
        f"    role: \"{role}\"",
        f"    job_to_be_done: \"{jtbd}\"",
        f"    model_tier: \"{model_tier}\"",
        f"    allowed_tools:",
    ]
    for t in tools:
        entry_lines.append(f"      - \"{t}\"")
    entry_lines.append(f"    verification_gate: \"{verification}\"")

    content = registry_path.read_text(encoding="utf-8")
    content += "\n".join(entry_lines) + "\n"
    registry_path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Dr. Gero's Bot Factory (Capsule Corp)")
    parser.add_argument("--name", required=True, help="Agent unique identifier (kebab-case, e.g. android-18)")
    parser.add_argument("--alias", required=True, help="DBZ Character Alias (e.g. Android 18 (The Refactoring Specialist))")
    parser.add_argument("--role", required=True, help="Professional title / role")
    parser.add_argument("--inspiration", default="Specialist Swarm Worker (Lauren Tan)", help="Inspiration")
    parser.add_argument("--description", required=True, help="One-line summary for discovery")
    parser.add_argument("--jtbd", required=True, help="Job To Be Done (exact responsibility)")
    parser.add_argument("--boundaries", default="- Do not perform unsolicited refactoring outside the targeted scope.\n  - Do not introduce unrequested external dependencies.", help="Anti-goals")
    parser.add_argument("--tools", default="view_file,replace_file_content,run_command", help="Comma-separated allowed tools")
    parser.add_argument("--verification", required=True, help="Deterministic check or command")
    parser.add_argument("--creed", default="Efficiency and precision. Clean work, verified results.", help="Character creed")
    parser.add_argument("--model-tier", default="inherit", choices=["inherit", "flash", "flash_lite", "pro"], help="Model tier")

    args = parser.parse_args()

    capsule_dir = Path(__file__).resolve().parent.parent
    bots_dir = capsule_dir / "bots"
    registry_file = capsule_dir / "registry.yaml"

    bots_dir.mkdir(parents=True, exist_ok=True)
    clean_filename = args.name.replace("-", "_") + ".md"
    bot_file = bots_dir / clean_filename

    if bot_file.exists():
        print(f"Error: Bot file {bot_file} already exists. Aborting to prevent overwrite.", file=sys.stderr)
        sys.exit(1)

    tool_list = [t.strip() for t in args.tools.split(",") if t.strip()]

    markdown_content = generate_bot_markdown(
        name=args.name,
        alias=args.alias,
        role=args.role,
        inspiration=args.inspiration,
        description=args.description,
        jtbd=args.jtbd,
        boundaries=args.boundaries,
        tools=tool_list,
        verification=args.verification,
        creed=args.creed
    )

    bot_file.write_text(markdown_content, encoding="utf-8")
    print(f" Bot persona created at: {bot_file}")

    if registry_file.exists():
        update_registry_yaml(
            registry_path=registry_file,
            name=args.name,
            alias=args.alias,
            role=args.role,
            inspiration=args.inspiration,
            jtbd=args.jtbd,
            tools=tool_list,
            verification=args.verification,
            model_tier=args.model_tier
        )
        print(f" Registered in {registry_file}")


if __name__ == "__main__":
    main()
