#!/usr/bin/env python3
"""
Dr. Gero's Transcript & Routine Healthcheck (Capsule Corp)
Faithfully implements Lauren Tan's Dr. Eggbot template & pstack methodology.

Audits conversation transcripts (transcript.jsonl) from Antigravity/Gemini/Codex sessions.
Detects:
  - User friction signals (frustration, "stop", "wrong", "i said", "undo", "not what i meant")
  - Misunderstandings & repeated human steering
  - Tool errors and token bloat
Outputs:
  - Executive capsule (at most 5 bullets)
  - Concrete proposals tagged [skill], [bot], or [routine] with supporting evidence
  - Stays quiet when there is nothing to propose (--quiet flag)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

FRICTION_PATTERNS = [
    r"\bno\b",
    r"\bdon't\b",
    r"\bdo not\b",
    r"\bstop\b",
    r"\bfix\b",
    r"\binstead\b",
    r"\bwrong\b",
    r"\bundo\b",
    r"\brevert\b",
    r"\berror\b",
    r"\bfailed\b",
    r"\bshould be\b",
    r"\bnot what i\b",
    r"\bnot what i meant\b",
    r"\bi said\b",
    r"\bthat's not\b",
    r"\bwhy did you\b",
    r"\bwhy are you\b",
    r"\bplease don't\b",
    r"\bwait\b",
]

COMPILED_FRICTION = [re.compile(p, re.IGNORECASE) for p in FRICTION_PATTERNS]


def find_brain_dir() -> Path:
    return Path.home() / ".gemini" / "antigravity-cli" / "brain"


def get_latest_conversation(brain_dir: Path) -> Optional[Path]:
    if not brain_dir.exists():
        return None
    convos = [p for p in brain_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if not convos:
        return None
    convos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return convos[0]


def parse_transcript(transcript_path: Path) -> List[Dict[str, Any]]:
    steps = []
    if not transcript_path.exists():
        return steps
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return steps


def analyze_transcript(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    human_corrections = []
    tool_failures = []
    tool_usage: Dict[str, int] = {}
    total_steps = len(steps)
    user_inputs = 0
    model_turns = 0

    prev_step = None
    for step in steps:
        step_type = step.get("type", "")
        source = step.get("source", "")
        content = step.get("content", "")

        if step_type == "USER_INPUT" or source == "USER_EXPLICIT":
            user_inputs += 1
            if prev_step and (prev_step.get("type") == "PLANNER_RESPONSE" or prev_step.get("source") == "MODEL"):
                matches = [p.pattern for p in COMPILED_FRICTION if p.search(content)]
                if matches:
                    human_corrections.append({
                        "step_index": step.get("step_index"),
                        "created_at": step.get("created_at"),
                        "matched_patterns": matches,
                        "excerpt": content[:300].strip(),
                    })

        elif step_type == "PLANNER_RESPONSE" or source == "MODEL":
            model_turns += 1
            tool_calls = step.get("tool_calls", [])
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name") or tc.get("name", "unknown")
                tool_usage[fn_name] = tool_usage.get(fn_name, 0) + 1

        if step.get("status") == "ERROR":
            tool_failures.append({
                "step_index": step.get("step_index"),
                "created_at": step.get("created_at"),
                "content": content[:300].strip() if content else "Error status on step"
            })

        prev_step = step

    proposals = []
    for corr in human_corrections:
        clean_text = re.sub(r"\s+", " ", corr["excerpt"])[:100]
        # Tag proposal category based on content
        if "test" in clean_text.lower() or "verify" in clean_text.lower():
            proposals.append({
                "type": "[skill]",
                "title": "Verification Gate Enforcement",
                "evidence": f"Step #{corr['step_index']}: \"{clean_text}\""
            })
        elif "agent" in clean_text.lower() or "bot" in clean_text.lower():
            proposals.append({
                "type": "[bot]",
                "title": "Specialized Subagent Extraction",
                "evidence": f"Step #{corr['step_index']}: \"{clean_text}\""
            })
        else:
            proposals.append({
                "type": "[skill]",
                "title": "Prompt Constraint & Runbook Patch",
                "evidence": f"Step #{corr['step_index']}: \"{clean_text}\""
            })

    return {
        "total_steps": total_steps,
        "user_inputs": user_inputs,
        "model_turns": model_turns,
        "tool_usage": tool_usage,
        "human_corrections": human_corrections,
        "tool_failures": tool_failures,
        "proposals": proposals,
    }


def generate_eggbot_report(convo_id: str, analysis: Dict[str, Any]) -> str:
    report = []
    report.append(f"# Dr. Gero's Transcript Healthcheck")
    report.append(f"**Session:** `{convo_id}` | **Timestamp:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    report.append(f"**Standard:** Dr. Eggbot & pstack Rubric (Lauren Tan / SpaceXAI)")
    report.append("")

    # 1. Executive Capsule (at most 5 bullets)
    report.append("## 1. Executive Capsule")
    report.append(f"- **Volume:** {analysis['total_steps']} total steps ({analysis['user_inputs']} user / {analysis['model_turns']} model turns).")
    report.append(f"- **Friction Signals:** {len(analysis['human_corrections'])} user steering/correction incidents detected.")
    report.append(f"- **Execution Reliability:** {len(analysis['tool_failures'])} tool call failures.")
    report.append(f"- **Tool Spread:** {len(analysis['tool_usage'])} distinct tools invoked across session.")
    if analysis["proposals"]:
        report.append(f"- **Actionable Gaps:** {len(analysis['proposals'])} candidate proposal(s) identified for review.")
    else:
        report.append("- **Status:** Clean execution. High autonomous alignment with zero steering friction.")
    report.append("")

    # 2. Proposals Tagged [skill] | [bot] | [routine]
    report.append("## 2. Proposals (Tagged by Evidence)")
    if analysis["proposals"]:
        for idx, p in enumerate(analysis["proposals"], 1):
            report.append(f"{idx}. **`{p['type']}` {p['title']}**")
            report.append(f"   - **Evidence:** {p['evidence']}")
    else:
        report.append("_Zero friction proposals._ System operated without prompt degradation.")
    report.append("")

    # 3. Tool Utilization & Bloat Check
    report.append("## 3. Tool Utilization & Lean Allowlist Audit")
    if analysis["tool_usage"]:
        report.append("| Tool Name | Invocations |")
        report.append("| :--- | :--- |")
        for tool, count in sorted(analysis["tool_usage"].items(), key=lambda x: x[1], reverse=True):
            report.append(f"| `{tool}` | {count} |")
    else:
        report.append("_No tool records found._")
    report.append("")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Dr. Gero's Transcript & Routine Healthcheck")
    parser.add_argument("--conversation-id", "-c", help="Conversation ID to audit")
    parser.add_argument("--latest", "-l", action="store_true", help="Audit the most recent conversation")
    parser.add_argument("--output", "-o", help="Path to save markdown audit report")
    parser.add_argument("--quiet", "-q", action="store_true", help="Stay quiet when there are zero proposals (Dr. Eggbot rule)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of markdown")
    args = parser.parse_args()

    brain_dir = find_brain_dir()
    target_convo: Optional[Path] = None

    if args.conversation_id:
        target_convo = brain_dir / args.conversation_id
    elif args.latest or not args.conversation_id:
        target_convo = get_latest_conversation(brain_dir)

    if not target_convo or not target_convo.exists():
        print(f"Error: Could not locate conversation directory in {brain_dir}", file=sys.stderr)
        sys.exit(1)

    convo_id = target_convo.name
    transcript_file = target_convo / ".system_generated" / "logs" / "transcript.jsonl"
    if not transcript_file.exists():
        transcript_file = target_convo / ".system_generated" / "logs" / "transcript_full.jsonl"

    if not transcript_file.exists():
        print(f"Error: No transcript found for conversation {convo_id}", file=sys.stderr)
        sys.exit(1)

    steps = parse_transcript(transcript_file)
    analysis = analyze_transcript(steps)

    if args.quiet and len(analysis["proposals"]) == 0:
        # Dr. Eggbot rule: stay quiet when nothing to report
        sys.exit(0)

    if args.json:
        output_text = json.dumps({"conversation_id": convo_id, "analysis": analysis}, indent=2)
    else:
        output_text = generate_eggbot_report(convo_id, analysis)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")
        print(f" Healthcheck report saved: {out_path}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
