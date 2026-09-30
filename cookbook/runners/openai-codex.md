# Using Capsule Corp with OpenAI Codex CLI

This guide explains how to get the most out of the **Capsule Corp Cohort** when developing with the **OpenAI Codex CLI** (`codex`).

---

## 1. How Codex Integrates with Capsule Corp

OpenAI Codex uses the universal agent standard and strict execution rules:

| Layer | Path | Purpose |
| :--- | :--- | :--- |
| **Workspace Directives** | `AGENTS.md` | Universal markdown standard loaded by Codex upon workspace entry. |
| **Execution Permissions** | `~/.codex/rules/default.rules` | Automatically configured by `capsule sync` to allow non-interactive `capsule` commands. |
| **Codex Skills** | `~/.codex/skills/` | Synced runbooks for verification, bot scaffolding, and transcript audits. |

---

## 2. Quick Setup & Permissions

### Initializing a Project
```bash
capsule init --tool codex /path/to/project
```
*(Alias `--tool agents` is also supported).*

### Pre-Approved Execution Rules
When you run `capsule sync --force`, Capsule Corp appends execution permissions to `~/.codex/rules/default.rules`:
```python
prefix_rule(pattern=["capsule"], decision="allow")
prefix_rule(pattern=["/path/to/capsule-corp/bin/capsule"], decision="allow")
```
This ensures Codex can run `capsule verify` and `capsule security` autonomously in non-interactive batch pipelines.

---

## 3. Best Practices with OpenAI Codex

### A. Non-Interactive Scripted Pipelines
Codex is well-suited for automated CLI scripting. You can pipe structured instructions directly to Codex:

```bash
codex "As @Goku, implement unit tests for authService.ts adhering to AGENTS.md. Then run capsule verify ."
```

### B. Enforcing Trunks' Verification Gate
Codex should always be instructed to end its execution block with verification:

```bash
capsule check .      # Everyday factual checks (tests, lint, typecheck, secrets)
capsule verify .     # Strict verification gate
```

### C. Standard Task Brief Envelope
Pipe structured task briefs to Codex rather than conversational introductions:

```text
Goal: Implement unit tests for authService.ts adhering to AGENTS.md
Scope: src/authService.ts, tests/authService.test.ts
Constraints: Zero external dependencies, minimal diff footprint
Acceptance Criteria: Covers invalid tokens, expiration, and rate-limiting
Verification: capsule check .
```

### D. Zero Conversational Filler
Codex should follow Goku's Ultra Instinct directive:
- Modify only the files directly specified.
- Do not add unrequested comments or speculative dependencies.
- Produce clean, minimal diffs.
