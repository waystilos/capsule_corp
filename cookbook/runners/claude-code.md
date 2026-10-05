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
- Core 4 Default Roles:
  - **`@bulma`**: MVP scoping, PRDs, API specs, and acceptance criteria.
  - **`@goku`**: Frontline implementation with Ultra Instinct focus.
  - **`@trunks`**: Verification gatekeeper: tests, linters, typechecks, diff audit.
  - **`@piccolo`** / **`@whis`**: Deconstruct complex epics into atomic tasks.
- Optional Specialists (on demand):
  - **`@android-17`**: Security audit for secrets, CORS, and dependency CVEs.
  - **`@cell`**: Red Team adversarial attacks, prompt injection fuzzing, and ReDoS.
  - **`@king-kai`**: Watchdog supervisor catching scope drift, rogue edits, and stalled shifts.
  - **`@android-18`**: Refactoring and dead code cleanup.
  - **`@videl`**: UX, accessibility, and user flows.
  - **`@vegeta`**: Docker, CI/CD, and database migrations.
  - **`@roshi`**: Game feel, canvas mechanics, sprite math, and physics.
  - **`@hercule`**: Launch marketing, README hooks, and distribution copy.
  - **`@zarbon`**: Visual elegance, typography, and micro-interactions.
  - **`@dr-gero`**: System scaffolding, skill creation, transcript friction auditing.
  - **`@goten`**: Sprite animation sequences and hitbox frame timing.
  - **`@android-16`**: Rive vector character rig validation and state-machine checks.

### C. Standard Task Brief Handoff
Pass tasks to Claude Code using the standard Task Brief envelope:

```markdown
### Task Brief
- **Goal:** Implement email OTP authentication with rate limiting
- **Scope:** src/auth/otp.py, tests/test_otp.py
- **Constraints:** Python 3.8+ compatible, zero new external dependencies
- **Acceptance Criteria:** Rate limit rejects 5+ requests/min; token expires after 5 mins
- **Verification:** capsule check .
```

### D. Multi-AI Check-In Room & Timeclock
When collaborating with other models (Codex, Gemini, Cursor) on the same codebase:
- Check active shifts: `capsule room`
- Clock in when starting work:
  ```bash
  capsule clock-in --task "Implement email OTP auth" --files "src/auth/otp.py,tests/test_otp.py"
  ```
  *(Claude Code environment is auto-detected as Anthropic / Claude 3.7 Sonnet)*
- Monitor shifts and avoid scope drift: `capsule spy .`
- Clock out upon successful verification:
  ```bash
  capsule clock-out --summary "OTP auth implemented and verified with capsule check"
  ```

---

## 4. The Verification Gate (Trunks' Rule)

Before ending your Claude Code session or accepting code changes, ensure Claude executes:

```bash
capsule check .      # Everyday factual checks (tests, lint, typecheck, secrets)
capsule verify .     # Strict verification gate
capsule security .   # Security scanner
capsule attack .     # Red team adversarial attack scan
```

All must report green with exit code 0.
