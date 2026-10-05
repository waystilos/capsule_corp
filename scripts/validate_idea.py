#!/usr/bin/env python3
"""
Capsule Corp Pre-Code Validation Engine (`capsule validate`)
Adversarial demand and distribution validation powered by Bulma's Razor and Hercule's Hype Audit.
Forces a ruthless GO / PIVOT / KILL verdict before a single line of code is written.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple, Any

try:
    from .runtime import configure_utf8_stdio
except ImportError:
    from runtime import configure_utf8_stdio

configure_utf8_stdio()

# Saturation and red-flag trigger patterns
HIGH_SATURATION_PATTERNS = [
    (re.compile(r"\b(todo|to-do|task manager|habit tracker)\b", re.IGNORECASE), "Task/Habit Trackers (Massive market saturation; near-zero barrier to entry)"),
    (re.compile(r"\b(wrapper around|chatgpt wrapper|simple gpt|ai wrapper)\b", re.IGNORECASE), "Thin LLM Wrappers (Fragile moats easily killed by upstream model updates)"),
    (re.compile(r"\b(crypto trading|meme coin|nft marketplace)\b", re.IGNORECASE), "Speculative Crypto/NFT (Regulatory friction & volatile sentiment)"),
    (re.compile(r"\b(social network for|tinder for|uber for)\b", re.IGNORECASE), "Generic Two-Sided Marketplaces (Cold start chicken-and-egg trap)"),
]

# Spreadsheet substitutability indicators
SPREADSHEET_SUBSTITUTES = [
    (re.compile(r"\b(simple list|contact list|bookmark manager|note taking|simple tracker)\b", re.IGNORECASE), "High Google Sheets / Notion substitutability"),
]

# High willingness-to-pay indicators (B2B, infra, security, compliance, data pipeline)
HIGH_WTP_PATTERNS = [
    (re.compile(r"\b(postgres|database|kubernetes|docker|security|compliance|hipaa|soc2|billing|invoice|stripe|pipeline|latency|monitoring|observability|sso|oauth)\b", re.IGNORECASE), "B2B / Developer / Ops infrastructure budget"),
]

# Ecosystem distribution indicators (tools embedded where developers/teams already work)
ECOSYSTEM_WEDGE_PATTERNS = [
    (re.compile(r"\b(cli|terminal|command line)\b", re.IGNORECASE), "CLI / Terminal integration (Frictionless developer workflow adoption)"),
    (re.compile(r"\b(github action|github app|git hook|pr review)\b", re.IGNORECASE), "GitHub / CI pipeline embed (Zero-context-switching distribution)"),
    (re.compile(r"\b(slack|discord|teams)\b", re.IGNORECASE), "Team collaboration embed (Natural organizational virality)"),
    (re.compile(r"\b(vscode|cursor|ide plugin|extension)\b", re.IGNORECASE), "IDE / Editor embed (Deep editor workflow lock-in)"),
    (re.compile(r"\b(postgres extension|k8s operator|helm chart|docker)\b", re.IGNORECASE), "Infrastructure native deployment (Direct operations adoption)"),
]

# Vanity hype indicators (relying on vague virality instead of utility)
VANITY_HYPE_PATTERNS = [
    (re.compile(r"\b(go viral|viral loop|tiktok|social media marketing|facebook ads|influencers)\b", re.IGNORECASE), "High CAC Vanity Risk: Relies on external ad spend or speculative virality"),
    (re.compile(r"\b(everyone will use it|for all consumers|universal app)\b", re.IGNORECASE), "Unfocused Demographic: Lacks a concrete, hair-on-fire initial niche"),
]


def audit_distribution_and_hype(idea_text: str) -> Dict[str, Any]:
    """Hercule's reality check on distribution wedges and vanity hype."""
    text = idea_text.lower()

    ecosystem_matches = []
    for pattern, label in ECOSYSTEM_WEDGE_PATTERNS:
        if pattern.search(text):
            ecosystem_matches.append(label)

    vanity_flags = []
    for pattern, warning in VANITY_HYPE_PATTERNS:
        if pattern.search(text):
            vanity_flags.append(warning)

    if ecosystem_matches and not vanity_flags:
        channel_status = "HEALTHY_WEDGE"
        channel_verdict = "🟢 Verified Organic Wedge (Embedded directly in existing user workflow)"
    elif ecosystem_matches and vanity_flags:
        channel_status = "MIXED"
        channel_verdict = "🟡 Mixed Signals (Has workflow embed, but diluted by speculative hype)"
    elif vanity_flags:
        channel_status = "HIGH_RISK_HYPE"
        channel_verdict = "🔴 High-Risk Hype Trap (Relies on external acquisition without organic retention hook)"
    else:
        channel_status = "STANDARD"
        channel_verdict = "⚪ Standard Distribution (Needs explicit outbound positioning)"

    return {
        "status": channel_status,
        "verdict": channel_verdict,
        "ecosystem_embeds": ecosystem_matches or ["Standalone application (requires explicit distribution effort)"],
        "vanity_flags": vanity_flags or ["Zero vanity flags detected (focused utility orientation)"],
    }


