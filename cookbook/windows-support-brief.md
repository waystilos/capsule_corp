# Whis Crew Brief: Windows Capsule Support

## Problem

The Unix shell executable `./bin/capsule` is not a native Windows entry point. Windows developers need an explicit launcher and commands that work in PowerShell or Command Prompt.

## Crew assignments

- **Goku:** maintain the Windows launcher and keep its exit code aligned with the Go CLI.
- **Bulma:** document the Windows first-run path in the root README and cookbook.
- **Vegeta:** manage CI/CD matrix runners for Windows (`windows-latest`).
- **Trunks:** verify commands on Windows CI runner with automated tests and gates.
- **Android 17:** review the launcher and docs for unsafe path handling or shell injection.

## Implementation

Use the checked-in `bin/capsule.cmd` launcher:

```powershell
.\bin\capsule.cmd list
```

It compiles and executes `bin\capsule-go.exe` directly with native Windows process management, preserving standard exit codes.

## Documentation requirements

- Show both PowerShell/Command Prompt syntax and Unix syntax.
- Explain that `config/*.sh` sync scripts require Git Bash, WSL, or another Bash environment on Windows.
- Do not tell Windows users to run `export PATH=...`; show the PowerShell session equivalent or point them to the Windows PATH settings.
- Keep the local launcher path available; do not require global installation for first use.

## Acceptance criteria

1. `bin\capsule.cmd list` compiles and executes `bin\capsule-go.exe` on Windows.
2. It exits non-zero with a useful message when Go is not installed during compile.
3. The root README has a Windows quick start.
4. The cookbook has a Windows troubleshooting path.
5. All Go tests and verification checks remain green on `windows-latest`.
