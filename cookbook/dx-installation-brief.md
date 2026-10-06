# Whis DX Brief: Install and Run Capsule Corp

## Outcome

A new developer should be able to go from “I found Capsule Corp” to “my project is wired and verified” with one obvious path, clear errors, and no silent global changes.

## Current friction

- The README assumes `capsule` is already on `PATH`.
- The direct fallback is `./bin/capsule`, but users must discover it.
- There is no read-only command that checks Python, Git, optional dependencies, PATH, or supported project tooling.
- “Installing Capsule” and “initializing a project” are different operations but are easy to confuse.
- Global synchronization changes home-directory configuration, so it needs an explicit preview and explanation.

## Proposed first-run experience

### Zero-install path

This must always work after cloning:

```bash
cd capsule-corp
./bin/capsule doctor
./bin/capsule test
./bin/capsule init --tool copilot /path/to/project
./bin/capsule verify /path/to/project
```

The output should say that `./bin/capsule` is the supported local runner and show the optional PATH setup only after the first successful check.

### Standalone compiled Go binary (Zero-dependency & Service Mode)

For production environments, containerized agents, or CI pipelines, compile the standalone Go binary:

```bash
cd capsule-corp
go build -o bin/capsule-go ./cmd/capsule
./bin/capsule-go doctor
./bin/capsule-go check .
./bin/capsule-go serve --port 8080 # run as HTTP REST service
```

### Optional global command

Install the compiled binary directly into your `$GOPATH/bin` or standard system path:

```bash
go install ./cmd/capsule
capsule doctor
```

The local `./bin/capsule` path remains the zero-configuration fallback and works autonomously without any global installation.

## Command: `capsule doctor`

`doctor` is read-only and exits non-zero only when the local runner cannot function. It reports:

- Go toolchain version and runtime diagnostics.
- Whether embedded assets and YAML registry load correctly.
- Whether Git is available for workspace verification.
- Whether `capsule` is on `PATH` and how to add it.
- Whether the current directory looks like a supported project.
- Which verification and security tools are detected.
- The exact next command to run.

Example successful output:

```text
Capsule Corp doctor: READY
Runner: ./bin/capsule (Go standalone)
Go: go1.26.0 darwin/arm64
Git: available
Project: detected
Next: ./bin/capsule check .
```

Example blocked output:

```text
Capsule Corp doctor: NEEDS ATTENTION
Problem: Git was not found
Fix: Install Git and rerun ./bin/capsule doctor
```

## Installation boundaries

- `doctor` checks; it does not modify files.
- `init` writes project-level instructions and preserves existing files by default.
- `sync --dry-run` previews global changes.
- `sync --force` is the explicit global mutation and creates backups.
- No command should silently edit shell startup files during first run.

## Handoff to Goku

Implement in this order:

1. Add `capsule doctor` with deterministic checks and exit codes.
2. Add packaging metadata and a console-script entry point without breaking `./bin/capsule`.
3. Update the README and cookbook to use the doctor-first flow.
4. Add integration tests for missing Go/Git/PATH conditions and successful local execution.
5. Run `capsule test`, `capsule verify`, and `capsule security`.

## Acceptance criteria

- A fresh clone has one discoverable, working first command.
- A user can distinguish local execution, package installation, project initialization, and global synchronization.
- Every setup failure includes a concrete fix and the next command.
- First-run checks do not mutate the user’s home directory or project.
- The existing commands and direct `./bin/capsule` workflow remain compatible.

## Non-goals for the first pass

- No interactive wizard that edits shell configuration automatically.
- No mandatory cloud account, plugin, or AI provider connection.
- No redesign of the bot roster or agent responsibilities.
