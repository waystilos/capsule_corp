# Situation: Something failed

Use this recipe before changing code in response to a confusing command result.

## First identify the failing layer

```bash
capsule list
capsule test
capsule verify /path/to/project
capsule security /path/to/project
```

Read the exit code as well as the printed report. A failed child command should now produce a non-zero `capsule` exit code.

## Common cases

### `capsule` is not found

Run the binary directly:

```bash
/path/to/capsule-corp/bin/capsule list
```

Then add `capsule-corp/bin` to your shell `PATH` if that is appropriate for your machine.

### `capsule verify` says no test runner was found

Add or configure the project’s native test runner. If this is a deliberate documentation/configuration-only check, use:

```bash
capsule verify --skip-tests /path/to/project
```

### Sync refuses to replace a target

This is a safety stop. Inspect the target, run `capsule sync --dry-run`, then use `capsule sync --force` only if replacement is intended.

### Security reports a missing audit tool

Install the scanner required by the project’s manifest. Do not reinterpret “tool unavailable” as “no vulnerabilities.”

### A generated bot is rejected

Use lowercase kebab-case for `--name`, such as `api-sentinel`. Do not use slashes, `..`, spaces, or uppercase characters.

