# Situation: Something failed

Use this recipe before changing code in response to a confusing command result.

## First identify the failing layer

```bash
capsule list
capsule test
capsule verify /path/to/project
capsule security /path/to/project
capsule attack /path/to/project
```

Read the exit code as well as the printed report. A failed child command should now produce a non-zero `capsule` exit code.

## Common cases

### `capsule` is not found

Run the binary directly:

```bash
/path/to/capsule-corp/bin/capsule list
```

Then add `capsule-corp/bin` to your shell `PATH` if that is appropriate for your machine.

On Windows, use the checked-in launcher from PowerShell or Command Prompt:

```powershell
.\bin\capsule.cmd list
```

If that fails, run the doctor command to diagnose your environment:

```powershell
.\bin\capsule.cmd doctor
```

The `config/*.sh` synchronization scripts require Git Bash, WSL, or another Bash environment on Windows.

### `capsule verify` says no test runner was found

Add or configure the project’s native test runner (Go, Node, Python, or Rust). If this is a deliberate documentation/configuration-only check, ensure the repository has a supported manifest (`go.mod`, `package.json`, `Cargo.toml`, etc.).

### `capsule security` reports exposed credentials

If `capsule security` detects secrets or high-entropy tokens:
1. Move the secret to an environment variable or secure vault.
2. Remove the hardcoded secret from tracked files.
3. Rerun `./bin/capsule security .` to verify 0 exposed secrets remain.

### Sync refuses to replace a target

This is a safety stop. Inspect the target, run `capsule sync --dry-run`, then use `capsule sync --force` only if replacement is intended.

### Security reports a missing audit tool

Install the scanner required by the project’s manifest. Do not reinterpret “tool unavailable” as “no vulnerabilities.”

### A generated bot is rejected

Use lowercase kebab-case for `--name`, such as `api-sentinel`. Do not use slashes, `..`, spaces, or uppercase characters.
