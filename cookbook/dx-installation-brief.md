# Whis DX Brief: Install and Run Capsule Corp

## Outcome

A new developer should be able to go from “I found Capsule Corp” to “my project is wired and verified” with one obvious path, clear errors, and no silent global changes.

## Current Experience

- The standalone compiled Go binary has zero external runtime dependencies and sub-2ms startup.
- Fast system installation via `make install` or `./bin/capsule install`.
- Shell autocompletion scripts for Zsh, Bash, and Fish via `capsule completion`.
- Automated Git pre-commit verification hook via `capsule hook install`.
- Read-only diagnostics via `capsule doctor` checking Go, Git, PATH, repository tree, and legacy Python shims.
- Automated migration from legacy Python installations via `capsule sync`.

## First-Run Experience

### 1. Recommended Path: Global Install to PATH

```bash
git clone https://github.com/waystilos/capsule_corp.git
cd capsule_corp
make install
capsule doctor
capsule list
```

### 2. Zero-Install Path

Always works immediately after cloning without modifying system PATH:

```bash
git clone https://github.com/waystilos/capsule_corp.git
cd capsule_corp
./bin/capsule doctor
./bin/capsule test
./bin/capsule init --tool copilot /path/to/project
./bin/capsule verify /path/to/project
```

### 3. Service Mode Daemon

Run Capsule Corp as a background HTTP REST service daemon:

```bash
capsule serve --port 8080
```

Endpoints: `/health`, `/api/v1/room`, `/api/v1/messages`, `/api/v1/route`, `/api/v1/bots`.

## Command: `capsule doctor`

`doctor` is read-only and exits non-zero only when the local runner cannot function. It reports:

- Git version and repository status.
- Go compiler version.
- Whether `capsule` is on `PATH` and how to install it.
- Whether any conflicting legacy Python shims or packages remain on the system.
- Overall readiness state.

Example output:

```text
Capsule Corp Doctor Diagnostics:
  [OK] Git         : git version 2.53.0
  [OK] Go          : go version go1.26.0 darwin/arm64
  [OK] Repository  : Valid git repository work tree
  [OK] CLI (PATH)  : capsule command is directly available in PATH (/Users/.../bin/capsule)
  [OK] Legacy Python: No conflicting legacy Python shims or packages detected
Environment is READY.
```

## Installation Boundaries

- `doctor` checks; it does not modify files.
- `init` writes project-level instructions and preserves existing files by default.
- `sync --dry-run` previews global changes.
- `sync --force` is the explicit global mutation, migrating legacy Python packages and updating AI configs with backups.
- No command silently edits shell startup files during first run.
