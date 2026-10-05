# Situation: I am starting with Capsule Corp

Use this recipe when you have just cloned the repository or want to understand the cohort before using it on a project.

## Steps

```bash
cd /path/to/capsule-corp
capsule check .       # Factual breakdown: tests, lint, typecheck, secrets
capsule list          # Roster of roles, aliases, and model tiers
capsule test          # Cohort test suite
capsule verify .      # Strict verification gate
capsule security .    # Vulnerability & secret scanner
capsule attack .      # Cell's red team adversarial attack scan
```

If the command is not installed globally, use `./bin/capsule` from the repository root.

## Core Role Architecture

Capsule Corp operates with **four default roles** and calls **specialists only when strictly needed**:

- **Product (`@Bulma`):** Requirements, user journeys, API contracts, acceptance criteria.
- **Builder (`@Goku`):** Frontline implementation with Ultra Instinct focus. Lean code, minimal diffs.
- **Reviewer (`@Trunks`):** Verification gatekeeper: tests, linters, typechecks, diff hygiene.
- **Coordinator (`@Piccolo` / `@Whis`):** Epic decomposition and orchestrating specialists.

Optional specialists (`@Android-17` for security, `@Cell` for red team attacks, `@King-Kai` for watchdog supervision, `@Android-18` for refactoring, `@Videl` for UX, `@Vegeta` for infra, `@Roshi` for games, `@Hercule` for hype, `@Zarbon` for polish, `@Dr-Gero` for meta, `@Goten` for sprite animation, `@Android-16` for rive rigs) are invoked only on-demand.

## Ask the AI

```text
Read the Capsule Corp cookbook and summarize which operative should handle my request.
Do not change files yet. Tell me the proposed scope and verification command.
```

## You are ready when

- `capsule check .` outputs `VERDICT: PASS`.
- The internal tests pass (`capsule test`).
- Verification and security checks produce green results.
- You can identify whether a task needs a **Small Fix** (Builder $\to$ verify), **Standard Feature** (Product $\to$ Builder $\to$ Reviewer $\to$ verify), or **Complex Epic** (Coordinator $\to$ specialists $\to$ Builder $\to$ Reviewer $\to$ verify).

