"""Resolve Capsule Corp model tiers to concrete model names.

Precedence, highest first:
  1. explicit ``--model`` flag
  2. env ``CAPSULE_MODEL``, then ``CAPSULE_MODEL_<TIER>`` (FLASH / PRO / PREMIUM)
  3. per-bot override (``bots:`` in config/models.yaml)
  4. tier default (``tiers:`` in config/models.yaml, else built-in fallback)

Per-task downshift/escalation (see ``route_tier``): small fixes run flash,
complex epics keep the coordinator's registry tier, and premium is used only on
explicit request (``--tier premium`` / ``--escalate``).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_TIERS: Dict[str, str] = {"flash": "haiku", "pro": "sonnet", "premium": "opus"}
KNOWN_TIERS = tuple(DEFAULT_TIERS)
DEFAULT_TIER = "pro"  # registry tier "inherit"/missing resolves here
_MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]*")  # use fullmatch: `$` would accept a trailing newline
MAX_MODEL_LEN = 128
TIER_ORDER = {"flash": 0, "pro": 1, "premium": 2}
# Bots whose work must never run below their registry tier, whatever the task size.
PROTECTED_BOTS = ("android-17", "cell", "beerus")
# Word-start stems (match with any word suffix) and whole words (optional plural/-ed/-ing); never mid-word.
SECURITY_STEMS = ("secur", "vuln", "secret", "leak", "inject", "authenticat", "authoriz", "password", "passwd",
                  "token", "crypto", "exploit", "privilege", "overflow", "bypass", "deserializ", "session",
                  "cookie", "encrypt", "decrypt", "sanitiz", "credential", "sqli", "oauth", "traversal", "pentest", "fuzz")
SECURITY_WORDS = ("xss", "csrf", "ssrf", "rce", "jwt", "cors", "auth", "authn", "authz", "hash", "cve", "sso", "tls")
SECURITY_KEYWORDS = SECURITY_STEMS + SECURITY_WORDS
_SECURITY_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:(?:" + "|".join(SECURITY_STEMS) + r")[A-Za-z]*|(?:" + "|".join(SECURITY_WORDS)
    + r")(?:s|es|ed|ing)?(?![A-Za-z]))|cve-\d{4}-\d+|(?<![A-Za-z0-9])pen[ -]test|(?<![A-Za-z0-9])penetration", re.IGNORECASE)

TEMPLATE = """# Capsule Corp model tier mapping.
# Precedence (highest first): --model flag > CAPSULE_MODEL > CAPSULE_MODEL_<TIER>
#   > per-bot override (bots:) > tier default (tiers:)
tiers:
  flash: haiku
  pro: sonnet
  premium: opus
