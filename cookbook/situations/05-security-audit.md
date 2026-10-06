# Situation: I need a security audit

Use this recipe before sharing a branch, deploying, or investigating a suspected secret or vulnerability.

## Run Android 17 (Defensive Security Scan)

```bash
capsule security /path/to/project
```

The scanner checks common API-key/private-key patterns, selected dangerous code patterns, and supported dependency manifests.

For machine-readable output:

```bash
capsule security --json /path/to/project
```

## Run Cell (Offensive Red Team Attack Scan)

```bash
capsule attack /path/to/project
```

The offensive scanner actively attempts prompt injection payloads, ReDoS algorithmic complexity attacks, BOLA / authorization bypasses, SSRF vulnerabilities, and unauthenticated endpoints.

For machine-readable attack findings:

```bash
capsule attack --json /path/to/project
```

## Run Lord Beerus (Architectural Inquisition & Grilling)

```bash
capsule grill /path/to/project
```

Lord Beerus audits the git diff and untracked files for architectural flaws: swallowed exceptions, missing HTTP/subprocess timeouts, and untested logic.

## Ask Android 17 (Defensive Audit)

```text
Act as Android 17. Audit this project for leaked secrets,
injection risks, dangerous dynamic execution, permissive CORS,
dependency vulnerabilities, and authentication weaknesses.
Report severity, file:line, evidence, and a concrete remediation.
Do not suppress findings and do not modify feature code.
```

## Ask Cell (Offensive Attack & Fuzzing)

```text
Act as Cell. Launch adversarial attacks against this project.
Attempt prompt injection evasions, ReDoS inputs, BOLA privilege
escalation, and edge-case payload fuzzing. Produce concrete proof-of-concept
payloads and exploit chains that expose weaknesses before attackers do.
```

## Ask Lord Beerus (Inquisition & Grilling)

```text
Act as Lord Beerus. Interrogate the architecture and code diff for structural
weaknesses: swallowed errors, unbounded loops, missing network timeouts, and
untested new symbols. Apply Hakai-level scrutiny.
```

## If a scanner is unavailable

Treat the result as incomplete, not clean. Install the project’s required audit tooling or record why the gate is blocked. A missing dependency scanner or security gate failure blocks release.

## You are ready when

- No secrets are present in tracked, staged, or untracked project files (`capsule security`).
- Cell's adversarial attack scan passes with zero high/critical vulnerabilities (`capsule attack`).
- Lord Beerus' architectural inquisition passes with divine approval (`capsule grill`).
- Dependency audit tooling ran successfully where a manifest exists.
- High- and critical-severity findings are resolved or explicitly blocked from release.


