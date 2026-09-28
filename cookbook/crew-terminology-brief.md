# Whis Crew Brief: Capsule Corp-Owned Terminology

The cohort must use Capsule Corp’s own language for its operating model. Remove external names and borrowed labels from bot prompts, skills, scripts, reports, and documentation.

## Team assignments

- **Dr. Gero:** own the terminology contract and reject external framework names in new agent or skill definitions.
- **Bulma:** keep public onboarding and README language clear and Capsule Corp-specific.
- **Goku:** update implementation-facing scripts and report generators without changing observable CLI behavior.
- **Trunks:** search the repository for forbidden terminology and run the full verification gate.

## Canonical replacements

| Remove | Use |
| --- | --- |
| Borrowed quality-bar labels | Capsule Corp Quality Bar |
| Borrowed transcript-template names | Capsule Corp Transcript Healthcheck |
| External inspiration credits in runtime/docs | Capsule Corp operating principles |

## Acceptance criteria

1. No borrowed quality-bar or transcript-template names remain in active code, prompts, skills, or docs.
2. The transcript auditor’s public report and CLI behavior remain functional.
3. The 23 principles are described as Capsule Corp’s own operating system.
4. `capsule test`, `capsule verify`, and `capsule security` pass.
