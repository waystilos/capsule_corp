"""Deterministically route a request to the safest Capsule Corp owner."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CAPSULE_ROOT = Path(os.environ.get("CAPSULE_RESOURCE_ROOT", Path(__file__).resolve().parent.parent)).resolve()


def load_routes() -> Dict:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required for capsule route") from exc

    path = CAPSULE_ROOT / "config" / "routing.yaml"
    if not path.exists():
        raise RuntimeError(f"Routing policy not found at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("routes"), list):
        raise RuntimeError("Routing policy is invalid")
    return data


STRONG_WEIGHT = 3


def score_request(request: str, route: Dict) -> Tuple[int, List[str]]:
    text = request.casefold()
    matched = []
    score = 0
    for keyword in route.get("strong_keywords", []):
        if re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", text):
            matched.append(keyword)
            score += STRONG_WEIGHT
    for keyword in route.get("keywords", []):
        if keyword in matched:
            continue
        if re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", text):
            matched.append(keyword)
            score += 1
    for keyword in route.get("avoid", []):
        if re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", text):
            score -= 2
    return score, matched


BOT_TO_ROLE: Dict[str, str] = {
    "bulma": "Product",
    "goku": "Builder",
    "trunks": "Reviewer",
    "piccolo": "Coordinator",
    "whis": "Coordinator (Triage)",
    "android-17": "Security Specialist",
    "android-18": "Refactoring Specialist",
    "videl": "UX Specialist",
    "vegeta": "Infrastructure Specialist",
    "roshi": "Game Specialist",
    "dr-gero": "Meta-Agent Architect",
    "king-kai": "Agent Drift Overseer",
    "hercule": "Market Reality & Hype Auditor",
    "zarbon": "Aesthetic & Polish Specialist",
    "cell": "Red Team & Adversarial Chaos",
    "beerus": "Architectural Inquisitor & Code Griller",
    "goten": "Sprite Animation Specialist",
    "android-16": "Rive Rig Integration Specialist",
}


COORDINATORS = ("piccolo", "whis")
VERIFICATION_STEP = "Verification (capsule check)"

WORKFLOW_ROLE: Dict[str, str] = {
    "bulma": "Product",
    "goku": "Builder",
    "trunks": "Reviewer",
    "piccolo": "Coordinator",
    "whis": "Coordinator",
    "android-17": "Security",
    "android-18": "Refactoring",
    "videl": "UX",
    "vegeta": "Infra",
    "roshi": "Game",
    "dr-gero": "Meta-Agent",
    "king-kai": "Watchdog",
    "hercule": "Hype Auditor",
    "zarbon": "Polish",
    "cell": "Red Team",
    "beerus": "Inquisitor",
    "goten": "Animation",
    "android-16": "Rig Integration",
}


def registry_roles() -> Dict[str, str]:
    """Roles of registry bots (e.g. scaffolded ones), keyed by hyphenated bot id."""
    try:
        import yaml
        data = yaml.safe_load((CAPSULE_ROOT / "registry.yaml").read_text(encoding="utf-8"))
        bots = data.get("bots", {}) if isinstance(data, dict) else {}
        return {
            str(d.get("name", key)): str(d["role"])
            for key, d in bots.items()
            if isinstance(d, dict) and d.get("role")
        }
    except (ImportError, OSError, ValueError, AttributeError):
        return {}
    except Exception:  # malformed registry must never break routing
        return {}


def bot_role(bot: str) -> str:
    return BOT_TO_ROLE.get(bot) or registry_roles().get(bot, "Specialist")


def workflow_label(bot: str) -> str:
    display = "-".join(part.capitalize() for part in bot.split("-"))
    role = WORKFLOW_ROLE.get(bot) or registry_roles().get(bot, "Specialist")
    return f"{role} (@{display})"


# A strong signal alone makes an epic; weak signals need two distinct hits ("fix typo in the system" is not an epic).
STRONG_COMPLEX_KEYWORDS = ["epic", "orchestrate", "deconstruct", "multi-agent"]
WEAK_COMPLEX_KEYWORDS = ["architecture", "redesign", "migrate", "system"]
COMPLEX_KEYWORDS = STRONG_COMPLEX_KEYWORDS + WEAK_COMPLEX_KEYWORDS


def is_complex(request: str) -> bool:
    text = (request or "").casefold()

    def hit(kw: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text) is not None

    return any(hit(k) for k in STRONG_COMPLEX_KEYWORDS) or sum(hit(k) for k in WEAK_COMPLEX_KEYWORDS) >= 2


def determine_workflow(request: str, owner: str, handoff: Optional[List[str]] = None) -> Tuple[str, List[str], List[str]]:
    """Pick a workflow tier, then build the chain from the route's own handoff list.

    Only the bots named in the matched route's handoff take part. Coordinators are
    added for epics, Product is added only for Builder-owned standard features, and
    nothing else is widened. This keeps specialist work from cycling through the
    whole cohort.
    """
    text = request.casefold()
    small_fix_kws = ["fix", "bug", "typo", "tweak", "patch", "quick", "style", "css", "align", "rename"]

    def has_any(keywords: List[str]) -> bool:
        return any(re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text) for kw in keywords)

    chain = list(dict.fromkeys([owner] + list(handoff or [])))

    if is_complex(request) or owner in COORDINATORS:
        tier = "complex_epic"
        coordinator = owner if owner in COORDINATORS else next((b for b in chain if b in COORDINATORS), "piccolo")
        workers = [b for b in chain if b not in COORDINATORS]
        if not workers:
            workers = ["goku", "trunks"]
        chain = [coordinator] + workers
    elif has_any(small_fix_kws):
        tier = "small_fix"
        # Product and coordinators are dropped; the reviewer stays so verification is never skipped silently.
        chain = [b for b in chain if b not in COORDINATORS and b != "bulma"] or [owner]
    else:
        tier = "standard_feature"
        if owner == "goku" and "bulma" not in chain:
            chain = ["bulma"] + chain

    return tier, [workflow_label(b) for b in chain] + [VERIFICATION_STEP], chain


def _envelope():
    try:
        from scripts import envelope
    except ImportError:
        import envelope  # type: ignore
    return envelope


def _seed(request: str, entry: List[str]) -> Dict:
    """Router-seeded envelope fields (see scripts/envelope.py) plus the caller-supplied entry fields."""
    env = _envelope().Envelope.new(request)
    payload = env.to_dict()
    payload["entry_required"] = list(entry)
    return payload


def route_request(request: str) -> Dict:
    raw_request = request
    request = _envelope().sanitize_text(request, keep_newlines=True)  # score on what the envelope will keep
    result = _route_sanitized(request)
    if request != raw_request:
        result["sanitized"] = True  # root_request differs from the literal input (invisible chars/controls removed)
    return result


def _route_sanitized(request: str) -> Dict:
    policy = load_routes()
    ranked = []
    for route in policy["routes"]:
        score, matched = score_request(request, route)
        ranked.append((score, route, matched))
    offensive = any(r["owner"] in ("cell", "beerus") and sc > 0 for sc, r, _ in ranked)
    if not offensive and _models().has_security_keyword(request):
        # security terms break ties against generic implementation words (fix/bug/code)
        ranked = [(sc + 1 if sc > 0 and r.get("intent") == "security" else sc, r, mt) for sc, r, mt in ranked]
    ranked.sort(key=lambda item: item[0], reverse=True)

    best_score, best_route, matched = ranked[0]
    tied = len(ranked) > 1 and best_score == ranked[1][0]
    if best_score <= 0 or tied:
        fallback_owner = policy["fallback"]
        # Only the coordinator acts until the request is clarified: chain == handoff == [owner].
        tier = "complex_epic" if is_complex(request) else "triage"
        return {
            **_seed(request, []),
            "status": "needs_clarification",
            "owner": fallback_owner,
            "role": bot_role(fallback_owner),
            "intent": "triage",
            "reason": "No single route matched with confidence; Whis must clarify before dispatch.",
            "handoff": [fallback_owner],
            "matches": matched,
            "workflow_tier": tier,
            "suggested_workflow": [workflow_label(fallback_owner)],
            "is_suggestion": True,
        }

    owner = best_route["owner"]
    tier, workflow, chain = determine_workflow(request, owner, best_route["handoff"])
    return {
        **_seed(request, best_route.get("entry") or []),
        "status": "routed",
        "owner": owner,
        "role": bot_role(owner),
        "intent": best_route["intent"],
        "reason": f"Matched: {', '.join(matched)}.",
        "handoff": chain,
        "matches": matched,
        "workflow_tier": tier,
        "suggested_workflow": workflow,
        "is_suggestion": True,
    }


def _models():
    try:
        from scripts import models
    except ImportError:
        import models  # type: ignore
    return models


ROUTE_WIDE_REASONS = ("small_fix downshift", "explicit --tier", "escalated")


def attach_model(result: Dict, cli_model: Optional[str] = None, tier: Optional[str] = None, escalate: bool = False) -> Dict:
    """Add model fields to a route result, plus per-hop models and safety warnings.

    Top-level model/model_tier/model_source describe the owner (see models.route_tier).
    Every hop gets its own resolve_model(bot=...) result; downshifts are guarded by
    models.guard_tier so android-17/cell/beerus and security requests never run on flash.
    """
    m = _models()
    owner = result["owner"]
    request = result.get("root_request", "")
    coordinator_tier = m.bot_tier(result["handoff"][0]) if result["handoff"] else m.DEFAULT_TIER
    chosen, why = m.route_tier(result.get("workflow_tier", ""), coordinator_tier, tier, escalate, request)
    warnings: List[str] = []
    override_warnings: List[str] = []

    def resolve(bot: str):
        registry_tier = m.bot_tier(bot)
        wide = why in ROUTE_WIDE_REASONS
        requested = chosen if (chosen and (bot == owner or wide)) else registry_tier
        final, guard_why = m.guard_tier(bot, requested, request)
        res = m.resolve_model(bot=bot, tier=final, cli_model=cli_model)
        if guard_why:
            warnings.append(f"{bot}: tier raised {requested} -> {final}: {guard_why}")
        if res["source"].startswith("env:") and (final != registry_tier or guard_why or bot in m.PROTECTED_BOTS):
            warnings.append(
                f"{bot}: {res['source'][4:]} overrides the tier-{final} model (downshift/guard rules do not vet env model names)"
            )
        if cli_model:
            warnings.append(f"{bot}: --model '{res['model']}' overrides the tier-{final} model (not vetted)")
        if wide and chosen and chosen != registry_tier and not cli_model:
            flag = "--escalate" if escalate and not tier else "--tier"
            warnings.append(f"{bot}: {flag} sets tier {chosen} over registry tier {registry_tier}")
        if bot in m.PROTECTED_BOTS and res["source"] not in ("cli:--model", "env:CAPSULE_MODEL"):
            dw = m.protected_downgrade_warning(bot, res["model"], source=res["source"])
            if dw:
                override_warnings.append(dw)
                warnings.append(dw)
        if bot in m.PROTECTED_BOTS and (res["source"] == "cli:--model" or res["source"] == "env:CAPSULE_MODEL"):
            base = m.resolve_model(bot=bot, tier=final, env={})
            if base["model"] != res["model"]:
                override_warnings.append(
                    f"WARN: {bot} is a protected bot; {res['source']} replaces its tier-{final} model "
                    f"'{base['model']}' with '{res['model']}' (possible downgrade, not vetted)"
                )
        return res, guard_why

    hops = []
    owner_res = None
    for bot in result["handoff"]:
        res, guard_why = resolve(bot)
        if bot == owner:
            owner_res, owner_guard = res, guard_why
        hops.append({"bot": bot, "model": res["model"], "tier": res["tier"]})
    if owner_res is None:  # owner not in chain (should not happen); resolve it directly
        owner_res, owner_guard = resolve(owner)
    result["model"] = owner_res["model"]
    result["model_tier"] = owner_res["tier"]
    result["model_source"] = owner_res["source"]
    result["model_reason"] = why + (f"; guard: {owner_guard}" if owner_guard else "")
    result["hops"] = hops
    result["warnings"] = list(dict.fromkeys(warnings))
    if override_warnings:
        result["override_warning"] = "; ".join(dict.fromkeys(override_warnings))
    return result


def persist_result(result: Dict, base: Optional[Path] = None) -> str:
    """Persist the routed envelope under ``<base>/.capsule/envelopes/``; return its reference (relative path)."""
    env_mod = _envelope()
    base = Path(base or Path.cwd())
    env = env_mod.Envelope.from_dict({k: result[k] for k in ("root_request", "root_hash", "ledger", "artifacts")})
    env = env.append({"kind": "route", "owner": result["owner"], "workflow_tier": result.get("workflow_tier", "")})
    path = env_mod.persist(env, base)
    return path.relative_to(base).as_posix()


def main(argv=None) -> int:
    import json
    parser = argparse.ArgumentParser(description="Route a request to the safest Capsule Corp owner")
    parser.add_argument("request", nargs="+", help="Request text to classify")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    parser.add_argument("--model", help="Force a model (highest precedence)")
    parser.add_argument("--tier", help="Force a model tier: flash, pro, premium")
    parser.add_argument("--escalate", action="store_true", help="Escalate to the premium tier")
    parser.add_argument("--persist", action="store_true", help="Opt in: write the envelope to .capsule/envelopes/ and print its reference")
    args = parser.parse_args(argv)
    try:
        result = attach_model(route_request(" ".join(args.request)), args.model, args.tier, args.escalate)
        if args.persist:
            result["envelope_ref"] = persist_result(result)
    except _models().ModelsError as exc:
        msg = _envelope().sanitize_text(exc, 300)
        if args.json:
            print(json.dumps({"status": "error", "error": msg}))
        else:
            print(f"Error: {msg}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError) as exc:  # EnvelopeError is a ValueError
        msg = _envelope().sanitize_text(exc, 300)
        if args.json:
            print(json.dumps({"status": "error", "error": msg}))
        else:
            print(f"Routing error: {msg}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Status: {result['status']}")
        print(f"Owner: {result['owner']} ({result.get('role', 'Specialist')}) [Suggestion]")
        print(f"Workflow Tier: {result.get('workflow_tier', 'standard_feature')}")
        print(f"Suggested Workflow: {' -> '.join(result.get('suggested_workflow', []))}")
        print(f"Intent: {result['intent']}")
        print(f"Reason: {result['reason']}")
        print(f"Handoff: {' -> '.join(result['handoff'])}")
        clean = _envelope().sanitize_text
        print(f"Model: {clean(result['model'], 128)} (tier: {result['model_tier']}, source: {clean(result['model_source'], 64)})")
        if result.get("envelope_ref"):
            print(f"Envelope: {result['envelope_ref']}")
        if result.get("override_warning"):
            print(clean(result["override_warning"], 600), file=sys.stderr)
        for warning in result.get("warnings", []):
            print(f"Warning: {clean(warning, 300)}", file=sys.stderr)
    return 0 if result["status"] == "routed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
