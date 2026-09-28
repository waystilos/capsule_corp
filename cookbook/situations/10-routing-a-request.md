# Situation: I do not know who to ask

Start with **Whis** when the request is unclear. Whis is the front door for routing and is responsible for clarifying ownership instead of guessing.

## Use the deterministic router

From the Capsule Corp repository or an installed package:

```bash
capsule route "I need an accessible onboarding flow with clear error states"
```

The command returns the owner, intent, reason, and expected handoff chain. For example:

```text
Owner: videl
Handoff: videl -> bulma -> piccolo
```

## Routing rules

- Product scope, MVP, requirements, or API contracts → **Bulma**
- UX, accessibility, onboarding, journeys, or interaction states → **Videl**
- Task decomposition and orchestration → **Piccolo**
- Focused implementation or bug fix → **Goku**
- Tests, linting, type checks, or release verification → **Trunks**
- Security, secrets, vulnerabilities, or auth review → **Android 17**
- Behavior-preserving cleanup → **Android 18**
- Deployment, CI/CD, databases, or performance → **Vegeta**
- New bots, skills, prompts, or transcript audits → **Dr. Gero**

If the router reports `needs_clarification`, ask Whis to clarify the desired outcome before dispatching. Do not choose between tied specialists by guesswork.

## You are ready when

- One owner is named.
- The requested outcome and scope are written down.
- The handoff chain is explicit.
- Acceptance criteria and verification are assigned before implementation begins.