def evaluate_idea(
    idea: str,
    target_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run Bulma's Razor and Hercule's Distribution Audit on an idea."""
    cleaned_idea = idea.strip()
    if not cleaned_idea or len(cleaned_idea) < 8:
        raise ValueError("Idea description is too short. Provide at least a full sentence describing the feature or product.")

    text = cleaned_idea.lower()

    # 1. BULMA'S RAZOR: 5 Adversarial Dimensions
    # Dimension 1: The Spreadsheet Test (Substitutability)
    spreadsheet_penalty = 0
    spreadsheet_notes = []
    for pattern, note in SPREADSHEET_SUBSTITUTES:
        if pattern.search(text):
            spreadsheet_penalty += 3.5
            spreadsheet_notes.append(note)

    spreadsheet_score = max(1.0, round(9.0 - spreadsheet_penalty, 1))

    # Dimension 2: Buyer Authority & Willingness to Pay
    wtp_bonus = 0
    wtp_notes = []
    for pattern, note in HIGH_WTP_PATTERNS:
        if pattern.search(text):
            wtp_bonus += 3.0
            wtp_notes.append(note)

    if any(kw in text for kw in ["b2b", "enterprise", "teams", "devops", "dba", "sre", "revenue"]):
        wtp_bonus += 2.0

    consumer_penalty = 2.0 if any(kw in text for kw in ["consumer", "students", "friends", "casual", "dating"]) else 0.0
    wtp_score = min(10.0, max(2.0, round(5.0 + wtp_bonus - consumer_penalty, 1)))

    # Dimension 3: Distribution Wedge Feasibility
    wedge_score = 6.5
    wedge_notes = []
    if any(kw in text for kw in ["discord", "slack", "github", "chrome extension", "shopify", "postgres", "npm", "cli"]):
        wedge_score += 2.5
        wedge_notes.append("Built-in ecosystem distribution wedge identified")
    elif any(kw in text for kw in ["social media", "ads", "tiktok", "twitter", "word of mouth"]):
        wedge_score -= 2.0
        wedge_notes.append("Vague social/ad acquisition (high customer acquisition cost risk)")

    wedge_score = min(10.0, max(2.0, round(wedge_score, 1)))

    # Dimension 4: Saturation & Competitive Moat
    saturation_penalties = []
    for pattern, warning in HIGH_SATURATION_PATTERNS:
        if pattern.search(text):
            saturation_penalties.append(warning)

    moat_score = 8.0
    if saturation_penalties:
        moat_score -= (len(saturation_penalties) * 3.0)
    moat_score = max(1.0, round(moat_score, 1))

    # Dimension 5: Scope & 80/20 Slice Feasibility
    feature_count = len(re.findall(r"(\band\b|,|\bwith\b|\bplus\b)", text))
    if feature_count >= 4:
        scope_score = 5.0
        amputation_advice = "Severe feature bloat detected in idea brief. Amputate 80% of secondary features."
    else:
        scope_score = 8.5
        amputation_advice = "Sharp, focused scope. Ready for minimal atomic MVP specification."

    # Composite Score (0.0 to 10.0)
    composite_score = round(
        (spreadsheet_score * 0.25) +
        (wtp_score * 0.25) +
        (wedge_score * 0.25) +
        (moat_score * 0.15) +
        (scope_score * 0.10),
        1
    )

    # Verdict derivation
    if composite_score >= 7.5 and not saturation_penalties:
        verdict = "GO"
        verdict_badge = "🟢 GO (Greenlit for PRD & MVP Blueprint)"
    elif composite_score >= 5.5 and len(saturation_penalties) <= 1 and spreadsheet_score >= 6.0:
        verdict = "PIVOT"
        verdict_badge = "🟡 PIVOT (Viable core, but fatal distribution or buyer flaw)"
    else:
        verdict = "KILL"
        verdict_badge = "🔴 KILL (High substitution, zero willingness to pay, or bloated trap)"

    # 2. HERCULE'S RECON: Distribution & Hype Reality Check
    distribution_audit = audit_distribution_and_hype(cleaned_idea)

    # 3. 14-Day Kill Metric Generation
    kill_metric = (
        "If fewer than 3 paying users or active team installations are retained 14 days post-launch, "
        "terminate project immediately and reallocate engineering tokens."
    )

    return {
        "idea": cleaned_idea,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "verdict_badge": verdict_badge,
        "score": composite_score,
        "dimensions": {
            "spreadsheet_test": {
                "score": spreadsheet_score,
                "label": "The Spreadsheet Test (Non-Substitutability)",
                "passed": spreadsheet_score >= 6.0,
                "notes": spreadsheet_notes or ["Passes: requires custom database, automation, or persistent compute"],
            },
            "buyer_authority": {
                "score": wtp_score,
                "label": "Buyer Authority & Willingness to Pay",
                "passed": wtp_score >= 6.0,
                "notes": wtp_notes or ["Standard monetization profile"],
            },
            "distribution_wedge": {
                "score": wedge_score,
                "label": "Distribution Wedge Feasibility",
                "passed": wedge_score >= 6.0,
                "notes": wedge_notes or ["Standard outbound / community distribution"],
            },
            "moat_saturation": {
                "score": moat_score,
                "label": "Moat & Market Saturation",
                "passed": moat_score >= 6.0,
                "warnings": saturation_penalties,
            },
            "scope_clarity": {
                "score": scope_score,
                "label": "80/20 Amputation & Scope Discipline",
                "passed": scope_score >= 6.0,
                "advice": amputation_advice,
            },
        },
        "distribution": distribution_audit,
        "kill_metric": kill_metric,
        "target_dir": str(target_dir) if target_dir else None,
    }


def render_validation_contract_markdown(eval_data: Dict[str, Any]) -> str:
    """Generate the formal .capsule/VALIDATION.md contract that bounds Goku and King Kai."""
    idea = eval_data["idea"]
    verdict = eval_data["verdict"]
    score = eval_data["score"]
    ts = eval_data["timestamp"]
    dims = eval_data["dimensions"]
    dist = eval_data.get("distribution", {})

    lines = [
        "# 💡 Capsule Corp Pre-Code Validation Contract",
        f"**Idea:** {idea}",
        f"**Validated On:** {ts}",
        f"**Final Verdict:** {eval_data['verdict_badge']}",
        f"**Viability Score:** {score} / 10.0",
        "",
        "---",
        "",
        "## 1. Bulma's Razor Evaluation",
    ]

    for key, dim in dims.items():
        icon = "✓" if dim.get("passed", True) else "✗"
        lines.append(f"### {icon} {dim['label']} ({dim['score']}/10)")
        if "notes" in dim:
            for note in dim["notes"]:
                lines.append(f"- {note}")
        if "warnings" in dim and dim["warnings"]:
            for warn in dim["warnings"]:
                lines.append(f"- ⚠️ **Warning:** {warn}")
        if "advice" in dim:
            lines.append(f"- **Guidance:** {dim['advice']}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 2. Hercule's Distribution & Hype Audit",
        f"**Channel Verdict:** {dist.get('verdict', 'N/A')}",
        "",
        "### Workflow Embeds:",
    ])
    for item in dist.get("ecosystem_embeds", []):
        lines.append(f"- {item}")

    lines.append("")
    lines.append("### Vanity & CAC Reality Check:")
    for flag in dist.get("vanity_flags", []):
        lines.append(f"- {flag}")

    lines.extend([
        "",
        "---",
        "",
        "## 3. The 14-Day Falsification Metric",
        f"> **Kill Criteria:** {eval_data['kill_metric']}",
        "",
        "---",
        "",
        "## 4. Operational Handoff Envelope",
        f"- **Verdict Status:** `{verdict}`",
    ])

    if verdict == "GO":
        lines.extend([
            "- **Next Owner:** `@Bulma` (Chief Product Architect) to author PRD with strict acceptance criteria.",
            "- **Builder Boundary:** `@Goku` is authorized to build ONLY the single atomic wedge approved above.",
            "- **Watchdog Grant:** `@King-Kai` will enforce zero unbudgeted file drift against this scope.",
        ])
    elif verdict == "PIVOT":
        lines.extend([
            "- **Action Required:** Address the flagged distribution or monetization flaws above.",
            "- **Re-run:** Run `capsule validate \"revised idea\"` once the wedge is sharpened.",
        ])
    else:
        lines.extend([
            "- **Action Required:** KILL project. Do not allocate engineering shifts or write code.",
        ])

    lines.append("")
    return "\n".join(lines)


def save_validation_contract(eval_data: Dict[str, Any], target_dir: Path) -> Path:
    """Save validation results into .capsule/VALIDATION.md atomically."""
    capsule_dir = target_dir / ".capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)
    out_file = capsule_dir / "VALIDATION.md"
    content = render_validation_contract_markdown(eval_data)
    out_file.write_text(content, encoding="utf-8")
    return out_file


def format_validation_terminal_report(eval_data: Dict[str, Any]) -> str:
    """Format rich terminal output for developer review."""
    dist = eval_data.get("distribution", {})
    lines = [
        "=" * 88,
        " 💡 CAPSULE CORP PRE-CODE VALIDATION DECK (Bulma & Hercule)",
        "=" * 88,
        f" Idea:   {eval_data['idea'][:72]}",
        f" Status: {eval_data['verdict_badge']}",
        f" Score:  {eval_data['score']} / 10.0",
        "-" * 88,
        " BULMA'S ADVERSARIAL RAZOR:",
    ]

    for _, dim in eval_data["dimensions"].items():
        badge = "✓" if dim.get("passed", True) else "✗"
        lines.append(f"   [{badge}] {dim['label']:<48} ({dim['score']}/10)")
        if "warnings" in dim and dim["warnings"]:
            for w in dim["warnings"]:
                lines.append(f"       ⚠️ {w}")

    lines.append("")
    lines.append(" HERCULE'S DISTRIBUTION & HYPE AUDIT:")
    lines.append(f"   Verdict: {dist.get('verdict', 'N/A')}")
    for embed in dist.get("ecosystem_embeds", []):
        lines.append(f"   • Embed: {embed}")
    for flag in dist.get("vanity_flags", []):
        lines.append(f"   • Hype:  {flag}")

    lines.append("")
    lines.append(" 14-DAY KILL CRITERIA:")
    lines.append(f"   \"{eval_data['kill_metric']}\"")
    lines.append("=" * 88)

    if eval_data["verdict"] == "GO":
        lines.append(" 🚀 ACTION: GREENLIT. Contract saved. Handing off to @Bulma for MVP PRD specification.")
    elif eval_data["verdict"] == "PIVOT":
        lines.append(" 🟡 ACTION: PIVOT REQUIRED. Do not write code. Sharpen wedge and re-validate.")
    else:
        lines.append(" 🛑 ACTION: KILL. Fatal viability flaw. Engineering tokens preserved.")
    lines.append("=" * 88)

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Capsule Corp Pre-Code Validation Engine")
    parser.add_argument("idea", nargs="?", help="Idea or feature brief to validate")
    parser.add_argument("--file", "-f", help="Read idea brief from a markdown or text file")
    parser.add_argument("--save", action="store_true", default=True, help="Save contract to .capsule/VALIDATION.md (default: true)")
    parser.add_argument("--no-save", action="store_false", dest="save", help="Do not write contract to disk")
    parser.add_argument("--dir", default=".", help="Target project directory (default: CWD)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Exit code 1 if verdict is KILL or PIVOT")

    args = parser.parse_args(argv)

    idea_text = args.idea
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            return 1
        idea_text = file_path.read_text(encoding="utf-8")

    if not idea_text:
        if sys.stdin.isatty():
            try:
                print("💡 Enter the founder idea or feature brief to validate:")
                idea_text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                return 1
        else:
            idea_text = sys.stdin.read().strip()

    if not idea_text:
        print("Error: No idea provided. Usage: capsule validate \"Your idea description\"", file=sys.stderr)
        return 1

    target_dir = Path(args.dir).resolve()

    try:
        eval_data = evaluate_idea(
            idea=idea_text,
            target_dir=target_dir,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.save:
        save_validation_contract(eval_data, target_dir)

    if args.json:
        print(json.dumps(eval_data, indent=2))
    else:
        print(format_validation_terminal_report(eval_data))

    if args.strict and eval_data["verdict"] in ("KILL", "PIVOT"):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
