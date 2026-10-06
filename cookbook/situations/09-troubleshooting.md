# Situation: Something failed

Use this recipe before changing code in response to a confusing command result.

## First identify the failing layer

```bash
capsule doctor
capsule list
capsule test
capsule verify /path/to/project
capsule security /path/to/project
capsule attack /path/to/project
```

Read the exit code as well as the printed report. A failed child command produces a non-zero `capsule` exit code.

## Common cases

### `capsule` is not found

Run the binary directly:

```bash
/path/to/capsule_corp/bin/capsule list
```

Then install `capsule` into your shell `PATH`:

```bash
make install
# or
/path/to/capsule_corp/bin/capsule install
```

On Windows, use the checked-in launcher from PowerShell or Command Prompt:

```powershell
.\bin\capsule.cmd list
```

If that fails, confirm that Go is installed:

```powershell
go version
```

The `config/*.sh` synchronization scripts require Git Bash, WSL, or another Bash environment on Windows.

### Upgrading from legacy Python version

If you see `ModuleNotFoundError: No module named 'capsule'` when invoking `capsule`, your system PATH contains a legacy Python shim. Run:

```bash
capsule sync
# or directly:
./bin/capsule sync
```

This uninstalls legacy pip packages, rehashes pyenv, and upgrades the executable on your PATH to the Go binary.

### `capsule verify` says no test runner was found

Add or configure the project’s native test runner. If this is a deliberate documentation/configuration-only check, use:

```bash
capsule verify --skip-tests /path/to/project
```

### `capsule security` reports uninstalled tool

Install the scanner required by the project’s manifest (e.g. `npm audit`, `cargo audit`, `govulncheck`, `pip-audit`). Do not reinterpret “tool unavailable” as “no vulnerabilities.”

### Sync refuses to replace a target

This is a safety stop. Inspect the target, run `capsule sync --dry-run`, then use `capsule sync --force` only if replacement is intended.

### A generated bot is rejected

Use lowercase kebab-case for `--name`, such as `api-sentinel`. Do not use slashes, `..`, spaces, or uppercase characters.
