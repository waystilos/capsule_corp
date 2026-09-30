# Situation: I have a feature to build

Use this recipe for any change: from a small bugfix or CSS adjustment up to a complex multi-service epic.

## Step 1: Pick the Workflow Matching Your Task

Avoid forcing every request through the entire cohort:

- **Small Fix (typo, CSS tweak, quick bugfix):** Go straight to **Builder (`@Goku`)** $\to$ **`capsule check`**. Skip product scoping and coordinator overhead.
- **Standard Feature (new endpoint, component, user flow):** **Product (`@Bulma`)** defines acceptance criteria $\to$ **Builder (`@Goku`)** implements $\to$ **Reviewer (`@Trunks`)** reviews $\to$ **`capsule check`**.
- **Complex Epic (architecture overhaul, auth migration):** **Coordinator (`@Piccolo` / `@Whis`)** deconstructs into task tree & invokes specialists $\to$ **Builder (`@Goku`)** $\to$ **Reviewer (`@Trunks`)** $\to$ **`capsule check`**.

---

## Step 2: The Standard Task Brief Envelope

When assigning work or passing tasks between roles, always format the brief using this schema:

```markdown
### Task Brief
- **Goal:** [1-2 sentences: what is being built or fixed and why]
- **Scope:** [Exact files, endpoints, or UI surfaces touched]
- **Constraints:** [Tech boundaries, no unrequested refactors, zero external dependencies]
- **Acceptance Criteria:** [Testable bullets asserting observable behaviors]
- **Verification:** [Explicit commands to run: e.g. capsule check, pytest, npm test]
```

---

## Step 3: Execution & Verification

### 1. Product Scoping (Bulma) — Standard Feature
```text
Act as Product (@Bulma). Turn this idea into an MVP spec with concrete acceptance criteria.
Define testable behaviors before code is written. Do not write implementation code.
```

### 2. Implementation (Goku) — Builder
Give Goku the Task Brief:
```text
Act as Builder (@Goku). Implement this Task Brief with Ultra Instinct focus.
Zero conversational filler, minimal diff footprint. Add behavior tests asserting observable outputs.
```

### 3. Review & Verification (Trunks) — Reviewer
```bash
capsule check /path/to/project
```

Then run strict gates before opening a PR:
```bash
capsule verify /path/to/project
capsule security /path/to/project
```

## You are ready when

- Every acceptance criterion has an automated test asserting observable behavior.
- `capsule check` passes with exit code 0.
- Diff contains zero secrets, debug markers, or unrelated files.

