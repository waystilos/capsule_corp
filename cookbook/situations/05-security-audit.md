# Situation: I need a security audit

Use this recipe before sharing a branch, deploying, or investigating a suspected secret or vulnerability.

## Run Android 17

```bash
capsule security /path/to/project
```

The scanner checks common API-key/private-key patterns, selected dangerous code patterns, and supported dependency manifests.

For machine-readable output:

```bash
capsule security --json /path/to/project
```

## Ask Android 17

```text
Act as Android 17. Audit this project for leaked secrets,
injection risks, dangerous dynamic execution, permissive CORS,
dependency vulnerabilities, and authentication weaknesses.
Report severity, file:line, evidence, and a concrete remediation.
Do not suppress findings and do not modify feature code.
```

## If a scanner is unavailable

Treat the result as incomplete, not clean. Install the project’s required audit tooling or record why the gate is blocked. A missing dependency scanner is a verification failure.

## You are ready when

- No secrets are present in tracked, staged, or untracked project files.
- Dependency audit tooling ran successfully where a manifest exists.
- High- and critical-severity findings are resolved or explicitly blocked from release.

