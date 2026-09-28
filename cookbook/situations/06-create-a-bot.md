# Situation: I need a new specialized bot

Use this recipe when an existing operative has a recurring responsibility that deserves a dedicated prompt and verification gate.

## Start with the contract

Define exactly one job, explicit anti-jobs, a concise voice, allowed tools, and a deterministic verification gate. If the job is not distinct from an existing bot, improve the existing bot instead.

## See the reserve bench

```bash
capsule scaffold --list-archetypes
```

Create a reserve archetype:

```bash
capsule scaffold --from-archetype gohan
```

Or define a custom bot:

```bash
capsule scaffold \
  --name api-sentinel \
  --alias 'Api Sentinel (Contract Guardian)' \
  --role 'API Contract Specialist' \
  --description 'Checks API compatibility and schema drift.' \
  --jtbd 'Finds breaking API changes before release.' \
  --verification 'Contract tests pass with exit code 0.'
```

Names must be lowercase kebab-case. The generator rejects path traversal and escapes registry values safely.

## Verify the result

```bash
capsule list
capsule test
git diff -- bots/ registry.yaml
```

## You are ready when

- The new bot has one bounded responsibility.
- Its registry entry and persona file agree.
- The verification gate is executable, not aspirational prose.

