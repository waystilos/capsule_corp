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
capsule verify /path/to/project
capsule security /path/to/project
```

## If the project already has instructions

Read them first. Keep the project’s conventions, then merge the useful Capsule Corp guidance manually. Use this only when you explicitly want Capsule Corp to replace those files:

```bash
capsule init --tool copilot --force /path/to/project
```

## You are ready when

- The project has a clear owner for product, implementation, security, and verification work.
- Its native tests run through `capsule verify`.
- The project’s existing AI instructions were preserved or intentionally replaced.
