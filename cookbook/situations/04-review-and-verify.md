# Situation: I need a code review or release gate

Use this recipe before opening a pull request, handing work to another developer, or shipping a release.

## Run the gates

```bash
capsule verify /path/to/project
capsule security /path/to/project
git status --short
git diff --check
```

Verification inspects staged, unstaged, and untracked files for conflict markers and common exposed-secret patterns. It also runs the project’s detected test suite.

If there is intentionally no test runner, make the decision explicit:

```bash
capsule verify --skip-tests /path/to/project
```

Do not use `--skip-tests` as a substitute for adding tests when the project can support them.

## Ask Trunks

```text
Act as Trunks. Review the current project state.
Run the native tests, inspect staged/unstaged/untracked changes,
and report exact failing commands and file locations. Do not modify product code.
```

## Ask Android 18

Only after behavior is covered:

```text
Act as Android 18. Find dead code or duplication in the current change.
Preserve observable behavior, avoid new dependencies, and prove the refactor with tests.
```

## You are ready when

- Tests, verification, and security checks exit 0.
- No unexplained files or generated artifacts are in the diff.
- Review findings are either fixed or explicitly accepted.

