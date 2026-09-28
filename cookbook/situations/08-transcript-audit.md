# Situation: I need to audit an AI transcript

Use this recipe when an AI session required repeated correction, produced tool errors, or became unnecessarily long.

## Audit the latest conversation

```bash
capsule audit --latest
```

For JSON output:

```bash
capsule audit --latest --json
```

To save a report:

```bash
capsule audit --latest --output /path/to/audit.md
```

## Ask Dr. Gero

```text
Act as Dr. Gero. Review this transcript audit.
Separate user steering, tool failures, repeated work, and token bloat.
Propose the smallest structural fix, tagged [skill], [bot], or [routine].
Stay quiet when there is no actionable proposal.
```

## You are ready when

- The report includes concrete evidence from the session.
- The proposed fix addresses the recurring pattern rather than one symptom.
- The lesson is encoded in a skill, test, metadata rule, or routine when possible.

