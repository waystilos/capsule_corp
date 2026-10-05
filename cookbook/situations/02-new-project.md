# Situation: I am connecting a new project

Use this recipe when a project should receive Capsule Corp’s AI instructions and verification workflow.

## Steps

Preview global changes first if you plan to sync the tools on your machine:

```bash
capsule sync --dry-run
```

Initialize the project:

```bash
capsule init /path/to/project
```

This creates `.github/copilot-instructions.md` containing the **Agent Self-Provisioning Rule**.

### Autonomous Agent Self-Provisioning
Whenever ANY AI agent (Claude Code, Google Antigravity/Gemini, Cursor, Windsurf, Codex) connects to an initialized project, the agent detects the Capsule Corp directives and **autonomously executes `capsule init --tool <agent> .` on its own**—installing its directive files (`CLAUDE.md`, `GEMINI.md`, `.cursorrules`, etc.) without you needing to remember or pick which tool flag to pass.

You can also auto-detect and initialize all active or installed tools upfront:

```bash
capsule init --auto /path/to/project
```

Or add specific integrations explicitly when desired:

```bash
capsule init --tools copilot,claude,codex,cursor,gemini /path/to/project
```

Validate the result:

```bash
capsule check /path/to/project       # Everyday check: tests, lint, typecheck, secrets
capsule verify /path/to/project      # Strict verification gate
capsule security /path/to/project    # Security and CVE scan
capsule attack /path/to/project      # Red team adversarial attack scan
```

### Pre-Code Idea Validation (`capsule validate`)
Before scaffolding a new project or writing code, validate the product thesis, competitor alternatives, moat, and pain severity:

```bash
capsule validate "Real-time collaborative markdown editor with CRDTs"
```

Bulma evaluates the thesis against 5 dimensions, delivering an instant GO / PIVOT / KILL verdict and score stored in `.capsule/VALIDATION.md`.

### Project-Specific Configuration (`capsule.json`)
Rather than relying on build manifest heuristics, you can explicitly configure check commands in `capsule.json`, `.capsulerc.json`, or `pyproject.toml`:

```json
{
  "test": "npm test",
  "lint": "npm run lint",
  "typecheck": "tsc --noEmit"
}
```

When present, `capsule check` executes these commands directly and reports factual `[PASS]`, `[FAIL]`, and `[SKIP]` statuses with durations.

## If the project already has instructions

Read them first. Keep the project’s conventions, then merge the useful Capsule Corp guidance manually. Use this only when you explicitly want Capsule Corp to replace those files:

```bash
capsule init --tool copilot --force /path/to/project
```

## You are ready when

- The project has configured directives (`AGENTS.md`, `.github/copilot-instructions.md`, `CLAUDE.md`, or `GEMINI.md`).
- `capsule check` runs and passes tests, linters, and diff audit.
- The project’s existing AI instructions were preserved or intentionally replaced.
