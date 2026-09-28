# The 23 Capsule Corp Principles
Adapted from Lauren Tan's (@poteto) `pstack` at SpaceXAI / Cursor.

These 23 principles govern all engineering and agent design across the Capsule Corp cohort.

---

## 1. Core Principles
1. **laziness-protocol:** Bias toward deletion and the smallest change that solves the problem.
2. **foundational-thinking:** Apply before writing logic: choose core types and data structures first, sequence scaffold vs feature work, identify what concurrent actors share. Get data structures right so downstream code becomes obvious.
3. **redesign-from-first-principles:** Redesign as if the requirement had been a foundational assumption from day one, instead of bolting it on.
4. **attack-the-premise:** When two or more fixes sharing one premise have failed the same gate, question the premise instead of writing another fix that assumes it.
5. **subtract-before-you-add:** Remove dead weight, redundant validators, and stub references first, then build on the simpler base.
6. **minimize-reader-load:** Count layers between question and answer, and hidden state in the reader's head; collapse one-caller wrappers and shrink mutable scope.
7. **outcome-oriented-execution:** Converge on the target architecture; don't preserve smooth intermediate states with throwaway compatibility code.
8. **experience-first:** Choose user delight over implementation convenience; ship fewer polished features over more rough ones.
9. **exhaust-the-design-space:** Build 2-3 competing prototypes and compare side by side before committing.
10. **build-the-lever:** For any non-trivial work, build the tool that does it or proves it (script, generator, codemod, or skill) instead of working by hand. The tool is the artifact a reviewer can rerun.

---

## 2. Architecture Principles
11. **model-the-domain:** Encode the domain in a structure instead of scattered conditionals.
12. **boundary-discipline:** Concentrate guards at system boundaries (CLI, config, network, external APIs); trust internal types and keep business logic in pure functions.
13. **type-system-discipline:** Make illegal states unrepresentable, brand semantic primitives, parse external data at boundaries, refuse to lie to the compiler, exhaust variants.
14. **make-operations-idempotent:** Converge to the same end state regardless of partial prior runs.
15. **migrate-callers-then-delete-legacy-apis:** Migrate callers and delete the old API in the same wave instead of preserving compatibility layers.
16. **separate-before-serializing-shared-state:** Eliminate sharing first; serialize structurally only when one shared writer is a real invariant.

---

## 3. Verification Principles
17. **prove-it-works:** Verify against the real artifact (run the feature, read the actual value, inspect the diff), not a proxy, self-report, or "it compiles."
18. **fix-root-causes:** Trace each symptom to its root cause and fix it there; reproduce first, ask why until you reach it, resist nil-check guards that silence crashes.
19. **sequence-verifiable-units:** Break work into small units that each end in a verifiable state, check each before the next, and order delivery so the sequence proves itself.
20. **test-behavior-not-implementation:** Call the code the way its users do and assert the result they observe against a literal expected value.

---

## 4. Delegation & Meta Principles
21. **guard-the-context-window:** Route bulk work to subagents; keep summaries in the main thread, not raw payloads.
22. **never-block-on-the-human:** Proceed, present the result, let the human course-correct after the fact; reserve confirmation for irreversible actions.
23. **encode-lessons-in-structure:** Encode the rule as a lint, metadata flag, runtime check, or script instead of more prose text.
