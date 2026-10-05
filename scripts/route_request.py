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


def score_request(request: str, route: Dict) -> Tuple[int, List[str]]:
    text = request.casefold()
    matched = []
    score = 0
    for keyword in route.get("keywords", []):
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
}


def workflow_label(bot: str) -> str:
    display = "-".join(part.capitalize() for part in bot.split("-"))
    return f"{WORKFLOW_ROLE.get(bot, 'Specialist')} (@{display})"


def determine_workflow(request: str, owner: str, handoff: Optional[List[str]] = None) -> Tuple[str, List[str]]:
    """Pick a workflow tier, then build the chain from the route's own handoff list.

    Only the bots named in the matched route's handoff take part. Coordinators are
    added for epics, Product is added only for Builder-owned standard features, and
    nothing else is widened. This keeps specialist work from cycling through the
    whole cohort.
    """
    text = request.casefold()
    small_fix_kws = ["fix", "bug", "typo", "tweak", "patch", "quick", "style", "css", "align", "rename"]
    complex_kws = ["epic", "architecture", "orchestrate", "deconstruct", "redesign", "migrate", "system", "multi-agent"]

    def has_any(keywords: List[str]) -> bool:
        return any(re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text) for kw in keywords)

    chain = list(dict.fromkeys([owner] + list(handoff or [])))

    if has_any(complex_kws) or owner in COORDINATORS:
        tier = "complex_epic"
        coordinator = owner if owner in COORDINATORS else next((b for b in chain if b in COORDINATORS), "piccolo")
        workers = [b for b in chain if b not in COORDINATORS]
        if not workers:
            workers = ["goku", "trunks"]
        chain = [coordinator] + workers
    elif has_any(small_fix_kws):
        tier = "small_fix"
        chain = [b for b in chain if b not in COORDINATORS and b not in ("bulma", "trunks")] or [owner]
    else:
        tier = "standard_feature"
        if owner == "goku" and "bulma" not in chain:
            chain = ["bulma"] + chain

    return tier, [workflow_label(b) for b in chain] + [VERIFICATION_STEP]


def route_request(request: str) -> Dict:
    policy = load_routes()
    ranked = []
    for route in policy["routes"]:
        score, matched = score_request(request, route)
        ranked.append((score, route, matched))
    ranked.sort(key=lambda item: item[0], reverse=True)

    best_score, best_route, matched = ranked[0]
    tied = len(ranked) > 1 and best_score == ranked[1][0]
    if best_score <= 0 or tied:
        fallback_owner = policy["fallback"]
        tier, workflow = determine_workflow(request, fallback_owner, [fallback_owner])
        return {
            "status": "needs_clarification",
            "owner": fallback_owner,
            "role": BOT_TO_ROLE.get(fallback_owner, "Coordinator"),
            "intent": "triage",
            "reason": "No single route matched with confidence; Whis must clarify before dispatch.",
            "handoff": [fallback_owner],
            "matches": matched,
            "workflow_tier": tier,
            "suggested_workflow": workflow,
            "is_suggestion": True,
        }

    owner = best_route["owner"]
    tier, workflow = determine_workflow(request, owner, best_route["handoff"])
    return {
        "status": "routed",
        "owner": owner,
        "role": BOT_TO_ROLE.get(owner, "Specialist"),
        "intent": best_route["intent"],
        "reason": f"Matched: {', '.join(matched)}.",
        "handoff": best_route["handoff"],
        "matches": matched,
        "workflow_tier": tier,
        "suggested_workflow": workflow,
        "is_suggestion": True,
    }


def main(argv=None) -> int:
    import json
    parser = argparse.ArgumentParser(description="Route a request to the safest Capsule Corp owner")
    parser.add_argument("request", nargs="+", help="Request text to classify")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args(argv)
    try:
        result = route_request(" ".join(args.request))
    except (OSError, RuntimeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}))
        else:
            print(f"Routing error: {exc}", file=sys.stderr)
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
    return 0 if result["status"] == "routed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
