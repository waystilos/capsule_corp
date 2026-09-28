---
name: audit-transcripts
description: Runbook for Dr. Gero to audit past agent execution transcripts, detect repetitive human steering, and generate prompt/skill patches.
---

# Audit Transcripts Skill (Dr. Gero Runbook)

Use this skill to inspect session logs and extract improvements for the cohort.

## Transcript Locations
Antigravity stores session logs at:
`<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`

## Audit Procedure

1. **Scan for Friction Signals:**
   - Look for `source: "USER_EXPLICIT"` steps following agent actions.
   - Detect user phrases indicating correction: *"No, don't do that"*, *"Fix this"*, *"That's not what I asked"*, *"Don't touch that file"*.
   - Identify tool calls with error statuses or repeated identical invocations.

2. **Extract Root Causes:**
   - Did the agent lack project context? $\to$ Needs a Rule (`GEMINI.md` or `AGENTS.md`).
   - Did the agent wander or over-engineer? $\to$ Needs tighter boundaries in its `Job To Be Done`.
   - Did the agent use the wrong tool? $\to$ Tool allowlist must be pruned.
   - Was a manual multi-step workflow repeated? $\to$ Convert into a reusable `SKILL.md`.

3. **Output Remediation Report:**
   - **Agent Name:** Target bot.
   - **Observed Glitch:** The friction pattern identified.
   - **Prompt Patch:** Exact lines to add under "Boundaries" or "Execution Directives".
   - **Skill Candidate:** Any recurring workflow ready to graduate to a Skill.
