#!/usr/bin/env python3
"""
Dr. Gero's Bot Factory (Capsule Corp)
Scaffolds a new specialized agent adhering strictly to the Capsule Corp DBZ Contract:
  1. Mandatory Dragon Ball Z Name & Persona
  2. One Job, One Voice, Explicit Anti-Jobs
  3. Lean Toolset Allowlist
  4. Deterministic Verification Gate
"""

import argparse
import sys
from pathlib import Path
from typing import List

DBZ_RESERVE_ARCHETYPES = {
    "gohan": {
        "alias": "Gohan (Deep Analytics & Diagnostics)",
        "role": "Deep Analytics & Edge-Case Bug Hunter",
        "jtbd": "Digs into complex failure traces, mathematical models, and edge-case bug diagnostics.",
        "description": "Scholar-warrior who analyzes complex failure traces and root causes.",
    },
    "krillin": {
        "alias": "Krillin (First Responder & Incident Triage)",
        "role": "Incident Responder & Alert Triage",
        "jtbd": "Sounds the alarm on production outages, triages alerts, and contains live incidents.",
        "description": "Vigilant first responder who triages alerts and contains production incidents.",
    },
    "roshi": {
        "alias": "Master Roshi (Codebase Mentor & Docs)",
        "role": "Codebase Mentor & Architectural Guide",
        "jtbd": "Explains complex subsystems to engineers, writes onboarding runbooks and ADRs.",
        "description": "Wise mentor who writes architectural documentation and onboarding guides.",
    },
    "android-16": {
        "alias": "Android 16 (Documentation & Changelogs)",
        "role": "User Documentation & Release Notes Specialist",
        "jtbd": "Writes polished, developer-friendly API documentation, release notes, and guides.",
        "description": "Gentle giant who writes clear user-facing documentation and changelogs.",
    },
    "tien": {
        "alias": "Tien (Observability & APM / Third Eye)",
        "role": "Observability, Telemetry & Tracing Specialist",
        "jtbd": "Monitors latency, traces distributed requests, and configures dashboards.",
        "description": "Unblinking third eye focused on system metrics, tracing, and alerts.",
    },
    "korin": {
        "alias": "Korin (Vendor & Integration Manager)",
        "role": "API Integration & Package Sentinel",
        "jtbd": "Evaluates, integrates, and monitors third-party APIs, SDKs, and vendor webhooks.",
        "description": "Senzu bean supplier who manages third-party integrations and dependencies.",
    },
    "shenron": {
        "alias": "Shenron (Backup & Disaster Recovery)",
        "role": "Database Snapshots & Disaster Recovery",
        "jtbd": "Executes automated database backups, validates snapshots, and runs recovery drills.",
        "description": "Eternal dragon that ensures data durability and instant disaster recovery.",
    },
    "yamcha": {
        "alias": "Yamcha (Chaos Engineering & Resilience)",
        "role": "Chaos Testing & Failover Specialist",
        "jtbd": "Intentionally simulates network partitions and service crashes to verify resilience.",
        "description": "Takes the hit in chaos experiments so the production cluster stays alive.",
    },
}


def generate_bot_markdown(
    name: str,
    alias: str,
    role: str,
    description: str,
    jtbd: str,
    boundaries: str,
    tools: List[str],
    verification: str
) -> str:
    tools_formatted = "\n".join([f"- `{t}`: Required for {t} operations." for t in tools])

    return f"""---
name: {name}
alias: {alias}
role: {role}
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
1. Execute immediately when inputs are unambiguous without preliminary conversational filler.
2. Maintain documentation integrity and touch only files within your assigned scope.
3. Verify your work with deterministic assertions before completing your turn.

---

## 4. Verification Gate (Mandatory)
- **Deterministic Assertion:** {verification}
"""


