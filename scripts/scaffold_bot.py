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
import json
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import List

try:
    from .runtime import configure_utf8_stdio
    from . import sanitize as _sanitize
except ImportError:
    from runtime import configure_utf8_stdio
    import sanitize as _sanitize  # type: ignore

configure_utf8_stdio()

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

BOT_NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")


def validate_bot_name(name: str) -> None:
    if not name or name.startswith("-") or name.endswith("-") or "--" in name or not BOT_NAME_PATTERN.fullmatch(name):
        raise ValueError("name must contain only lowercase letters, numbers, and single hyphens")


GENERIC_WORDS = frozenset({
    "fix", "test", "tests", "build", "add", "update", "implement", "review", "security", "bug", "bugs",
    "code", "feature", "refactor", "deploy", "plan", "verify", "check", "debug", "docs", "lint",
    "api", "ci", "auth", "design", "product", "ux", "run", "make", "create", "change", "help",
})

KNOWN_TOOLS = (
    "Read", "Write", "Edit", "MultiEdit", "Bash", "Grep", "Glob", "LS", "NotebookEdit",
    "WebFetch", "WebSearch", "TodoWrite", "Task", "Agent",
)
# Legacy Capsule tool names map onto enforced Claude Code tool names.
TOOL_ALIASES = {
    "view_file": "Read", "read_file": "Read", "replace_file_content": "Edit",
    "write_file": "Write", "run_command": "Bash", "grep_search": "Grep", "list_dir": "LS",
}
_KNOWN_LOWER = {t.lower(): t for t in KNOWN_TOOLS}


def canonical_tools(tools: List[str]) -> List[str]:
    """Map to canonical enforced tool names; reject '*' and anything not on the known list."""
    out: List[str] = []
    for raw in tools:
        t = clean_line(raw, 64)
        if not t:
            continue
        if "*" in t:
            raise ValueError("wildcard tool '*' is not allowed; list explicit tools")
        canon = TOOL_ALIASES.get(t.lower()) or _KNOWN_LOWER.get(t.lower())
        if not canon:
            raise ValueError(f"unknown tool '{t}'; allowed: {', '.join(KNOWN_TOOLS)}")
        if canon not in out:
            out.append(canon)
    if not out:
        raise ValueError("at least one tool is required")
    return out[:20]


def routing_reserved_keywords(routing_path: Path) -> set:
    """Strong keywords (and owners) already claimed by existing routes."""
    if not routing_path or not Path(routing_path).exists():
        return set()
    text = Path(routing_path).read_text(encoding="utf-8")
    found = set()
    try:
        import yaml
        for r in (yaml.safe_load(text) or {}).get("routes") or []:
            for k in r.get("strong_keywords") or []:
                found.add(str(k).strip().lower())
            if r.get("owner"):
                found.add(str(r["owner"]).strip().lower())
        return found
    except ImportError:
        pass  # PyYAML absent: regex fallback below
    except (ValueError, AttributeError, TypeError, yaml.YAMLError) as exc:
        print(f"warning: routing YAML unparseable, using regex fallback: {exc}", file=sys.stderr)
        found = set()
    for m in re.finditer(r"^\s+(?:strong_keywords|owner):\s*\[?([^\]\n]*)\]?", text, re.MULTILINE):
        for k in m.group(1).split(","):
            k = k.strip().strip("\"'").lower()
            if k:
                found.add(k)
    return found


def check_routing_collisions(routing_path: Path, name: str, alias: str) -> None:
    first = alias.split("(")[0].strip().lower()
    reserved = routing_reserved_keywords(routing_path)
    for term in dict.fromkeys(t for t in (name.lower(), first) if t):
        if term in GENERIC_WORDS:
            raise ValueError(f"'{term}' is a generic word and would steal unrelated requests; pick a distinctive name/alias")
        if term in reserved:
            raise ValueError(f"'{term}' collides with an existing route keyword/owner; pick a distinctive name/alias")


_TOOL_RE = re.compile(r"[^A-Za-z0-9_.:*/-]")
TIER_PATTERN = re.compile(r"^[a-z0-9_]+$")


def clean_line(value: str, max_len: int = 200) -> str:
    """Single-line text: control chars/newlines become spaces, whitespace collapsed, length capped."""
    text = _sanitize.scrub(value, control_to_space=True)
    return " ".join(text.split())[:max_len]


def clean_boundaries(value: str, max_lines: int = 10, max_len: int = 200) -> str:
    """Boundary bullets: each line cleaned; front-matter fences and headings dropped; '- ' enforced."""
    lines = []
    for raw in re.split(r"[\r\n\u2028\u2029]+", str(value or "")):
        line = clean_line(raw, max_len)
        if not line or line.startswith("#") or set(line) <= set("-=_* "):
            continue
        if not line.startswith("- "):
            line = "- " + line.lstrip("-* ")
        lines.append(line)
    return "\n  ".join(lines[:max_lines])


