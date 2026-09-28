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

This creates missing project-level guidance such as `AGENTS.md`, `.cursorrules`, `.windsurfrules`, and GitHub Copilot instructions. Existing files are preserved.

Validate the result:

```bash
capsule verify /path/to/project
capsule security /path/to/project
```

## If the project already has instructions

Read them first. Keep the project’s conventions, then merge the useful Capsule Corp guidance manually. Use this only when you explicitly want Capsule Corp to replace those files:

```bash
capsule init --force /path/to/project
```

## You are ready when

- The project has a clear owner for product, implementation, security, and verification work.
- Its native tests run through `capsule verify`.
- The project’s existing AI instructions were preserved or intentionally replaced.

