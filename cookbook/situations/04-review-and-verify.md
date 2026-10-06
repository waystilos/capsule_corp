# Situation: I need a code review or release gate

Use this recipe before opening a pull request, handing work to another developer, or shipping a release.

## Everyday Checks vs Release Gates

### 1. Everyday Development Checks (`capsule check`)
Run factual checks during everyday coding to inspect tests, linters, typecheckers, and diff secrets:

```bash
capsule check /path/to/project
```

`capsule check` reports each check as `[PASS]`, `[FAIL]`, or `[SKIP]` with execution times. If configured in `capsule.json` or `pyproject.toml [tool.capsule]`, it executes your project's explicit commands rather than guessing.

### 2. Strict Release & PR Gates (`capsule verify`)
Before opening a pull request or tagging a release:

```bash
capsule verify /path/to/project
capsule security /path/to/project
capsule attack /path/to/project
capsule grill /path/to/project
git status --short
git diff --check
```

Verification inspects staged, unstaged, and untracked files for conflict markers and common exposed-secret patterns. It also runs the project’s detected or configured test suite, while `capsule attack` launches Cell's adversarial probes, and `capsule grill` executes Lord Beerus' architectural inquisition against swallowed errors and missing timeouts.

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

## Ask Lord Beerus (Inquisitor & Code Griller)

```text
Act as Lord Beerus. Conduct a ruthless architectural inquisition of this pull request:
probe for swallowed exceptions, missing timeouts, edge cases, untested code paths,
and Hakai-level code smells.
```

## Ask Android 18

Only after behavior is covered:

```text
Act as Android 18. Find dead code or duplication in the current change.
Preserve observable behavior, avoid new dependencies, and prove the refactor with tests.
```

## You are ready when

- Tests, verification, security, adversarial attack, and grill checks exit 0.
- No unexplained files or generated artifacts are in the diff.
- Review findings are either fixed or explicitly accepted.