def update_registry_yaml(
    registry_path: Path,
    name: str,
    alias: str,
    role: str,
    jtbd: str,
    tools: List[str],
    verification: str,
    model_tier: str = "inherit"
):
    entry_lines = [
        f"\n  {name.replace('-', '_')}:",
        f"    name: \"{name}\"",
        f"    alias: \"{alias}\"",
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
    parser.add_argument("--name", help="Agent unique identifier (kebab-case, e.g. gohan)")
    parser.add_argument("--alias", help="DBZ Character Alias (e.g. Gohan (The Diagnostics Specialist))")
    parser.add_argument("--role", help="Professional title / role")
    parser.add_argument("--description", help="One-line summary for discovery")
    parser.add_argument("--jtbd", help="Job To Be Done (exact responsibility)")
    parser.add_argument("--boundaries", default="- Do not perform unsolicited refactoring outside scope.\n  - Do not introduce unrequested external dependencies.", help="Anti-goals")
    parser.add_argument("--tools", default="view_file,replace_file_content,run_command", help="Comma-separated allowed tools")
    parser.add_argument("--verification", help="Deterministic check or command")
    parser.add_argument("--model-tier", default="inherit", choices=["inherit", "flash", "flash_lite", "pro"], help="Model tier")
    parser.add_argument("--list-archetypes", action="store_true", help="List predefined Dragon Ball Z character archetypes ready for use")
    parser.add_argument("--from-archetype", help="Scaffold a bot directly from a predefined DBZ archetype (e.g. gohan, krillin, roshi)")

    args = parser.parse_args()

    if args.list_archetypes:
        print("==================================================================")
        print(" 🐉 CAPSULE CORP DBZ CHARACTER RESERVE BENCH")
        print("==================================================================")
        for key, arch in DBZ_RESERVE_ARCHETYPES.items():
            print(f"• {key:<12} | {arch['alias']:<35} | {arch['role']}")
            print(f"  JTBD: {arch['jtbd']}\n")
        print("Scaffold any of these with: capsule scaffold --from-archetype <name>")
        sys.exit(0)

    capsule_dir = Path(__file__).resolve().parent.parent
    bots_dir = capsule_dir / "bots"
    registry_file = capsule_dir / "registry.yaml"

    if args.from_archetype:
        key = args.from_archetype.lower().strip()
        if key not in DBZ_RESERVE_ARCHETYPES:
            print(f"Error: Unknown archetype '{key}'. Use --list-archetypes to see options.", file=sys.stderr)
            sys.exit(1)
        arch = DBZ_RESERVE_ARCHETYPES[key]
        name = key
        alias = arch["alias"]
        role = arch["role"]
        description = arch["description"]
        jtbd = arch["jtbd"]
        verification = "Native project test suite passes with exit code 0."
        tools = ["view_file", "replace_file_content", "run_command"]
        boundaries = "- Do not write features outside assigned scope.\n  - Enforce zero regressions."
        model_tier = "inherit"
    else:
        if not args.name or not args.alias or not args.role or not args.description or not args.jtbd or not args.verification:
            print("Error: Missing required arguments. To see reserve DBZ archetypes, run with --list-archetypes.", file=sys.stderr)
            sys.exit(1)
        name = args.name
        alias = args.alias
        role = args.role
        description = args.description
        jtbd = args.jtbd
        boundaries = args.boundaries
        tools = [t.strip() for t in args.tools.split(",") if t.strip()]
        verification = args.verification
        model_tier = args.model_tier

    clean_filename = name.replace("-", "_") + ".md"
    bot_file = bots_dir / clean_filename

    if bot_file.exists():
        print(f"Error: Bot file {bot_file} already exists. Aborting to prevent overwrite.", file=sys.stderr)
        sys.exit(1)

    markdown_content = generate_bot_markdown(
        name=name,
        alias=alias,
        role=role,
        description=description,
        jtbd=jtbd,
        boundaries=boundaries,
        tools=tools,
        verification=verification
    )

    bot_file.write_text(markdown_content, encoding="utf-8")
    print(f" Bot persona created at: {bot_file}")

    if registry_file.exists():
        update_registry_yaml(
            registry_path=registry_file,
            name=name,
            alias=alias,
            role=role,
            jtbd=jtbd,
            tools=tools,
            verification=verification,
            model_tier=model_tier
        )
        print(f" Registered in {registry_file}")


if __name__ == "__main__":
    main()
