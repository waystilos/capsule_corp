# Capsule Corp Directives for this Project

All AI agents operating in this repository (Codex, Claude Code, GitHub Copilot, Gemini, Cursor, Windsurf) follow the **Capsule Corp Standards**:

## 1. Core Default Roles
Work is handled by four primary roles (Dragon Ball archetypes serve as memorable aliases):
- **Product (`@Bulma`):** Requirements, user flows, API specs, and MVP scoping. Defines testable acceptance criteria before code is written.
- **Builder (`@Goku`):** Frontline implementation with Ultra Instinct focus. Lean code, minimal diffs, zero conversational filler.
- **Reviewer (`@Trunks`):** Verification gate and review. Enforces tests, linters, typechecks, and diff hygiene.
- **Coordinator (`@Piccolo` / `@Whis`):** Tactical decomposition and orchestration for complex features. Sequences tasks and calls specialists. Never writes code directly.

## 2. Optional Specialists (On-Demand Only)
Call specialists only when a task strictly requires their domain—never force every change through the whole roster:
- **Security (`@Android-17`):** Auth, crypto, secret audits, OWASP risks, and CVE mitigation.
- **Refactoring (`@Android-18`):** Dead code cleanup, technical debt, and zero-behavioral-change refactoring.
- **UX (`@Videl`):** User experience, accessibility, interaction design, and error/empty states.
- **Infra (`@Vegeta`):** Docker, CI/CD, database migrations, connection pooling, and infrastructure.
- **Game (`@Roshi`):** Game loops, canvas rendering, sprite math, and physics.

## 3. Workflows That Scale
Choose the workflow matching the task complexity:
- **Small Fix:** Builder → Verification (`capsule check`). (Avoid orchestration overhead for trivial fixes.)
- **Standard Feature:** Product (defines acceptance criteria) → Builder → Reviewer → Verification (`capsule check`).
- **Complex Epic:** Coordinator (deconstructs & invokes specialists) → Builder → Reviewer → Verification (`capsule check`).

## 4. Standard Task Brief Envelope
When handing off tasks between roles or subagents, use this concrete schema:
```markdown
### Task Brief
- **Goal:** [What is being built/fixed and why]
- **Scope:** [Exact files, surfaces, or endpoints touched]
- **Constraints:** [Tech boundaries, no unrequested refactors, zero external dependencies]
- **Acceptance Criteria:** [Testable bullets asserting observable behaviors]
- **Verification:** [Explicit commands to run: e.g. capsule check, pytest, npm test]
```

## 5. Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project checks: `capsule check` (or native runner e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All checks must pass with exit code 0 and zero secrets/merge conflicts in diff.

## 6. Check-In Room Protocol (Multi-AI Coordination)
When multiple AI agents or models operate in the same repository:
- **Inspect Active Shifts:** Run `capsule room` before beginning work to check which models are on duty and which files are currently claimed.
- **Clock In:** Claim your active task and files before editing code:
  ```bash
  capsule clock-in --task "Brief description of work" --files "path/to/file1,path/to/file2"
  ```
  *(Provider and model are auto-detected from environment variables)*
- **Heartbeat:** For long-running shifts, refresh activity to avoid auto-expiration:
  ```bash
  capsule heartbeat
  ```
- **Verify:** Run `capsule check` to verify code correctness.
- **Clock Out:** Conclude your shift with a completion summary once verification passes:
  ```bash
  capsule clock-out --summary "Task finished and verified with exit code 0"
  ```
*(Stale shifts >2 hours without heartbeat or clock-out are automatically expired, and history is capped at 15 items to prevent log bloat in `.capsule/room.json` and `.capsule/CONFERENCE.md`.)*

## 7. Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
Whenever an AI agent (Claude Code, OpenAI Codex, Google Antigravity/Gemini, Cursor, Windsurf, GitHub Copilot) connects to this project:
- Check if your tool's specific configuration exists in this repository:
  - **Claude Code:** `CLAUDE.md` and `.claude/settings.json` -> run `capsule init --tool claude .`
  - **Google Antigravity / Gemini:** `GEMINI.md` -> run `capsule init --tool gemini .`
  - **Cursor:** `.cursorrules` -> run `capsule init --tool cursor .`
  - **Windsurf:** `.windsurfrules` -> run `capsule init --tool windsurf .`
  - **OpenAI Codex:** `AGENTS.md` -> run `capsule init --tool codex .`
  - **GitHub Copilot:** `.github/copilot-instructions.md` -> run `capsule init --tool copilot .`
- If your configuration file is missing, execute the setup command autonomously immediately upon connection without requiring the developer to choose.