def clean_tools(tools: List[str], max_tools: int = 20) -> List[str]:
    cleaned = []
    for t in tools:
        t = _TOOL_RE.sub("", clean_line(t, 64))
        if t and t not in cleaned:
            cleaned.append(t)
    return cleaned[:max_tools]


def generate_bot_markdown(
    name: str,
    alias: str,
    role: str,
    description: str,
    jtbd: str,
    boundaries: str,
    tools: List[str],
    verification: str,
    model_tier: str = "inherit",
) -> str:
    alias = clean_line(alias, 120)
    role = clean_line(role, 120)
    description = clean_line(description, 300)
    jtbd = clean_line(jtbd, 400)
    verification = clean_line(verification, 300)
    boundaries = clean_boundaries(boundaries)
    tools = canonical_tools(tools)
    model_tier = normalize_tier(model_tier)
    if not TIER_PATTERN.fullmatch(model_tier) and model_tier != "inherit":
        raise ValueError(f"invalid model tier '{model_tier}'")
    tools_formatted = "\n".join([f"- `{t}`: Required for {t} operations." for t in tools])
    yaml_name = json.dumps(name)
    yaml_alias = json.dumps(alias)
    yaml_role = json.dumps(role)
    yaml_description = json.dumps(description)
    tier_line = "" if model_tier == "inherit" else f"\nmodel_tier: {model_tier}"

    return f"""---
name: {yaml_name}
alias: {yaml_alias}
role: {yaml_role}
description: {yaml_description}
tools: {", ".join(tools)}{tier_line}
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


def normalize_tier(tier: str) -> str:
    """Tier ids are underscore-separated everywhere (hyphen input is accepted)."""
    return (tier or "inherit").strip().lower().replace("-", "_")


def known_tiers(content: str) -> List[str]:
    try:
        import yaml
        data = yaml.safe_load(content) or {}
        tiers = (data.get("functional_envelope") or {}).get("tiers") or {}
        return [normalize_tier(t) for t in tiers]
    except ImportError:
        return []
    except (ValueError, AttributeError, TypeError, yaml.YAMLError) as exc:
        print(f"warning: could not parse tiers from registry: {exc}", file=sys.stderr)
        return []


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError as exc:
                print(f"warning: could not remove temp file {tmp}: {exc}", file=sys.stderr)


@contextmanager
def scaffold_lock(root: Path, timeout: float = 30.0, stale_after: float = 60.0):
    """Cross-platform lockfile (O_CREAT|O_EXCL); stale locks are broken by age."""
    lock = Path(root) / ".scaffold.lock"
    deadline = time.time() + timeout
    fd = None
    while fd is None:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_after:
                    lock.unlink()
                    continue
            except OSError:
                continue
            if time.time() > deadline:
                raise OSError(f"timed out waiting for scaffold lock {lock}")
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass  # already broken as stale by another process
        except OSError as exc:
            print(f"warning: could not remove lock {lock}: {exc}", file=sys.stderr)


def add_to_tier(content: str, tier: str, registry_key: str) -> str:
    pattern = re.compile(
        rf"(^    {re.escape(tier)}:[ \t]*\n(?:      .*\n)*?      operatives: \[)([^\]]*)(\])", re.MULTILINE
    )
    match = pattern.search(content)
    if not match:
        raise ValueError(f"registry tier '{tier}' has no operatives list")
    items = match.group(2).strip()
    entry = json.dumps(registry_key)
    new_items = f"{items}, {entry}" if items else entry
    return content[:match.start(2)] + new_items + content[match.end(2):]


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
    validate_bot_name(name)
    registry_key = name.replace('-', '_')
    model_tier = normalize_tier(model_tier)
    content = registry_path.read_text(encoding="utf-8")
    if model_tier != "inherit" and model_tier not in known_tiers(content):
        raise ValueError(f"unknown model tier '{model_tier}'; use inherit or one of: {', '.join(known_tiers(content)) or 'none defined'}")
    if re.search(rf"^  {re.escape(registry_key)}:\s*$", content, re.MULTILINE):
        raise ValueError(f"registry already contains bot '{name}'")
    entry_lines = [
        f"\n  {registry_key}:",
        f"    name: {json.dumps(name)}",
        f"    alias: {json.dumps(alias)}",
        f"    role: {json.dumps(role)}",
        f"    job_to_be_done: {json.dumps(jtbd)}",
        f"    model_tier: {json.dumps(model_tier)}",
        "    allowed_tools:",
    ]
    for t in tools:
        entry_lines.append(f"      - {json.dumps(t)}")
    entry_lines.append(f"    verification_gate: {json.dumps(verification)}")

    if model_tier != "inherit":
        content = add_to_tier(content, model_tier, registry_key)
    if not content.endswith("\n"):
        content += "\n"
    content += "\n".join(entry_lines) + "\n"
    atomic_write(registry_path, content)


def add_route(routing_path: Path, name: str, alias: str) -> None:
    """Append a minimal route so the new bot is routable by name."""
    content = routing_path.read_text(encoding="utf-8")
    if re.search(rf"^    owner: {re.escape(name)}\s*$", content, re.MULTILINE):
        raise ValueError(f"routing already contains owner '{name}'")
    first = alias.split("(")[0].strip().lower()
    keywords = list(dict.fromkeys([name, first] if first else [name]))
    block = (
        f"  - intent: {name.replace('-', '_')}\n"
        f"    owner: {name}\n"
        f"    strong_keywords: [{', '.join(json.dumps(k) for k in keywords)}]\n"
        f"    keywords: [{', '.join(json.dumps(k) for k in keywords)}]\n"
        f"    handoff: [{name}, trunks]\n"
    )
    atomic_write(routing_path, content.rstrip("\n") + "\n" + block)


def scaffold_bot(
    root: Path,
    name: str,
    alias: str,
    role: str,
    description: str,
    jtbd: str,
    boundaries: str,
    tools: List[str],
    verification: str,
    model_tier: str = "inherit",
) -> List[Path]:
    """Create persona, .claude/agents file, registry entry (+tier) and route as one unit.

    Any failure restores every touched file. Raises ValueError/OSError.
    """
    validate_bot_name(name)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with scaffold_lock(root):
        return _scaffold_locked(root, name, alias, role, description, jtbd, boundaries, tools, verification, model_tier)


def _scaffold_locked(root, name, alias, role, description, jtbd, boundaries, tools, verification, model_tier):
    bot_file = root / "bots" / (name.replace("-", "_") + ".md")
    agent_file = root / ".claude" / "agents" / (name + ".md")
    registry_file = root / "registry.yaml"
    routing_file = root / "config" / "routing.yaml"
    for existing in (bot_file, agent_file):
        if existing.exists():
            raise ValueError(f"{existing} already exists; refusing to overwrite")

    model_tier = normalize_tier(model_tier)
    alias = clean_line(alias, 120)
    role = clean_line(role, 120)
    description = clean_line(description, 300)
    jtbd = clean_line(jtbd, 400)
    verification = clean_line(verification, 300)
    tools = canonical_tools(tools)
    check_routing_collisions(routing_file, name, alias)
    if model_tier != "inherit":
        if not TIER_PATTERN.fullmatch(model_tier):
            raise ValueError(f"invalid model tier '{model_tier}'")
        if registry_file.exists():
            tiers = known_tiers(registry_file.read_text(encoding="utf-8"))
            if model_tier not in tiers:
                raise ValueError(f"unknown model tier '{model_tier}'; use inherit or one of: {', '.join(tiers) or 'none defined'}")
    markdown = generate_bot_markdown(
        name=name, alias=alias, role=role, description=description, jtbd=jtbd,
        boundaries=boundaries, tools=tools, verification=verification, model_tier=model_tier,
    )
    snapshots = {p: p.read_text(encoding="utf-8") for p in (registry_file, routing_file) if p.exists()}
    created: List[Path] = []
    try:
        bot_file.parent.mkdir(parents=True, exist_ok=True)
        bot_file.write_text(markdown, encoding="utf-8")
        created.append(bot_file)
        agent_file.parent.mkdir(parents=True, exist_ok=True)
        agent_file.write_text(markdown, encoding="utf-8")
        created.append(agent_file)
        if registry_file.exists():
            update_registry_yaml(registry_file, name, alias, role, jtbd, tools, verification, model_tier)
        if routing_file.exists():
            add_route(routing_file, name, alias)
    except (OSError, ValueError):
        for path in created:
            try:
                path.unlink()
            except OSError as exc:
                print(f"warning: rollback cleanup failed for {path}: {exc}", file=sys.stderr)
        for path, text in snapshots.items():
            try:
                atomic_write(path, text)
            except OSError as exc:
                print(f"warning: rollback cleanup failed for {path}: {exc}", file=sys.stderr)
        raise
    return created + list(snapshots)


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
    parser.add_argument("--model-tier", default="inherit", help="Model tier id (inherit or a tier in registry functional_envelope; hyphens accepted)")
    parser.add_argument("--list-archetypes", action="store_true", help="List predefined Dragon Ball Z character archetypes ready for use")
    parser.add_argument("--from-archetype", help="Scaffold a bot directly from a predefined DBZ archetype (e.g. gohan, krillin)")

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

    try:
        validate_bot_name(name)
    except ValueError as exc:
        print(f"Error: invalid bot name '{name}': {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        scaffold_bot(capsule_dir, name, alias, role, description, jtbd, boundaries, tools, verification, model_tier)
    except (OSError, ValueError) as exc:
        print(f"Error: could not scaffold bot '{name}': {exc}", file=sys.stderr)
        sys.exit(1)
    print(f" Bot persona created in {bots_dir} and .claude/agents; registry and routing updated")


if __name__ == "__main__":
    main()
