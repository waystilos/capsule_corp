---
name: scaffold-agent
description: Runbook for Dr. Gero to design, interview, and scaffold high-precision, single-responsibility agents following Lauren Tan's Michelin Kitchen framework.
---

# Scaffold Agent Skill (Dr. Gero Runbook)

Use this skill when designing a new agent or upgrading an existing agent in the cohort.

## Phase 1: The Scoping Interview
Before writing any code or system prompt, answer these five questions:
1. **The Single JTBD:** What is the single outcome this agent is held accountable for? (If it has "and" in the purpose, split it).
2. **The Voice/Archetype:** What DBZ persona best fits this operational mode?
3. **The Minimal Toolset:** What is the absolute minimum list of tools it needs?
4. **The Deterministic Verification:** How does the agent or system objectively verify success (e.g. CLI exit code, schema check)?
5. **Autonomy Stage:** Where is it on the ladder?
   - Level 1: Watch (Supervised interactive pairing)
   - Level 2: Skill (Extracted markdown runbook)
   - Level 3: Routine (Headless cron/CI background execution)

## Phase 2: Generating the Agent Specification
Create the file under `bots/<character_name>.md` and register it in `registry.yaml`:

```markdown
---
name: <name>
alias: <DBZ Character Alias>
role: <Title>
inspiration: <SpaceXAI / Lauren Tan equivalent>
description: <Short discovery string>
---

# <Alias>: <Title>

> "<Character Creed>"

## 1. Job To Be Done (JTBD)
- **Primary:** <Exact task>
- **Boundaries (What it MUST NOT do):** <Anti-goals>

## 2. Allowed Tools
- `<tool_name>`: <Rationale>

## 3. Execution Directives (Bias to Act)
1. ...
2. ...

## 4. Verification Gate
- `<verification command or assertion>`
```

## Phase 3: Registration
Update `registry.yaml` and invoke `define_subagent` if the agent should be immediately active in the session.
