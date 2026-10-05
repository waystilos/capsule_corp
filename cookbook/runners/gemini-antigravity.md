# Using Capsule Corp with Google Antigravity & Gemini CLI

This guide explains how to get the most out of the **Capsule Corp Cohort** when developing with **Google Antigravity (AGY)** and the **Gemini CLI** (`agy`).

---

## 1. How Antigravity / Gemini Integrates with Capsule Corp

Google Antigravity is a natively agentic coding environment equipped with subagent invocation, rich artifacts, and background reactive messaging:

| Layer | Path | Purpose |
| :--- | :--- | :--- |
| **Workspace Directives** | `GEMINI.md` | Injected into the system prompt for all Antigravity agent turns. |
| **Global Guidelines** | `~/.gemini/GEMINI.md` | Universal Capsule Corp standards applied to all active workspaces. |
| **Custom Skills** | `~/.gemini/config/skills/` | Built-in and synced skills (`audit-transcripts`, `scaffold-agent`, `verification-gate`). |
| **Artifacts** | `<appDataDir>/brain/<convo-id>/` | Structured reports, PRDs, task lists, and visual diagrams. |

---

## 2. Quick Setup & Autonomous Onboarding

### Initialize a Project
```bash
capsule init --tool gemini /path/to/project
```
*(Alias `--tool agy` is also supported).*

### Zero-Touch Auto-Adoption
When you open a workspace in Antigravity or invoke `agy` in a repository initialized with Capsule Corp:
- Antigravity detects the Capsule Corp directives (`.github/copilot-instructions.md` or `AGENTS.md`).
- If `GEMINI.md` is missing, Antigravity **autonomously executes `capsule init --tool gemini .`**.

---

## 3. Best Practices in Antigravity

### A. Subagent Delegation (`invoke_subagent`)
Antigravity can spin up dedicated background subagents for research and tasks:
- **Research Specialist:** Delegate deep codebase exploration or web searches to a read-only `research` subagent to keep the main context window lean (`guard-the-context-window` principle).
- **Execution Specialist:** Invoke `self` or defined cohort subagents for concurrent multi-file edits.

### B. High-Leverage Slash Commands
Take advantage of Antigravity's interactive slash commands:
- **`/plan` (Piccolo Mode):** Triggers structured, step-by-step task tree planning before code modifications begin.
- **`/goal` (Ultra Instinct Goku):** Runs long-running autonomous execution with thorough verification gates.
- **`/boost` (Trunks + Android 17):** Deep reasoning mode with multi-perspective analysis and rigorous verification.
- **`/grill-me` (Bulma Interview):** Rapid interactive Q&A to resolve requirements and edge-case ambiguities.

### C. Artifact & Task Brief Handoffs
Deliverables and handoffs use the standard Task Brief envelope:
- **Bulma:** Generates structured PRD artifacts with Mermaid user flow diagrams and testable acceptance criteria.
- **Piccolo:** Deconstructs complex features into atomic tasks formatted as Task Briefs.
- **Goku:** Executes the Task Brief with Ultra Instinct focus, adding behavior tests.

### D. Multi-AI Check-In Room & Timeclock
When collaborating with other AI runners (Claude Code, OpenAI Codex, Cursor) on the same workspace:
- Check active shifts and claimed files: `capsule room`
- Clock in before modifying code:
  ```bash
  capsule clock-in --task "Task description" --files "path/to/files"
  ```
  *(Antigravity / Gemini environment is auto-detected)*
- Monitor shifts and avoid scope drift: `capsule spy .`
- Clock out after running verification checks:
  ```bash
  capsule clock-out --summary "Task finished and verified with exit code 0"
  ```

---

## 4. The Verification Gate (Trunks' Rule)

Antigravity executes verification gates asynchronously in background tasks:
```bash
capsule check .      # Everyday factual checks (tests, lint, typecheck, secrets)
capsule verify .     # Strict verification gate
capsule security .   # Security scanner
capsule attack .     # Red team adversarial attack scan
```
Because Antigravity listens to task completion notifications automatically, you do not need to poll or wait manually—the system resumes execution when verification reports are ready.
