"""Deterministically route a request to the safest Capsule Corp owner."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


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
        return {
            "status": "needs_clarification",
            "owner": policy["fallback"],
            "intent": "triage",
            "reason": "No single route matched with confidence; Whis must clarify before dispatch.",
            "handoff": [policy["fallback"]],
            "matches": matched,
        }

    return {
        "status": "routed",
        "owner": best_route["owner"],
        "intent": best_route["intent"],
        "reason": f"Matched: {', '.join(matched)}.",
        "handoff": best_route["handoff"],
        "matches": matched,
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
        print(f"Owner: {result['owner']}")
        print(f"Intent: {result['intent']}")
        print(f"Reason: {result['reason']}")
        print(f"Handoff: {' -> '.join(result['handoff'])}")
    return 0 if result["status"] == "routed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
