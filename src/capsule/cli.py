"""Installed entry point for the Capsule Corp CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import List, Optional


def _configure_utf8_stdio() -> None:
    """Keep CLI output safe when Windows redirects stdout through cp1252."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


_configure_utf8_stdio()


def _installed_resource_candidates() -> List[Path]:
    """Return data-file locations used by system, virtualenv, and --user installs."""
    data = Path(sysconfig.get_path("data"))
    purelib = Path(sysconfig.get_path("purelib"))
    userbase = sysconfig.get_config_var("userbase")
    candidates = [data / "share" / "capsule-corp"]
    if userbase:
        candidates.append(Path(userbase) / "share" / "capsule-corp")
    candidates.extend(
        [
            purelib.parent / "share" / "capsule-corp",
            purelib.parent.parent / "share" / "capsule-corp",
        ]
    )

    unique = []
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate not in unique:
            unique.append(candidate)
    return unique


def resource_root() -> Path:
    """Find bundled resources in a checkout or an installed environment."""
    override = os.environ.get("CAPSULE_RESOURCE_ROOT")
    if override:
        return Path(override).resolve()

    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "registry.yaml").exists():
        return checkout

    candidates = _installed_resource_candidates()
    for candidate in candidates:
        if (candidate / "registry.yaml").exists():
            return candidate
    return candidates[0]


def run_module(module: str, args: List[str]) -> int:
    env = os.environ.copy()
    env["CAPSULE_RESOURCE_ROOT"] = str(resource_root())
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        env=env,
    ).returncode


def cmd_list(args: Optional[List[str]] = None) -> int:
    registry = resource_root() / "registry.yaml"
    if not registry.exists():
        print(f"Error: bundled registry not found at {registry}", file=sys.stderr)
        return 1

    if "--json" in (args or []):
        import json
        from scripts import models
        cfg, warnings = models.load_config(resource_root())
        for w in warnings:
            print(w, file=sys.stderr)
        try:
            print(json.dumps({"bots": models.list_bots(resource_root())}, indent=2))
        except models.ModelsError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        import yaml
    except ImportError:
        print("Capsule Corp Cohort Registry:")
        try:
            print(registry.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"Error: unable to read bundled registry: {exc}", file=sys.stderr)
            return 1
        return 0
    try:
        data = yaml.safe_load(registry.read_text(encoding="utf-8"))
        bots = data.get("bots", {}) if isinstance(data, dict) else {}
    except OSError as exc:
        print(f"Error: unable to read bundled registry: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"Error: bundled registry is invalid YAML: {exc}", file=sys.stderr)
        return 1

    print("=" * 90)
    print(" 🚀 CAPSULE CORP AGENT COHORT ROSTER")
    print("=" * 90)
    print(f"{'BOT ID':<16} | {'ALIAS':<32} | {'MODEL TIER':<10} | {'MODEL':<10} | {'PRIMARY ROLE'}")
    print("-" * 18 + "+" + "-" * 34 + "+" + "-" * 12 + "+" + "-" * 12 + "+" + "-" * 24)
    from scripts import models
    cfg, warnings = models.load_config(resource_root())
    for w in warnings:
        print(w, file=sys.stderr)
    for bot_id, details in bots.items():
        details = details if isinstance(details, dict) else {}
        name = details.get("name", bot_id)
        alias = details.get("alias", name)
        tier = details.get("model_tier", "inherit")
        role = details.get("role", "")
        try:
            model = models.resolve_model(bot=name, root=resource_root(), config=cfg)["model"]
        except models.ModelsError:
            model = "?"
        print(f"{name:<16} | {alias[:32]:<32} | {tier:<10} | {model:<10} | {role}")
    print("=" * 90)
    print(f"Total Agents: {len(bots)} | Resources: {resource_root()}")
    return 0


def cmd_test() -> int:
    tests = resource_root() / "tests"
    if tests.exists():
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", str(tests), "-p", "test_*.py"],
            cwd=str(resource_root()),
            env=env,
        ).returncode

    print("Installed Capsule Corp package is ready; repository tests are not bundled.")
    print("Run `python -m unittest discover -s tests -p 'test_*.py'` from a source checkout.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("Usage: capsule {check|validate|room|spy|clock-in|clock-out|heartbeat|send|inbox|ack|list|route|models|doctor|test|scaffold|audit|verify|security|attack|grill|init|sync} [options]")
        return 0

    command, extra = args[0], args[1:]
    if command == "check":
        return run_module("scripts.check_project", extra)
    if command == "validate":
        return run_module("scripts.validate_idea", extra)
    if command in {"room", "conference"}:
        return run_module("scripts.room", ["status"] + extra)
    if command in {"spy", "watchdog"}:
        return run_module("scripts.spy_watchdog", extra)
    if command == "clock-in":
        return run_module("scripts.room", ["clock-in"] + extra)
    if command == "clock-out":
        return run_module("scripts.room", ["clock-out"] + extra)
    if command in {"heartbeat", "touch"}:
        return run_module("scripts.room", ["heartbeat"] + extra)
    if command in {"send", "inbox", "ack"}:
        return run_module("scripts.messaging", [command] + extra)
    if command == "list":
        return cmd_list(extra)
    if command == "route":
        return run_module("scripts.route_request", extra)
    if command == "models":
        return run_module("scripts.models", extra)
    if command == "doctor":
        return run_module("scripts.doctor", extra)
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
    if command in {"attack", "redteam"}:
        return run_module("scripts.red_team", extra)
    if command in {"grill", "inquisition"}:
        return run_module("scripts.grill_code", extra)
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
