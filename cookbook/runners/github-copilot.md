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

### B. Copilot Edits with Goku & Android 18
- Use **@Goku mode** for new features: "Focus only on this function. No speculative helpers."
- Use **@Android-18 mode** for cleanups: "Refactor this legacy utility into a TypeScript pure function without changing observable behavior."

### C. Zero-Trust Security Enforcement
Copilot might autocomplete dummy secrets (e.g. `sk-test-...`).
- The directives instruct Copilot never to hardcode secrets and to use `process.env` or `os.environ`.
- Trunks' diff sentinel (`capsule security .`) catches and blocks any accidental completions before commits.
