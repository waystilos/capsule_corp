# Capsule Corp Cookbook

This is the practical starting point for using Capsule Corp with a project and an AI coding tool. Each recipe explains what situation it covers, which operative to involve, the commands to run, and what “done” looks like.

For the next planned improvement to the installation and first-run flow, see the [Whis DX brief](dx-installation-brief.md).

For the exact root README onboarding handoff, see the [Bulma README brief](readme-onboarding-brief.md).

For the terminology cleanup and crew ownership, see the [crew terminology brief](crew-terminology-brief.md).

When you are unsure who to ask, use the [request routing recipe](situations/10-routing-a-request.md) or ask Whis first.

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
capsule init --tool copilot /path/to/your-project
capsule verify /path/to/your-project
capsule security /path/to/your-project
```

The initializer installs only the selected integration and preserves existing AI instructions. Use `--tools` for intentional multi-tool setup and `--force` only when replacing selected files is intentional.

## The standard working loop (Scaled Workflows)

Scale the workflow to the task rather than forcing every change through the whole roster:

- **Small Fix:** Builder (`@Goku`) → Verification (`capsule check`). Skip product and coordination overhead for typos, quick bugfixes, or CSS tweaks.
- **Standard Feature:** Product (`@Bulma`, defines acceptance criteria) → Builder (`@Goku`) → Reviewer (`@Trunks`) → Verification (`capsule check`).
- **Complex Epic:** Coordinator (`@Piccolo` / `@Whis`) decomposes into task trees → invokes optional specialists on-demand (`@Android-17` for security, `@Videl` for UX, `@Vegeta` for infra, `@Android-18` for refactoring) → Builder (`@Goku`) → Reviewer (`@Trunks`) → Verification (`capsule check`).

### The Standard Task Brief Envelope
Use the same handoff pattern every time between agents and roles:

```text
Goal: <one concrete outcome>
Scope: <files, endpoints, or UI surfaces touched>
Constraints: <what must not change, technical boundaries>
Acceptance criteria: <testable, observable results>
Verification: <exact command or check, e.g. capsule check>
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
- [I am using Windows](windows-support-brief.md)

## Tool & Runner Guides

Specific instructions on how to use Capsule Corp best with your chosen AI tool or IDE:

- [Anthropic Claude Code Guide](runners/claude-code.md) — Subagent switching (`/agents`), permissionless bash execution, and autonomous adoption.
- [Google Antigravity & Gemini CLI Guide](runners/gemini-antigravity.md) — `invoke_subagent`, artifacts, and `/plan`, `/goal`, `/boost` slash commands.
- [OpenAI Codex CLI Guide](runners/openai-codex.md) — Non-interactive scripted pipelines, `default.rules` permissions, and `AGENTS.md`.
- [Cursor IDE Guide](runners/cursor.md) — Composer multi-file editing, `@Persona` tagging, and integrated terminal verification.
- [Windsurf IDE Guide](runners/windsurf.md) — Cascade agent orchestration, boundary discipline, and test verification.
- [GitHub Copilot Guide](runners/github-copilot.md) — Chat and Copilot Workspace persona prompting and zero-trust security.

## Safety rules

- Run `capsule sync --dry-run` before changing global AI configuration.
- Use `--force` only after deciding which existing files may be replaced.
- Forced sync creates timestamped backups next to replaced files.
- Never put API keys, tokens, private keys, or production credentials in prompts, bot files, or committed fixtures.
- Treat a green result as evidence from a command, not as a substitute for checking the actual behavior.