bots: {}
"""


class ModelsError(Exception):
    """User-facing error (exit code 2)."""


try:
    from scripts.sanitize import cap as _cap, scrub as _scrub
except ImportError:  # run as a bare script/module from scripts/
    from sanitize import cap as _cap, scrub as _scrub  # type: ignore


def sanitize_text(value, limit=None) -> str:
    """Shared sanitizer (scripts/sanitize.py): ANSI, controls and invisible/format chars removed, capped."""
    return _cap(_scrub(value), limit)


def validate_model_name(value, what: str = "model") -> str:
    """Return ``value`` if it is a safe model name, else raise ModelsError (message is sanitized)."""
    if not isinstance(value, str) or len(value) > MAX_MODEL_LEN or not _MODEL_RE.fullmatch(value):
        shown = sanitize_text(value, 40) if isinstance(value, str) else type(value).__name__
        raise ModelsError(f"invalid {what} {shown!r}: must match [A-Za-z0-9][A-Za-z0-9._:/[]-]* (no leading '-', whitespace or control chars)")
    return value


def capsule_root() -> Path:
    return Path(os.environ.get("CAPSULE_RESOURCE_ROOT", Path(__file__).resolve().parent.parent)).resolve()


def config_path(root: Optional[Path] = None) -> Path:
    return (root or capsule_root()) / "config" / "models.yaml"


def norm_bot(name: str) -> str:
    return str(name).strip().lower().replace("_", "-")


def _strip_comment(line: str) -> str:
    """Drop a YAML comment: `#` outside quotes and at line start or after whitespace."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"" and (i == 0 or line[i - 1] in " \t:[{,"):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _unquote(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
        return val[1:-1]
    return val


def _mini_parse(text: str) -> Dict:
    """Two-level `section:` / `  key: value` parser used when PyYAML is absent."""
    data: Dict = {}
    section = None
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            key, _, val = line.partition(":")
            val = val.strip()
            if val in ("", "{}"):
                data[key.strip()] = {}
                section = key.strip()
            else:
                data[key.strip()] = _unquote(val)
                section = None
        elif section is not None:
            key, _, val = line.strip().partition(":")
            data[section][key.strip()] = _unquote(val)
    return data


def _parse(text: str):
    try:
        import yaml
    except ImportError:
        return _mini_parse(text)
    return yaml.safe_load(text)


def load_config(root: Optional[Path] = None) -> Tuple[Dict, List[str]]:
    """Return ({'tiers': {...}, 'bots': {...}}, warnings). Never raises."""
    cfg = {"tiers": dict(DEFAULT_TIERS), "bots": {}}
    warnings: List[str] = []
    path = config_path(root)
    if not path.exists():
        return cfg, warnings
    try:
        data = _parse(path.read_text(encoding="utf-8"))
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError("root must be a mapping")
        for section in ("tiers", "bots"):
            if data.get(section) is not None and not isinstance(data[section], dict):
                raise ValueError(f"'{section}' must be a mapping")
    except Exception as exc:  # bad config must never traceback
        warnings.append(f"warning: {path} is invalid ({exc}); using built-in defaults")
        return cfg, warnings
    for tier, model in (data.get("tiers") or {}).items():
        if isinstance(model, str) and _MODEL_RE.fullmatch(model):
            cfg["tiers"][str(tier).lower()] = model
        else:
            warnings.append(f"warning: ignoring invalid model for tier '{tier}' in {path}")
    for bot, model in (data.get("bots") or {}).items():
        if isinstance(model, str) and _MODEL_RE.fullmatch(model):
            cfg["bots"][norm_bot(bot)] = model
        else:
            warnings.append(f"warning: ignoring invalid model for bot '{bot}' in {path}")
    return cfg, warnings


def _mini_registry_tiers(text: str) -> Dict[str, str]:
    """Line scanner for registry.yaml `bots:` entries (key at 2 spaces, name/model_tier at 4)."""
    out: Dict[str, str] = {}
    in_bots, key, name, tier = False, None, None, "inherit"

    def flush():
        if key is not None:
            out[norm_bot(name or key)] = tier.lower()

    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            flush()
            key = None
            in_bots = line.split(":", 1)[0].strip() == "bots"
            continue
        if not in_bots:
            continue
        m = re.match(r"^  ([\w.-]+):\s*$", line)
        if m:
            flush()
            key, name, tier = m.group(1), None, "inherit"
            continue
        m = re.match(r"^    (name|model_tier):\s*(.*)$", line)
        if m and key is not None:
            if m.group(1) == "name":
                name = _unquote(m.group(2))
            else:
                tier = _unquote(m.group(2))
    flush()
    return out


def registry_tiers(root: Optional[Path] = None) -> Dict[str, str]:
    """Bot id (hyphenated) -> registry model_tier. Empty only if the registry file is unreadable.

    Works without PyYAML via a small line scanner so ``resolve_model(bot=...)`` keeps working.
    """
    try:
        text = ((root or capsule_root()) / "registry.yaml").read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        import yaml
    except ImportError:
        return _mini_registry_tiers(text)
    try:
        data = yaml.safe_load(text)
        bots = data.get("bots", {}) if isinstance(data, dict) else {}
        out = {}
        for key, d in bots.items():
            if isinstance(d, dict):
                out[norm_bot(d.get("name", key))] = str(d.get("model_tier", "inherit")).lower()
        return out
    except Exception:
        return {}


def bot_tier(bot: str, root: Optional[Path] = None) -> str:
    tier = registry_tiers(root).get(norm_bot(bot), DEFAULT_TIER)
    return tier if tier in KNOWN_TIERS else DEFAULT_TIER


def resolve_model(
    bot: Optional[str] = None,
    tier: Optional[str] = None,
    cli_model: Optional[str] = None,
    root: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    config: Optional[Dict] = None,
) -> Dict[str, str]:
    """Resolve to {'bot','tier','model','source'}. Raises ModelsError on unknown tier/bot."""
    env = os.environ if env is None else env
    if config is None:
        config, _ = load_config(root)
    if tier is not None:
        tier = tier.lower()
        if tier not in KNOWN_TIERS:
            raise ModelsError(f"unknown tier '{sanitize_text(tier, 40)}'; use one of: {', '.join(KNOWN_TIERS)}")
    bot_key = None
    if bot:
        bot_key = norm_bot(bot)
        if bot_key not in registry_tiers(root):
            raise ModelsError(f"unknown bot '{sanitize_text(bot, 40)}'; run `capsule list` for registered bots")
    if tier is None:
        tier = bot_tier(bot_key, root) if bot_key else DEFAULT_TIER

    base = {"bot": bot_key or "", "tier": tier}
    if cli_model:
        return dict(base, model=validate_model_name(cli_model, "--model"), source="cli:--model")
    if env.get("CAPSULE_MODEL"):
        return dict(base, model=validate_model_name(env["CAPSULE_MODEL"], "CAPSULE_MODEL"), source="env:CAPSULE_MODEL")
    tier_var = f"CAPSULE_MODEL_{tier.upper()}"
    if env.get(tier_var):
        return dict(base, model=validate_model_name(env[tier_var], tier_var), source=f"env:{tier_var}")
    if bot_key and bot_key in config["bots"]:
        return dict(base, model=config["bots"][bot_key], source=f"config:bots.{bot_key}")
    if tier in config["tiers"]:
        return dict(base, model=config["tiers"][tier], source=f"config:tiers.{tier}")
    return dict(base, model=DEFAULT_TIERS[tier], source=f"default:{tier}")


def route_tier(workflow_tier: str, coordinator_tier: str, tier: Optional[str] = None, escalate: bool = False,
               request: str = "") -> Tuple[Optional[str], str]:
    """Pick the tier for a routed task. Returns (tier or None for owner's registry tier, reason).

    Rule: explicit ``--tier``/``--escalate`` (premium) wins; small_fix downshifts to
    flash; complex_epic keeps the coordinator's registry tier; otherwise the owner's
    registry tier applies. Premium is never chosen implicitly.
    """
    if tier:
        return tier, "explicit --tier"
    if escalate:
        return "premium", "escalated"
    if workflow_tier == "small_fix" and has_security_keyword(request):
        return None, "small_fix downshift skipped: security term in request"
    if workflow_tier == "small_fix":
        return "flash", "small_fix downshift"
    if workflow_tier == "complex_epic":
        return coordinator_tier, "complex_epic coordinator tier"
    return None, "registry tier"


def has_security_keyword(request: str) -> bool:
    return bool(_SECURITY_RE.search(request or ""))


def guard_tier(bot: str, tier: str, request: str = "", root: Optional[Path] = None) -> Tuple[str, Optional[str]]:
    """Raise a downshifted ``tier`` back to the safe floor. Returns (tier, reason or None).

    Floor: protected bots (android-17, cell, beerus) never go below their registry
    tier; a security keyword in the request keeps every hop off flash (floor: pro).
    """
    tier = str(tier).lower()
    if tier not in TIER_ORDER:
        raise ModelsError(f"unknown tier '{sanitize_text(tier, 40)}'; use one of: {', '.join(KNOWN_TIERS)}")
    floor = "flash"
    why = None
    if norm_bot(bot) in PROTECTED_BOTS:
        floor, why = bot_tier(bot, root), f"{norm_bot(bot)} never runs below its registry tier"
    if has_security_keyword(request) and TIER_ORDER[floor] < TIER_ORDER[DEFAULT_TIER]:
        floor, why = DEFAULT_TIER, "security keyword in request keeps routes off flash"
    if TIER_ORDER[tier] < TIER_ORDER[floor]:
        return floor, why
    return tier, None


def model_rank(model: str, cfg: Dict) -> Optional[int]:
    """Tier rank of a model name (exact tier mapping, else family name haiku/sonnet/opus); None if unknown."""
    low = model.lower()
    for tier, name in cfg["tiers"].items():
        if tier in TIER_ORDER and str(name).lower() == low:
            return TIER_ORDER[tier]
    for tier, name in DEFAULT_TIERS.items():
        if name in low:
            return TIER_ORDER[tier]
    return None


def check_protected_downgrade(bot: str, model: str, root: Optional[Path] = None) -> None:
    """Raise ModelsError if ``model`` is below (or cannot be verified against) a protected bot's registry tier."""
    key = norm_bot(bot)
    if key not in PROTECTED_BOTS:
        return
    cfg, _ = load_config(root)
    floor = bot_tier(key, root)
    rank = model_rank(model, cfg)
    if rank is None:
        why = f"cannot verify '{model}' is at or above its registry tier '{floor}'"
    elif rank < TIER_ORDER[floor]:
        why = f"'{model}' is below its registry tier '{floor}'"
    else:
        return
    raise ModelsError(f"{key} is a protected bot and {why}; pass --force to downgrade it anyway")


def protected_downgrade_warning(bot: str, model: str, root: Optional[Path] = None, source: str = "") -> Optional[str]:
    """Warning text if a protected bot resolves to a model below (or unverifiable against) its registry tier."""
    key = norm_bot(bot)
    if key not in PROTECTED_BOTS:
        return None
    cfg, _ = load_config(root)
    floor = bot_tier(key, root)
    rank = model_rank(model, cfg)
    if rank is not None and rank >= TIER_ORDER[floor]:
        return None
    how = "is flash-class or below" if rank is not None else "cannot be verified against"
    src = f" via {source}" if source else ""
    return (f"WARN: {key} is a protected bot (registry tier {floor}) and resolves to '{sanitize_text(model, 60)}'{src}, "
            f"which {how} that tier (possible downgrade)")


def list_bots(root: Optional[Path] = None) -> List[Dict[str, str]]:
    """Registered bots with registry tier and resolved model (for `capsule list --json`)."""
    cfg, _ = load_config(root)
    out = []
    for bot, tier in registry_tiers(root).items():
        res = resolve_model(bot=bot, root=root, config=cfg)
        out.append({"bot": bot, "tier": tier, "model": res["model"], "source": res["source"]})
    return out


def bot_view(bot: str, root: Optional[Path] = None) -> Dict[str, str]:
    """Per-bot view: registry tier, that tier's configured model, resolved model and its source."""
    cfg, _ = load_config(root)
    res = resolve_model(bot=bot, root=root, config=cfg)
    tier = res["tier"]
    registry_model = cfg["tiers"].get(tier, DEFAULT_TIERS[tier])
    view = {"bot": res["bot"], "tier": tier, "registry_model": registry_model,
            "model": res["model"], "source": res["source"], "protected": res["bot"] in PROTECTED_BOTS}
    warn = protected_downgrade_warning(res["bot"], res["model"], root, res["source"])
    if warn:
        view["warning"] = warn
    return view


def _set_in_text(text: str, section: str, key: str, value: str) -> str:
    lines = text.splitlines()
    head = None
    for i, ln in enumerate(lines):
        if re.match(rf"^{re.escape(section)}:\s*(\{{\}})?\s*(#.*)?$", ln):
            head = i
            break
    if head is None:
        return text.rstrip("\n") + f"\n{section}:\n  {key}: {value}\n"
    lines[head] = f"{section}:"
    end = head + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith((" ", "\t", "#"))):
        end += 1
    last = head
    for j in range(head + 1, end):
        if re.match(rf"^\s+{re.escape(key)}:", lines[j]):
            lines[j] = f"  {key}: {value}"
            return "\n".join(lines) + "\n"
        if lines[j].strip() and not lines[j].lstrip().startswith("#"):
            last = j
    lines.insert(last + 1, f"  {key}: {value}")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file in the same directory + os.replace; keeps the existing file mode."""
    import tempfile
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(prefix=".models-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError as exc:
            print(f"WARN: could not remove temp file {tmp}: {exc}", file=sys.stderr)
        raise


def _log_change(path: Path, section: str, key: str, old, new: str, force: bool) -> None:
    """Append one line to models-changes.log beside the config (O_APPEND, single write). Never fails the set."""
    import time
    log = path.parent / "models-changes.log"
    try:
        if log.is_symlink():
            raise OSError(f"refusing to log through a symlink: {log}")
        who = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
        line = "%s user=%s set %s.%s %s -> %s%s\n" % (
            time.strftime("%Y-%m-%dT%H:%M:%S%z"), sanitize_text(who, 40), section, key,
            sanitize_text(old, 128) if old is not None else "(unset)", sanitize_text(new, 128), " force=1" if force else "")
        fd = os.open(str(log), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as exc:
        print(f"WARN: could not log model change: {sanitize_text(exc, 200)}", file=sys.stderr)


def set_model(target: str, model: str, is_bot: bool = False, force: bool = False, root: Optional[Path] = None) -> str:
    """Write a tier/bot mapping, preserving other file content. Returns a status message."""
    validate_model_name(model)
    if is_bot:
        key = norm_bot(target)
        if key not in registry_tiers(root):
            raise ModelsError(f"unknown bot '{sanitize_text(target, 40)}'; run `capsule list` for registered bots")
        section = "bots"
        if not force:
            check_protected_downgrade(key, model, root)
    else:
        key = target.lower()
        if key not in KNOWN_TIERS:
            raise ModelsError(f"unknown tier '{sanitize_text(target, 40)}'; use one of: {', '.join(KNOWN_TIERS)}")
        section = "tiers"
    path = config_path(root)
    if path.is_symlink() or path.parent.is_symlink():
        raise ModelsError(f"refusing to write through a symlink: {path}")
    text = path.read_text(encoding="utf-8") if path.exists() else TEMPLATE
    try:
        existing = (_parse(text) or {}).get(section) or {}
    except Exception as exc:
        raise ModelsError(f"{path} is invalid ({exc}); fix it before using `models set`")
    current = existing.get(key) if isinstance(existing, dict) else None
    if current is not None and str(current) != model and not force:
        raise ModelsError(f"{section}.{key} is already '{current}'; pass --force to overwrite")
    if current is not None and str(current) == model:
        return f"{section}.{key} already {model}"
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, _set_in_text(text, section, key, model))
    msg = f"{section}.{key} = {model} ({path})"
    _log_change(path, section, key, current, model, force)
    if is_bot:
        warn = protected_downgrade_warning(key, model, root, f"config:bots.{key}")
        if warn:
            msg += "\n" + warn
    elif key in KNOWN_TIERS:
        for bot in PROTECTED_BOTS:
            if bot_tier(bot, root) == key:
                warn = protected_downgrade_warning(bot, model, root, f"config:tiers.{key}")
                if warn:
                    msg += "\n" + warn
    return msg


def show(root: Optional[Path] = None, as_json: bool = False) -> int:
    cfg, warnings = load_config(root)
    for w in warnings:
        print(w, file=sys.stderr)
    env_active = {sanitize_text(k, 64): sanitize_text(v, 128) for k, v in os.environ.items()
                  if k == "CAPSULE_MODEL" or k.startswith("CAPSULE_MODEL_")}
    if as_json:
        print(json.dumps({"tiers": cfg["tiers"], "bots": cfg["bots"], "env": env_active}, indent=2))
        return 0
    print(f"Model tiers ({config_path(root)}):")
    for tier in KNOWN_TIERS + tuple(t for t in cfg["tiers"] if t not in KNOWN_TIERS):
        print(f"  {tier:<8} -> {cfg['tiers'].get(tier, DEFAULT_TIERS.get(tier, '?'))}")
    if cfg["bots"]:
        print("Per-bot overrides:")
        for bot, model in sorted(cfg["bots"].items()):
            print(f"  {bot:<14} -> {model}")
    if env_active:
        print("Active env overrides:")
        for k, v in sorted(env_active.items()):
            print(f"  {k}={v}")
    print("Precedence: --model > CAPSULE_MODEL > CAPSULE_MODEL_<TIER> > per-bot override > tier default")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="capsule models", description="Show or set tier-to-model mapping")
    sub = parser.add_subparsers(dest="action")
    p_show = sub.add_parser("show", help="Show mapping (default)")
    p_show.add_argument("--json", action="store_true")
    p_set = sub.add_parser("set", help="Set a tier's (or --bot's) model")
    p_set.add_argument("target", help="tier (flash|pro|premium), or bot id with --bot")
    p_set.add_argument("model")
    p_set.add_argument("--bot", action="store_true", help="treat target as a bot id (per-bot override)")
    p_set.add_argument("--force", action="store_true", help="overwrite an existing different value")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--bot", dest="bot_view", metavar="BOT", help="show tier, registry model, resolved model and source for one bot")
    p_show.add_argument("--bot", dest="bot_view", metavar="BOT", help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    try:
        if args.action == "set":
            print(set_model(args.target, args.model, args.bot, args.force))
            return 0
        if getattr(args, "bot_view", None):
            view = bot_view(args.bot_view)
            if args.json or getattr(args, "json", False):
                print(json.dumps(view, indent=2))
            else:
                print(f"Bot: {view['bot']}" + (" (protected)" if view["protected"] else ""))
                print(f"  tier:           {view['tier']}")
                print(f"  registry model: {view['registry_model']}")
                print(f"  resolved model: {view['model']}")
                print(f"  source:         {view['source']}")
            return 0
        return show(as_json=getattr(args, "json", False))
    except ModelsError as exc:
        print(f"Error: {sanitize_text(exc, 300)}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {sanitize_text(exc, 300)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
