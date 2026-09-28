# Situation: I am starting with Capsule Corp

Use this recipe when you have just cloned the repository or want to understand the cohort before using it on a project.

## Steps

```bash
cd /path/to/capsule-corp
capsule list
capsule test
capsule verify .
capsule security .
```

If the command is not installed globally, use `./bin/capsule` from the repository root.

## Ask the AI

```text
Read the Capsule Corp cookbook and summarize which operative should handle my request.
Do not change files yet. Tell me the proposed scope and verification command.
```

## You are ready when

- The roster prints successfully.
- The internal tests pass.
- Verification and security checks produce a green result.
- You can identify the owner for product, implementation, security, verification, and infrastructure work.

