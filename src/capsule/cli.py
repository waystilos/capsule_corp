"""Installed entry point for the Capsule Corp CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import List, Optional


def resource_root() -> Path:
    """Find bundled resources in a checkout or an installed environment."""
    override = os.environ.get("CAPSULE_RESOURCE_ROOT")
    if override:
        return Path(override).resolve()

    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "registry.yaml").exists():
        return checkout

    return Path(sysconfig.get_path("data")) / "share" / "capsule-corp"


def run_module(module: str, args: List[str]) -> int:
    env = os.environ.copy()
    env["CAPSULE_RESOURCE_ROOT"] = str(resource_root())
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        env=env,
    ).returncode


def cmd_list() -> int:
    registry = resource_root() / "registry.yaml"
    if not registry.exists():
        print(f"Error: bundled registry not found at {registry}", file=sys.stderr)
        return 1

    try:
        import yaml

        data = yaml.safe_load(registry.read_text(encoding="utf-8"))
        bots = data.get("bots", {}) if isinstance(data, dict) else {}
    except (OSError, ImportError, ValueError):
        print("Capsule Corp Cohort Registry:")
        print(registry.read_text(encoding="utf-8"))
        return 0

    print("=" * 90)
    print(" 🚀 CAPSULE CORP AGENT COHORT ROSTER")
    print("=" * 90)
    print(f"{'BOT ID':<16} | {'ALIAS':<32} | {'MODEL TIER':<10} | {'PRIMARY ROLE'}")
    print("-" * 18 + "+" + "-" * 34 + "+" + "-" * 12 + "+" + "-" * 24)
    for bot_id, details in bots.items():
        details = details if isinstance(details, dict) else {}
        name = details.get("name", bot_id)
        alias = details.get("alias", name)
        tier = details.get("model_tier", "inherit")
        role = details.get("role", "")
        print(f"{name:<16} | {alias[:32]:<32} | {tier:<10} | {role}")
    print("=" * 90)
    print(f"Total Agents: {len(bots)} | Resources: {resource_root()}")
    return 0


def cmd_test() -> int:
    tests = resource_root() / "tests"
    if tests.exists():
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-p", "test_*.py"],
            cwd=str(resource_root()),
        ).returncode

    print("Installed Capsule Corp package is ready; repository tests are not bundled.")
    print("Run `python -m unittest discover -s tests -p 'test_*.py'` from a source checkout.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("Usage: capsule {list|route|test|scaffold|audit|verify|security|init|sync} [options]")
        return 0

    command, extra = args[0], args[1:]
    if command == "list":
        return cmd_list()
    if command == "route":
        return run_module("scripts.route_request", extra)
    if command == "test":
        return cmd_test()
    if command == "scaffold":
        return run_module("scripts.scaffold_bot", extra)
    if command == "audit":
        return run_module("scripts.audit_transcripts", extra)
    if command == "verify":
        return run_module("scripts.verify_project", extra)
    if command == "security":
        return run_module("scripts.security_audit", extra)
    if command == "init":
        return run_module("scripts.init_project", extra)
    if command == "sync":
        if os.name == "nt":
            print("capsule sync currently requires Git Bash or WSL on Windows.", file=sys.stderr)
            return 1
        return run_module("scripts.sync_tools", extra)

    print(f"Unknown subcommand: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
