---
name: verification-gate
description: Runbook for Trunks to verify code changes against test suites, linters, and typecheckers before changes are accepted.
---

# Verification Gate Skill (Trunks Runbook)

Use this skill whenever code is created or modified by worker bots (like Goku) before reporting completion.

## Protocol

1. **Detect Project Ecosystem:**
   - Node / TypeScript: `package.json` $\to$ `npm test`, `npx tsc --noEmit`, `npm run lint`
   - Python: `pyproject.toml`, `pytest.ini` $\to$ `pytest`, `mypy`, `flake8`
   - Rust: `Cargo.toml` $\to$ `cargo test`, `cargo clippy`
   - Go: `go.mod` $\to$ `go test ./...`
   - Elixir: `mix.exs` $\to$ `mix test`
   - .NET / C#: `*.csproj` $\to$ `dotnet test`

2. **Execute Test Matrix:**
   - Run the primary test runner command via `run_command`.
   - Capture stderr, stdout, and exit code.

3. **Evaluate Verdict:**
   - **Exit code 0:** GREEN. Pass to Piccolo with test summary (e.g., `42 passed in 1.2s`).
   - **Exit code > 0:** RED. Intercept and format the exact failure traceback:
     ```
     [FAIL] Trunks Verification Gate Triggered
     Command: <command>
     Failed Test: <test_name>
     Error: <traceback>
     Action: Delegating back to Goku for surgical fix.
     ```

4. **Diff Verification:**
   - Ensure no extraneous files, untracked binaries, or unformatted files were left behind.
