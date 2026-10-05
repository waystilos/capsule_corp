# Using Capsule Corp with Cursor IDE

This guide explains how to get the most out of the **Capsule Corp Cohort** when developing inside **Cursor IDE**.

---

## 1. How Cursor Integrates with Capsule Corp

Cursor reads directives from workspace rules files and system-wide configurations:

| Layer | Path | Purpose |
| :--- | :--- | :--- |
| **Workspace Directives** | `.cursorrules` / `AGENTS.md` | Injected into Cursor Chat and Cursor Composer contexts. |
| **Global Rules** | `~/.cursorrules` | Injected across all projects opened in Cursor on your machine. |
| **Integrated Terminal** | `PATH` | Direct access to the `capsule` CLI in Cursor's built-in terminal. |

---

## 2. Quick Setup & Autonomous Onboarding

### Initialize a Project
```bash
capsule init --tool cursor /path/to/project
```
This generates a lightweight `.cursorrules` file pointing to the Capsule Corp cohort.

### Zero-Touch Auto-Adoption
When you open an initialized repository in Cursor:
- Cursor reads `AGENTS.md` or `.github/copilot-instructions.md`.
- If `.cursorrules` is missing, Cursor agent mode can autonomously run `capsule init --tool cursor .`.

---

## 3. Best Practices in Cursor

### A. Tagging Personas in Composer
Cursor's Composer is designed for multi-file editing. Tag specialist personas directly in your Composer prompt:

```text
@Piccolo Plan the migration of our database models to Prisma.
Do not write code yet; break the migration into 4 discrete tasks.
```

Once the plan is established, prompt Goku:

```text
@Goku Implement Task 1 (schema definition) only. Keep changes minimal and focused.
```

### B. Verification in Composer & Integrated Terminal
When Cursor finishes a batch of file edits:
1. Open Cursor's integrated terminal (`` Ctrl+` `` or `` Cmd+` ``).
2. Run everyday checks:
   ```bash
   capsule check .      # Factual report: tests, lint, typecheck, secrets
   ```
3. Run strict release gates before opening PRs:
   ```bash
   capsule verify .
   capsule security .
   capsule attack .
   ```
4. If issues arise, paste the check output back into Composer:
   ```text
   Fix the regression identified by Trunks above.
   ```

### C. Guarding Against Hallucinated Dependencies
Cursor may occasionally suggest installing new npm or pip packages. Enforce Goku's constraint:
- *"Zero speculative dependencies without explicit approval."* Always verify with `capsule check .`.

### D. Multi-AI Check-In Room & Timeclock
When working with Cursor alongside other agents (Claude Code, Antigravity, Codex):
- Run `capsule room` to inspect claimed files before launching Composer edits.
- Clock in to claim your working files:
  ```bash
  capsule clock-in --task "Prisma migration" --files "prisma/schema.prisma"
  ```
  *(Cursor environment is auto-detected)*
- Monitor shifts and avoid scope drift: `capsule spy .`
- Clock out once verified:
  ```bash
  capsule clock-out --summary "Prisma schema defined and verified with capsule check"
  ```

