# Situation: I do not know who to ask

Start with **Whis** when the request is unclear. Whis is the front door for routing and is responsible for clarifying ownership instead of guessing.

## Use the Router for Suggestions

From the Capsule Corp repository or an installed package:

```bash
capsule route "I need an accessible onboarding flow with clear error states"
```

The router treats classification as a **heuristic suggestion**, giving host AIs and developers the freedom to choose the right workflow scale. The suggested workflow is built only from the matched route's handoff chain, so a specialist request never cycles through Product, Builder, and Reviewer by default:

```text
Status: routed
Owner: videl (UX Specialist) [Suggestion]
Workflow Tier: standard_feature
Suggested Workflow: UX (@Videl) -> Product (@Bulma) -> Coordinator (@Piccolo) -> Verification (capsule check)
Intent: user_experience
Reason: Matched: onboarding.
Handoff: videl -> bulma -> piccolo
```

Or for a small fix:

```bash
capsule route "fix button alignment bug in login view"
```

Output:
```text
Status: routed
Owner: goku (Builder) [Suggestion]
Workflow Tier: small_fix
Suggested Workflow: Builder (@Goku) -> Verification (capsule check)
Intent: implementation
Reason: Matched: fix, bug.
Handoff: goku -> trunks
```

## Routing Heuristics

### Core 4 Default Roles
- **Product (`@Bulma`):** Product scope, MVP, requirements, API contracts, acceptance criteria.
- **Builder (`@Goku`):** Implementation, bugfixes, code edits with Ultra Instinct focus.
- **Reviewer (`@Trunks`):** Tests, linters, typechecks, diff integrity.
- **Coordinator (`@Piccolo` / `@Whis`):** Task decomposition, epic orchestration, request triage.

### Optional Specialists (Called On-Demand Only)
- **UX (`@Videl`):** Accessibility, user journey, interaction and error states.
- **Security (`@Android-17`):** Auth, secrets, CVEs, OWASP patterns.
- **Red Team (`@Cell`):** Adversarial attacks, prompt injection fuzzing, ReDoS, BOLA, penetration testing.
- **Watchdog (`@King-Kai`):** Telepathic supervisor catching scope drift, rogue edits, and stalled shifts.
- **Refactoring (`@Android-18`):** Dead code cleanup, technical debt.
- **Infra (`@Vegeta`):** Docker, CI/CD, database migrations, connection pooling.
- **Game (`@Roshi`):** Game loops, canvas mechanics, sprite math.
- **Polish (`@Zarbon`):** Visual aesthetics, typography, micro-interactions, theme design.
- **Hype (`@Hercule`):** README hooks, launch announcements, marketing copy, social distribution.
- **Meta (`@Dr-Gero`):** Scaffolding bots and skills, transcript friction auditing.
- **Animation (`@Goten`):** Articulated sprite sequences, frame timing, clear gameplay hitbox reading.
- **Rig Integration (`@Android-16`):** Rive character rig validation, artboard and state-machine contract checks.

If the router reports `needs_clarification`, Whis will triage and ask for clarification rather than making a random guess between tied specialists. Host AIs may also override routing based on the developer's instructions.

## You are ready when

- One owner is named.
- The requested outcome and scope are written down.
- The handoff chain is explicit.
- Acceptance criteria and verification are assigned before implementation begins.
