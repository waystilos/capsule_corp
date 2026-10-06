# Bulma Brief: Root README Onboarding

## Goal

Someone who has never used Capsule Corp should understand what must be installed, run the CLI locally, install it to their system PATH, connect a project, preview global changes, and verify the result without guessing.

## Proposed README section

### Getting started

Capsule Corp is built in **Go 1.26+** and compiles to a zero-dependency static binary with sub-2ms startup and embedded assets (`registry.yaml`, `bots/`, `skills/`).

#### Option 1: Quick Install to PATH (Recommended)

Clone the repository and install `capsule` into your PATH:

```bash
git clone https://github.com/waystilos/capsule_corp.git
cd capsule_corp
make install
```

*(Or run `./bin/capsule install`, which copies the binary to `~/.local/bin` or `$GOPATH/bin`).*

Verify installation:

```bash
capsule list
capsule doctor
```

#### Option 2: Quick Try (Zero Installation)

```bash
git clone https://github.com/waystilos/capsule_corp.git
cd capsule_corp
./bin/capsule list
```

The `./bin/capsule` launcher (and `.\bin\capsule.cmd` on Windows) automatically compiles the Go binary (`bin/capsule-go`) on first run in <2 seconds.

#### Prerequisites

- Go 1.26 or newer (zero runtime dependencies beyond Go standard library and Git)
- Git, for diff and change verification

#### Run the built-in checks

```bash
capsule test
capsule verify .
capsule security .
capsule attack .
capsule grill .
```

All commands must exit with code 0 before treating the local setup as ready.

#### Developer Experience & Completions

Add shell autocompletions:

```bash
# Zsh
capsule completion zsh >> ~/.zshrc

# Bash
capsule completion bash >> ~/.bashrc

# Fish
capsule completion fish > ~/.config/fish/completions/capsule.fish
```

Install Git pre-commit verification gate:

```bash
capsule hook install
```

#### Connect a project

```bash
capsule init --tool copilot /path/to/project
capsule verify /path/to/project
capsule security /path/to/project
```

`init` installs only the selected integration and preserves unrelated instruction files. Configure several tools explicitly with `--tools`. Replacing selected guidance requires an explicit choice:

```bash
capsule init --tool copilot --force /path/to/project
```

#### Sync AI-tool skills and rules safely

Preview first:

```bash
capsule sync --dry-run
```

Apply global changes and migrate legacy Python installations:

```bash
capsule sync --force
```

Forced replacements create timestamped backups.

## Goku handoff

Implement the README section above and make the documented future path true.

### Acceptance criteria

1. A fresh clone has a clearly visible first command using `make install` or `./bin/capsule list`.
2. README names Go and Git prerequisites and explains why each is needed.
3. README documents global execution, completions, and pre-commit hook setup without editing shell files automatically.
4. README distinguishes `init` from `sync` and documents `--force` and `--dry-run` safety behavior.
5. README documents the exact `test`, `verify`, `security`, `attack`, and `grill` commands and their expected exit-code requirement.
6. `capsule doctor` diagnoses Go runtime, PATH availability, and legacy Python shim migrations.
7. Run `capsule check . --trust` after the README and packaging changes.

### Non-goals

- Do not redesign the agent roster.
- Do not make global sync automatic during installation.
- Do not silently modify `.zshrc`, `.bashrc`, or other shell startup files.
