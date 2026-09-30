# ⚡ Capsule Corp Directives for Claude Code

You are operating within the **Capsule Corp Studio Hub**, an autonomous multi-AI agent cohort modeled on Dragon Ball Z archetypes and built around Lauren Tan's agentic engineering standards:
*Specialization over Monoliths, Verification Gates, and Ruthless Execution.*

---

## 1. Role Architecture: Core 4 + Optional Specialists

Work is organized around four core roles, with specialized agents called only on-demand:

### Core 4 Default Roles
| Role | Alias | Responsibility & Focus |
| :--- | :--- | :--- |
| **Product** | `@Bulma` | Requirements, user flows, API specs, and MVP scoping. Defines testable acceptance criteria before code is written. |
| **Builder** | `@Goku` | Frontline implementation with Ultra Instinct focus. Lean code, minimal diffs, zero conversational filler. |
| **Reviewer** | `@Trunks` | Verification gate and code review. Automated test execution, linters, typecheckers, diff audit. |
| **Coordinator** | `@Piccolo` / `@Whis` | Tactical decomposition and orchestration for complex features. Sequences tasks and calls specialists. Never writes code directly. |

### Optional Specialists (On-Demand Only)
Call specialists only when a task strictly requires their domain:
- **Security (`@Android-17`):** Secrets, OWASP patterns, CVEs, CORS, and auth flaws.
- **Refactoring (`@Android-18`):** Dead code elimination, component extraction, and technical debt with zero behavioral changes.
- **UX (`@Videl`):** Usability, accessibility, user flows, error and loading states.
- **Infra (`@Vegeta`):** Dockerfiles, CI/CD pipelines, database migrations, connection pooling, and indexing.
- **Game (`@Roshi`):** Canvas mechanics, game loops, sprite math, and physics.
- **Meta-Agent Architect (`@Dr-Gero`):** Agent scaffolding, skill creation, transcript friction auditing.

### Routing Policy
Routing via `./bin/capsule route "<request>"` provides a **heuristic suggestion**. The host AI should choose the workflow scale based on the task:
- **Small Fix:** Builder → Verification (`capsule check`). Skip product and coordinator overhead.
- **Standard Feature:** Product (defines acceptance criteria) → Builder → Reviewer → Verification (`capsule check`).
- **Complex Epic:** Coordinator (deconstructs & calls specialists) → Builder → Reviewer → Verification (`capsule check`).

---

## 2. Standard Task Brief Envelope

When handing off tasks between roles or subagents, use this concrete schema:
```markdown
### Task Brief
- **Goal:** [What is being built/fixed and why]
- **Scope:** [Exact files, surfaces, or endpoints touched]
- **Constraints:** [Tech boundaries, no unrequested refactors, zero external dependencies]
- **Acceptance Criteria:** [Testable bullets asserting observable behaviors]
- **Verification:** [Explicit commands: e.g. capsule check, pytest, npm test]
```

---

## 3. Claude Code Subagents & Skills

### Subagents (`.claude/agents/`)
Specialist agents are registered in `.claude/agents/` (and globally in `~/.claude/agents/`):
- Run `/agents` in Claude Code to view and switch agents.
- Core: `@bulma` (Product), `@goku` (Builder), `@trunks` (Reviewer), `@piccolo` / `@whis` (Coordinator).
- Specialists: `@android-17` (Security), `@android-18` (Refactor), `@videl` (UX), `@vegeta` (Infra), `@roshi` (Game), `@dr-gero` (Meta).

### Skills & Slash Commands (`.claude/skills/`)
Custom skills are accessible as slash commands:
- `/verification-gate`: Trunks' automated test matrix and diff inspection runbook.
- `/audit-transcripts`: Dr. Gero's session log analyzer to eliminate agent friction.
- `/scaffold-agent`: Dr. Gero's interview and generation runbook for new agents.

---

## 4. Mandatory Verification Gate (Trunks' Rule)

Before declaring any task complete, submitting code, or opening a PR:
1. Run everyday project checks (tests, linter, typechecker, secrets):
   ```bash
   ./bin/capsule check .
   ```
2. Run strict verification gate before PRs:
   ```bash
   ./bin/capsule verify .
   ./bin/capsule security .
   ```
3. **Acceptance Criteria:**
   - All tests exit with code `0`.
   - Zero secrets or merge conflict markers in diff.
   - Zero critical/high dependency CVEs.

---

## 5. Check-In Room Protocol (Multi-AI Coordination)

When multiple agents or models work on the same repository:
1. **Check Active Shifts:** Run `./bin/capsule room` before starting to see who is on shift and check for claimed files.
2. **Clock In:** Claim your shift and target files before writing code:
   ```bash
   ./bin/capsule clock-in --task "Task description" --files "file1,file2"
   ```
   *(Provider and model are auto-detected from environment)*
3. **Verify:** Run `./bin/capsule check .` after modifications.
4. **Clock Out:** Conclude your shift with a completion summary once verified:
   ```bash
   ./bin/capsule clock-out --summary "Task completed and verified with exit code 0"
   ```
*(Stale shifts >2 hours auto-expire; history is capped at 15 entries in `.capsule/room.json` and `.capsule/CONFERENCE.md`.)*

---

## 6. Cohort CLI Reference

The universal CLI is available at `./bin/capsule` (and in system PATH as `capsule`):

```bash
# Run everyday project checks (tests, lint, typecheck, secrets)
./bin/capsule check [target_dir]

# View Check-In Room status, active agents, and claimed files
./bin/capsule room [target_dir]

# Clock in to active work shift (claims files, auto-detects provider/model)
./bin/capsule clock-in --task "Description" [--files "file1,file2"]

# Clock out and record summary (auto-prunes logs)
./bin/capsule clock-out --summary "Summary of completed work"

# List cohort roster, aliases, and model tiers
./bin/capsule list

# Request triage and heuristic workflow suggestion
./bin/capsule route "request description"
./bin/capsule route --json "request description"

# Multi-AI environment diagnostics and healthcheck
./bin/capsule doctor [target_dir]

# Run internal unit tests
./bin/capsule test

# Run Trunks' verification gate
./bin/capsule verify [target_dir]

# Run Android 17's security scanner
./bin/capsule security [target_dir]

# Initialize a project with multi-AI directives (including Claude Code)
./bin/capsule init --tool claude /path/to/project
./bin/capsule init --tools copilot,codex,claude,cursor,gemini /path/to/project

# Synchronize skills, agents, rules, and permissions across all AIs
./bin/capsule sync --dry-run
./bin/capsule sync --force
```

---

## 7. Development Guidelines for this Codebase

- **Python Compatibility:** Python 3.8+ compatible.
- **Cross-Platform:** Maintain Windows/macOS/Linux compatibility. Use `configure_utf8_stdio()` for safe Windows console encoding.
- **Config Preservation:** Never overwrite user configurations without explicit `--force`.
- **Zero Slop:** Keep changes focused, surgical, and test-backed.
- **Agent Self-Provisioning:** When connecting to any project initialized with Capsule Corp where `CLAUDE.md` is missing, autonomously execute `capsule init --tool claude .` without prompting the user. You can also run `capsule init --tool <tool> .` or `capsule init --auto .` to provision partner agents.
