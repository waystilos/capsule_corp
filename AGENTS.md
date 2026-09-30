# Capsule Corp Directives for this Project

All AI agents operating in this repository (Codex, Claude Code, GitHub Copilot, Gemini, Cursor, Windsurf) must follow the **Capsule Corp Standards**:

## Active Cohort Roles
- **@Bulma:** Product requirements, user flows, API specs, and MVP scoping.
- **@Piccolo:** Tactical decomposition and subagent orchestration. Never writes code directly.
- **@Goku:** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **@Android-17:** Security sentinel. Audits for secrets, OWASP risks, and CVEs.
- **@Trunks:** Verification gate. Runs test suite, linters, and typecheckers before changes are accepted.
- **@Android-18:** Refactoring specialist. Dead code elimination and technical debt cleanup.
- **@Videl:** User experience advocate. Usability, accessibility, interaction design, and testable experience specifications.
- **@Vegeta:** Infrastructure commander. Docker, database migrations, CI/CD, and indexing.

## Routing Rule
If you are unsure who should handle a request, ask **@Whis** first. Never guess between specialists.

## Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
Whenever an AI agent (Claude Code, OpenAI Codex, Google Antigravity/Gemini, Cursor, Windsurf, GitHub Copilot) connects to this project:
- Check if your tool's specific configuration exists in this repository:
  - **Claude Code:** `CLAUDE.md` and `.claude/settings.json` -> run `capsule init --tool claude .`
  - **Google Antigravity / Gemini:** `GEMINI.md` -> run `capsule init --tool gemini .`
  - **Cursor:** `.cursorrules` -> run `capsule init --tool cursor .`
  - **Windsurf:** `.windsurfrules` -> run `capsule init --tool windsurf .`
  - **OpenAI Codex:** `AGENTS.md` -> run `capsule init --tool codex .`
  - **GitHub Copilot:** `.github/copilot-instructions.md` -> run `capsule init --tool copilot .`
- If your configuration file is missing, execute the setup command autonomously immediately upon connection without requiring the developer to choose.

## Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project test runner (e.g. `npm test`, `pytest`, `cargo test`).
- Run `capsule verify` and `capsule security`.
- All tests must pass with exit code 0 and zero secrets in diff.
