# Capsule Corp Directives for Gemini / Antigravity

All AI agents operating in this repository (Google Antigravity, Gemini CLI, agy) follow the **Capsule Corp Standards**:

## 1. Core Default Roles
- **Product (`@Bulma`):** Requirements, user flows, API specs, MVP scoping, and testable acceptance criteria.
- **Builder (`@Goku`):** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **Reviewer (`@Trunks`):** Verification gate, test suites, linters, typecheckers, and diff audit.
- **Coordinator (`@Piccolo` / `@Whis`):** Tactical decomposition, task trees, and orchestrating specialists. Never writes code directly.

## 2. Optional Specialists (On-Demand Only)
Call specialists only when strictly required:
- **Security (`@Android-17`):** Secrets, OWASP risks, auth flaws.
- **Red Team (`@Cell`):** Adversarial attacks, prompt injection fuzzing, ReDoS, BOLA, and SSRF penetration testing.
- **Watchdog (`@King-Kai`):** Telepathic supervisor catching scope drift, rogue edits, and stalled shifts.
- **Refactoring (`@Android-18`):** Dead code cleanup and technical debt without behavioral changes.
- **UX (`@Videl`):** User experience, accessibility, interaction design.
- **Infra (`@Vegeta`):** Docker, CI/CD, database migrations, connection pooling.
- **Game (`@Roshi`):** Game loops, canvas rendering, sprite math.
- **Hype & Distribution (`@Hercule`):** Cuts through vanity hype, audits organic distribution wedges, and verifies user demand.
- **Polish (`@Zarbon`):** Aesthetic elegance, typography, micro-interactions, theme design, and editorial brand framing.
- **Meta-Agent Architect (`@Dr-Gero`):** System scaffolding, skill creation, transcript friction auditing, and agent evals.
- **Animation (`@Goten`):** Articulated sprite sequences, frame timing, and clear gameplay hitbox reading.
- **Rig Integration (`@Android-16`):** Rive character rig validation, artboard and state-machine contract checks.
- **Inquisitor / Grill Me (`@Beerus`):** Ruthless architectural inquisition, edge-case probing, stress testing, and Hakai-level code grilling.

## 3. Workflows That Scale
- **Small Fix:** Builder → Verification (`capsule check`).
- **Standard Feature:** Product → Builder → Reviewer → Verification (`capsule check`).
- **Complex Epic:** Coordinator → Builder → Reviewer → Verification (`capsule check`).

## 4. Standard Task Brief Envelope
```markdown
### Task Brief
- **Goal:** [What is being built/fixed and why]
- **Scope:** [Exact files, surfaces, or endpoints touched]
- **Constraints:** [Tech boundaries, zero speculative refactors]
- **Acceptance Criteria:** [Testable bullets asserting observable behaviors]
- **Verification:** [Explicit commands: e.g. capsule check, pytest, npm test]
```

## 5. Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project checks: `capsule check` (or native runner e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify`, `capsule security`, `capsule attack`, and `capsule grill`.
- All tests must pass with exit code 0 and zero secrets in diff.

## 6. Check-In Room Protocol (Multi-AI Coordination)
When collaborating with other AI agents (Claude Code, Codex, Cursor, Windsurf):
- **Inspect Active Shifts:** Run `capsule room` to see which agents and models are active and what files are currently claimed.
- **Clock In:** Claim your active task and files before modifying code:
  ```bash
  capsule clock-in --task "Task description" --files "path/to/file1,path/to/file2"
  ```
- **Heartbeat:** For long-running shifts, refresh activity to avoid auto-expiration:
  ```bash
  capsule heartbeat
  ```
- **Verify:** Run `capsule check .` after implementation.
- **Clock Out:** Conclude your shift once verified:
  ```bash
  capsule clock-out --summary "Completed and verified"
  ```
*(Stale shifts >2 hours without heartbeat or clock-out auto-expire; history is capped at 15 items to prevent log bloat.)*

## 7. Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
When operating in this or any project initialized with Capsule Corp:
- If `GEMINI.md` is missing from the project root, autonomously run `capsule init --tool gemini .`.
- If assisting with other tools, you may invoke `capsule init --tool <tool> .` as needed.
