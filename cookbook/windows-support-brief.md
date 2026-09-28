# Whis Crew Brief: Windows Capsule Support

## Problem

The Unix executable `./bin/capsule` is not a dependable Windows entry point. A Windows developer needs an explicit launcher and commands that work in PowerShell or Command Prompt.

## Crew assignments

- **Goku:** maintain the Windows launcher and keep its exit code aligned with the Python CLI.
- **Bulma:** document the Windows first-run path in the root README and cookbook.
- **Vegeta:** decide whether global PATH/package installation and sync should support native Windows or require Git Bash/WSL.
- **Trunks:** verify commands on Windows or a Windows CI runner, including missing-Python errors.
- **Android 17:** review the launcher and docs for unsafe downloads, shell injection, or credential guidance.

## Immediate fix

Use the checked-in `bin/capsule.cmd` launcher:

```powershell
.\bin\capsule.cmd list
```

It prefers the Windows Python launcher (`py`) and falls back to `python`, preserving the Python CLI’s exit code.

Equivalent direct invocation:

```powershell
py .\bin\capsule list
```

## Documentation requirements

- Show both PowerShell/Command Prompt syntax and Unix syntax.
- Explain that `config/*.sh` sync scripts require Git Bash, WSL, or another Bash environment on Windows.
- Do not tell Windows users to run `export PATH=...`; show the PowerShell session equivalent or point them to the Windows PATH settings.
- Keep the local launcher path available; do not require global installation for first use.

## Acceptance criteria

1. `bin/capsule.cmd list` works when `py` is installed.
2. It falls back to `python` when `py` is unavailable.
3. It exits non-zero with a useful message when neither is available.
4. The root README has a Windows quick start before the general shell setup.
5. The cookbook has a Windows troubleshooting path.
6. All Python tests and verification checks remain green.

