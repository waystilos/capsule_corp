# Situation: I have a feature to build

Use this recipe for a new feature, integration, endpoint, UI flow, or data change.

## 1. Scope it with Bulma

```text
Act as Bulma. Turn this idea into an MVP PRD.
Include the user journey, data entities, API contracts, acceptance criteria,
and explicit out-of-scope items. Do not write implementation code.
```

## 2. Decompose it with Piccolo

```text
Act as Piccolo. Read the PRD and break it into atomic tasks.
For each task, name the files or subsystem, dependencies, owner, expected output,
and exact verification command. Keep each task independently testable.
```

## 3. Implement with Goku

Give Goku one bounded task:

```text
Act as Goku.
Task: <one atomic task>
Files in scope: <paths>
Acceptance criteria: <literal observable behavior>
Do not change unrelated files. Add behavior-focused tests and run the test command.
```

## 4. Verify before expanding scope

After each task:

```bash
capsule verify /path/to/project
```

Then ask Android 17 and Trunks to review the result before starting the next task.

## You are ready when

- Every acceptance criterion has a test or a documented manual check.
- The diff is limited to the intended scope.
- Security and verification gates are green.

