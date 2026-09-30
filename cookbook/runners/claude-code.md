# Using Capsule Corp with Anthropic Claude Code

This guide explains how to get the most out of the **Capsule Corp Cohort** when developing with **Anthropic Claude Code** (`claude`).

---

## 1. How Claude Code Integrates with Capsule Corp

Claude Code reads configuration at both the workspace level and the global user level:

| Layer | Path | Purpose |
| :--- | :--- | :--- |
| **Workspace Directives** | `CLAUDE.md` | Persona definitions, Whis routing policy, and Trunks' verification gate. |
| **Tool Permissions** | `.claude/settings.json` | Pre-approves `capsule *` commands so Claude never pauses for bash permission prompts. |
| **Cohort Subagents** | `.claude/agents/*.md` | Specialized persona prompts switchable via `/agents` or direct delegation. |
| **Agentic Skills** | `.claude/skills/*/SKILL.md` | Runbooks for verification, scaffolding, and transcript audits. |
| **Global Rules** | `~/.claude/CLAUDE.md` | System-wide Capsule Corp standards synchronized across your machine. |

---

## 2. Quick Setup & Autonomous Onboarding

### In an Existing Project
If your project is already initialized with Capsule Corp:
```bash
capsule init --tool claude /path/to/project
```
This generates `CLAUDE.md` and `.claude/settings.json`.

### Zero-Touch Auto-Adoption
Whenever you launch Claude Code (`claude`) inside any repository that has been initialized with Capsule Corp:
- Claude Code detects the Capsule Corp directives (`.github/copilot-instructions.md` or `AGENTS.md`).
- If `CLAUDE.md` is missing, Claude **autonomously executes `capsule init --tool claude .` on its own**.
- You do not need to run manual setup commands.

---

## 3. Best Practices with Claude Code

### A. Seamless Pre-Approved CLI Execution
Capsule Corp pre-configures `.claude/settings.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(capsule *)",
      "Bash(./bin/capsule *)"
    ]
  }
}
```
This allows Claude to execute `capsule verify`, `capsule security`, and `capsule doctor` instantly in the background without prompting you for confirmation on every command.

### B. Invoking Specialist Subagents
Claude Code supports specialized subagents defined in `.claude/agents/`:
- Type `/agents` in Claude Code to view registered cohort operatives.
- Delegate explicit tasks to specialists:
  - **`@piccolo`**: Deconstruct complex epics into atomic tasks.
  - **`@goku`**: Surgical implementation with minimal conversational filler.
  - **`@android-17`**: Security audit for secrets, CORS, and dependency CVEs.
  - **`@trunks`**: Test execution and diff verification.
  - **`@android-18`**: Refactoring and dead code cleanup.

### C. Standard Claude Code Prompting Pattern
When starting a feature with Claude Code, follow this format:

```text
As @Whis, route this request and assign the proper specialist:
"We need to implement email OTP authentication with rate limiting."
```

Claude will route the request, assume the specialist role, and follow the handoff chain through verification.

---

## 4. The Verification Gate (Trunks' Rule)

Before ending your Claude Code session or accepting code changes, ensure Claude executes:

```bash
capsule verify .
capsule security .
```

Both must report `VERDICT: GREEN` with exit code 0.
