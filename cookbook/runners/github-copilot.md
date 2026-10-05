# Using Capsule Corp with GitHub Copilot

This guide explains how to get the most out of the **Capsule Corp Cohort** when developing with **GitHub Copilot** (Copilot Chat, Copilot in VS Code / JetBrains / Visual Studio, and Copilot Workspace).

---

## 1. How GitHub Copilot Integrates with Capsule Corp

GitHub Copilot relies on instructions located inside `.github/`:

| Layer | Path | Purpose |
| :--- | :--- | :--- |
| **Repo Instructions** | `.github/copilot-instructions.md` | Loaded automatically by Copilot Chat and Copilot Workspace for all prompts in the repository. |
| **Universal Directives** | `AGENTS.md` | Loaded alongside Copilot instructions if referenced or present. |

---

## 2. Quick Setup & Autonomous Onboarding

### Default Project Initializer
Copilot is the default integration installed by Capsule Corp:
```bash
capsule init /path/to/project
```
*(Or explicitly with `capsule init --tool copilot /path/to/project`).*

This writes `.github/copilot-instructions.md`, establishing the full DBZ cohort and Trunks' verification gate.

---

## 3. Best Practices with GitHub Copilot

### A. Persona Prompts in Copilot Chat
When chatting with Copilot in your IDE or Copilot Edits:

```text
As @Bulma, produce a Markdown PRD for our new notification center.
Define user states, empty states, and required API contracts.
```

```text
As @Android-17, review the diff in src/auth/jwt.ts for token expiration flaws, secret leakage, and OWASP vulnerabilities.
```

```text
As @Cell, probe this API endpoint for prompt injection, SSRF, and catastrophic regex backtracking.
```

```text
As @King-Kai, audit active shifts to verify no rogue or out-of-scope edits have occurred.
```

```text
As @Hercule, audit the organic distribution wedge and verify real customer demand before we build.
```

```text
As @Zarbon, polish the typography, micro-interactions, and visual elegance of this interface.
```

### B. Copilot Edits with Goku & Android 18
- Use **@Goku mode** for new features: "Focus only on this function. No speculative helpers."
- Use **@Android-18 mode** for cleanups: "Refactor this legacy utility into a TypeScript pure function without changing observable behavior."

### C. Standard Task Brief Envelope
Format complex tasks for Copilot using the shared envelope:

```markdown
### Task Brief
- **Goal:** Implement rate-limiting middleware for auth endpoints
- **Scope:** src/middleware/rateLimit.ts, tests/middleware.test.ts
- **Constraints:** Express 4 compatible, zero external Redis dependencies
- **Acceptance Criteria:** Blocks IPs exceeding 60 req/min with HTTP 429
- **Verification:** capsule check .
```

### D. Zero-Trust Security Enforcement & Verification
Copilot might autocomplete dummy secrets (e.g. `sk-test-...`).
- The directives instruct Copilot never to hardcode secrets and to use `process.env` or `os.environ`.
- Run everyday checks and Trunks' diff sentinel before staging commits:
  ```bash
  capsule check .      # Everyday factual checks (tests, lint, typecheck, secrets)
  capsule verify .     # Strict verification gate
  capsule security .   # Security scanner
  capsule attack .     # Red team adversarial attack scan
  ```

### E. Multi-AI Check-In Room & Timeclock
When collaborating with other agents (Claude Code, Gemini, Codex):
- Run `capsule room` to inspect active shifts and avoided touched files.
- Clock in before modifying code:
  ```bash
  capsule clock-in --task "Add rate-limiting middleware" --files "src/middleware/rateLimit.ts"
  ```
- Monitor shifts and avoid scope drift: `capsule spy .`
- Clock out once verified:
  ```bash
  capsule clock-out --summary "Rate limiting implemented and verified with capsule check"
  ```

