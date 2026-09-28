#!/usr/bin/env python3
"""
Dr. Gero's Transcript Auditor (Capsule Corp)
Inspired by Lauren Tan's Dr. Eggbot v0.2.0 at SpaceXAI.

Audits conversation transcripts (transcript.jsonl) from Antigravity sessions.
Identifies:
  - Repetitive human steering / corrections
  - Failed tool calls
  - Stalled or circular execution loops
Outputs actionable prompt patches, negative constraints, and skill graduation candidates.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

STEERING_PATTERNS = [
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
    r"\bthat's not\b",
    r"\bwhy did you\b",
    r"\bplease don't\b",
]

COMPILED_STEERING = [re.compile(p, re.IGNORECASE) for p in STEERING_PATTERNS]


def find_brain_dir() -> Path:
    default_dir = Path.home() / ".gemini" / "antigravity-cli" / "brain"
    return default_dir


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
            # Check if this user input followed a model action and contained steering keywords
            if prev_step and (prev_step.get("type") == "PLANNER_RESPONSE" or prev_step.get("source") == "MODEL"):
                matches = [p.pattern for p in COMPILED_STEERING if p.search(content)]
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

        # Check for tool errors in results
        status = step.get("status")
        if status == "ERROR":
            tool_failures.append({
                "step_index": step.get("step_index"),
                "created_at": step.get("created_at"),
                "content": content[:300].strip() if content else "Error status on step"
            })

        prev_step = step

    return {
        "total_steps": total_steps,
        "user_inputs": user_inputs,
        "model_turns": model_turns,
        "tool_usage": tool_usage,
        "human_corrections": human_corrections,
        "tool_failures": tool_failures,
    }


def generate_audit_report(convo_id: str, analysis: Dict[str, Any]) -> str:
    report = []
    report.append(f"# Dr. Gero's Transcript Audit Report")
    report.append(f"**Session ID:** `{convo_id}`")
    report.append(f"**Timestamp:** `{datetime.now().isoformat()}`")
    report.append(f"**Methodology:** Lauren Tan Michelin Kitchen Trust Engine (Watch -> Skill -> Routine)")
    report.append("")
    report.append("## 1. Executive Summary")
    report.append(f"- **Total Steps Recorded:** {analysis['total_steps']}")
    report.append(f"- **User Turns:** {analysis['user_inputs']}")
    report.append(f"- **Model Turns:** {analysis['model_turns']}")
    report.append(f"- **Detected Human Steering Points:** {len(analysis['human_corrections'])}")
    report.append(f"- **Failed Tool Calls:** {len(analysis['tool_failures'])}")
    report.append("")

    report.append("## 2. Tool Utilization & Bloat Check")
    if analysis["tool_usage"]:
        report.append("| Tool Name | Invocation Count |")
        report.append("| :--- | :--- |")
        for tool, count in sorted(analysis["tool_usage"].items(), key=lambda x: x[1], reverse=True):
            report.append(f"| `{tool}` | {count} |")
    else:
        report.append("_No explicit tool call records identified in this sample._")
    report.append("")

    report.append("## 3. Human Steering Incidents (Friction Signals)")
    if analysis["human_corrections"]:
        for idx, corr in enumerate(analysis["human_corrections"], 1):
            report.append(f"### Incident {idx} (Step #{corr['step_index']})")
            report.append(f"- **Trigger Keywords:** {', '.join(corr['matched_patterns'])}")
            report.append(f"- **User Steering Input:**")
            report.append(f"> \"{corr['excerpt']}\"")
            report.append("")
    else:
        report.append(" **Zero human steering incidents detected.** The session exhibited smooth autonomous alignment.")
        report.append("")

    report.append("## 4. Dr. Gero's Prescriptions & Prompt Patches")
    if analysis["human_corrections"]:
        report.append("Based on human steering patterns, apply the following negative constraints to your agent prompts:")
        report.append("```markdown")
        report.append("## Negative Constraints (Learned from Friction)")
        for corr in analysis["human_corrections"][:3]:
            clean_snippet = re.sub(r"\s+", " ", corr['excerpt'])[:80]
            report.append(f"- Guardrail against: \"{clean_snippet}...\"")
        report.append("```")
    else:
        report.append("The current agent prompts and boundaries are operating cleanly. No prompt degradation observed.")
    report.append("")

    report.append("## 5. Skill Graduation Candidates (Watch -> Skill -> Routine)")
    report.append("If any multi-step workflows were repeated in this session, codify them into a new skill under `skills/<name>/SKILL.md`.")
    report.append("")
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Dr. Gero's Transcript Auditor for Antigravity")
    parser.add_argument("--conversation-id", "-c", help="Conversation ID to audit")
    parser.add_argument("--latest", "-l", action="store_true", help="Audit the most recent conversation")
    parser.add_argument("--output", "-o", help="Path to save markdown audit report")
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
        # Fallback to transcript_full.jsonl
        transcript_file = target_convo / ".system_generated" / "logs" / "transcript_full.jsonl"

    if not transcript_file.exists():
        print(f"Error: No transcript found for conversation {convo_id}", file=sys.stderr)
        sys.exit(1)

    steps = parse_transcript(transcript_file)
    analysis = analyze_transcript(steps)

    if args.json:
        output_text = json.dumps({"conversation_id": convo_id, "analysis": analysis}, indent=2)
    else:
        output_text = generate_audit_report(convo_id, analysis)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")
        print(f" Audit report generated at: {out_path}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
