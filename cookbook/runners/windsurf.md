# Using Capsule Corp with Windsurf IDE

This guide explains how to get the most out of the **Capsule Corp Cohort** when developing inside **Windsurf IDE** (by Codeium).

---

## 1. How Windsurf Integrates with Capsule Corp

Windsurf’s **Cascade** engine utilizes workspace and global directive files to maintain operational constraints:

| Layer | Path | Purpose |
| :--- | :--- | :--- |
| **Workspace Directives** | `.windsurfrules` / `AGENTS.md` | Guides Cascade's context during autonomous multi-file workflows. |
| **Global Rules** | `~/.windsurfrules` | System-wide Capsule Corp constraints synchronized by `capsule sync`. |
| **Cascade Terminal** | Built-in Terminal | Direct execution of `capsule` commands. |

---

## 2. Quick Setup & Autonomous Onboarding

### Initialize a Project
```bash
capsule init --tool windsurf /path/to/project
```
This generates `.windsurfrules` with Capsule Corp specialist boundaries.

### Zero-Touch Auto-Adoption
When you open an initialized repository in Windsurf:
- Cascade inspects the workspace rules.
- If `.windsurfrules` is missing, Cascade detects the Capsule Corp directives in `AGENTS.md` and executes `capsule init --tool windsurf .` autonomously.

---

## 3. Best Practices in Windsurf (Cascade)

### A. Directing Cascade with DBZ Archetypes
In Windsurf’s Cascade chat, define the operating role:

```text
Follow the @Goku standard: implement the payment webhook handler in src/api/webhooks.ts.
Do not alter unrelated files or refactor existing logic. Include unit tests.
```

### B. Enforcing Boundaries on Cascade Runs
Cascade has broad agency to navigate and alter directories. Keep it on track by enforcing Capsule Corp principles:
- **`laziness-protocol`:** Enforce smallest-possible diffs.
- **`boundary-discipline`:** Confine input validation to the system edge.
- **`prove-it-works`:** Always request that Cascade execute the test suite in the terminal before marking a task complete.

### C. The Trunks Gate
Ask Cascade to execute:
```bash
capsule verify .
capsule security .
```
And verify that the diff contains 0 secret patterns and 0 regressions.
