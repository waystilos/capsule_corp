# Bulma Brief: Root README Onboarding

## Goal

Someone who has never used Capsule Corp should understand what must be installed, run the CLI locally, connect a project, preview global changes, and verify the result without guessing.

## Proposed README section

### Getting started

Capsule Corp does not require a system-wide installation. Clone the repository and run the local executable:

```bash
git clone <repository-url>
cd capsule-corp
./bin/capsule list
```

#### Prerequisites

- Python 3.8 or newer
- Git, for diff and change verification
- PyYAML for the full test suite and formatted registry output:

  ```bash
  python3 -m pip install PyYAML
  ```

Project-specific tools such as `pytest`, `npm`, `cargo`, or `go` are only needed when verifying a project that uses them.

#### Run the built-in checks

```bash
./bin/capsule test
./bin/capsule verify .
./bin/capsule security .
```

All three commands must exit with code 0 before treating the local setup as ready.

#### Use `capsule` without `./bin/`

For the current shell session:

```bash
export PATH="$PWD/bin:$PATH"
capsule list
```

To make that permanent, add the equivalent `export PATH=...` line to the shell startup file you use. The repository’s sync command can help configure supported AI tools, but it should be previewed first.

#### Connect a project

```bash
./bin/capsule init --tool copilot /path/to/project
./bin/capsule verify /path/to/project
./bin/capsule security /path/to/project
```

`init` installs only the selected integration and preserves unrelated instruction files. Configure several tools explicitly with `--tools`. Replacing selected guidance requires an explicit choice:

```bash
./bin/capsule init --tool copilot --force /path/to/project
```

#### Sync AI-tool skills and rules safely

Preview first:

```bash
./bin/capsule sync --dry-run
```

Apply global changes only after reviewing the preview:

```bash
./bin/capsule sync --force
```

Forced replacements create timestamped backups. Do not run global sync on a shared machine without checking the target paths.

#### Optional package installation

The repository provides a standard Python package entry point for developers who prefer a global command:

```bash
python3 -m pip install --user /path/to/capsule-corp
capsule list
```

When `pipx` is available, prefer an isolated install:

```bash
pipx install /path/to/capsule-corp
capsule list
```

The local `./bin/capsule` path remains available for source checkouts.

## Goku handoff

Implement the README section above and make the documented future path true.

### Acceptance criteria

1. A fresh clone has a clearly visible first command using `./bin/capsule`.
2. README names Python, Git, and PyYAML prerequisites and explains why each is needed.
3. README documents local execution, temporary PATH setup, and permanent PATH setup without editing shell files automatically.
4. README distinguishes `init` from `sync` and documents `--force` and `--dry-run` safety behavior.
5. README documents the exact `test`, `verify`, and `security` commands and their expected exit-code requirement.
6. Add a `capsule doctor` command or revise the README until it no longer promises a command that does not exist.
7. Add or update tests for the package entry point, missing optional dependencies, PATH guidance, and safe first-run behavior.
8. Run `capsule test`, `capsule verify`, and `capsule security` after the README and packaging changes.

### Non-goals

- Do not redesign the agent roster.
- Do not make global sync automatic during installation.
- Do not silently modify `.zshrc`, `.bashrc`, or other shell startup files.
