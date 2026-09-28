# Capsule Corp Cookbook

This is the practical starting point for using Capsule Corp with a project and an AI coding tool. Each recipe explains what situation it covers, which operative to involve, the commands to run, and what “done” looks like.

For the next planned improvement to the installation and first-run flow, see the [Whis DX brief](dx-installation-brief.md).

For the exact root README onboarding handoff, see the [Bulma README brief](readme-onboarding-brief.md).

## The five-minute start

From this repository:

```bash
cd /path/to/capsule-corp
./bin/capsule list
./bin/capsule test
```

If `capsule` is already on your `PATH`, omit `./bin/`.

To wire a project into the cohort:

```bash
capsule init /path/to/your-project
capsule verify /path/to/your-project
capsule security /path/to/your-project
```

The initializer preserves existing AI instructions. Use `--force` only when replacing them is intentional.

## The standard working loop

1. Ask **Bulma** to turn the idea into a small PRD with acceptance criteria.
2. Ask **Piccolo** to decompose the work into bounded tasks.
3. Ask **Goku** to implement one task at a time.
4. Ask **Android 17** to inspect secrets, dependencies, and security risks.
5. Ask **Trunks** to run tests and inspect the diff.
6. Ask **Android 18** only when the goal is behavior-preserving cleanup.
7. Ask **Vegeta** for deployment, CI, database, or performance work.

Use the same handoff pattern every time:

```text
Goal: <one concrete outcome>
Scope: <files or subsystem>
Constraints: <what must not change>
Acceptance criteria: <observable results>
Verification: <exact command or check>
```

## Situation recipes

- [I am starting with Capsule Corp](situations/01-first-day.md)
- [I am connecting a new project](situations/02-new-project.md)
- [I have a feature to build](situations/03-feature-work.md)
- [I need a code review or release gate](situations/04-review-and-verify.md)
- [I need a security audit](situations/05-security-audit.md)
- [I need a new specialized bot](situations/06-create-a-bot.md)
- [I need to sync rules to my AI tools](situations/07-sync-tools.md)
- [I need to audit an AI transcript](situations/08-transcript-audit.md)
- [Something failed](situations/09-troubleshooting.md)

## Safety rules

- Run `capsule sync --dry-run` before changing global AI configuration.
- Use `--force` only after deciding which existing files may be replaced.
- Forced sync creates timestamped backups next to replaced files.
- Never put API keys, tokens, private keys, or production credentials in prompts, bot files, or committed fixtures.
- Treat a green result as evidence from a command, not as a substitute for checking the actual behavior.
