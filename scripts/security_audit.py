#!/usr/bin/env python3
"""
Android 17's Security & Compliance Sentinel (Capsule Corp)
Automated startup security scanner:
  1. Secret detection (API keys, private keys, access tokens)
  2. Dependency vulnerability check (npm audit, cargo audit, pip-audit)
  3. Static code security scan (SQL injection patterns, eval, permissive CORS)
  4. Returns exit code 0 on clean, 1 on critical findings
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from .runtime import configure_utf8_stdio
    from . import secret_patterns as sp
except ImportError:
    from runtime import configure_utf8_stdio
    import secret_patterns as sp

configure_utf8_stdio()

# Shared with `capsule verify` / `capsule check` (scripts/secret_patterns.py).
SECRET_REGEXES = sp.SECRET_PATTERNS

# Every pattern is bounded: no unbounded `.*` (ReDoS-safe) and the scanner feeds
# them at most LINE_WINDOW characters at a time.
CODE_VULN_PATTERNS = [
    (re.compile(r"\beval\s*\(", re.IGNORECASE), "Dangerous dynamic code execution (eval)"),
    (re.compile(r"f[\"'][^\n]{0,200}?SELECT\s+[^\n]{0,200}?WHERE\s+[^\n]{0,200}?\{", re.IGNORECASE), "Possible SQL injection in formatted string query"),
    (re.compile(r"[\"']SELECT\s+[^\n]{0,200}?WHERE\s+[^\n]{0,200}?%\s*\(", re.IGNORECASE), "Possible SQL injection with % formatting"),
    (re.compile(r"Access-Control-Allow-Origin[\"']?\s*:\s*[\"']\*[\"']", re.IGNORECASE), "Overly permissive CORS policy ('*')"),
]

# Elixir / Erlang rules (applied to .ex, .exs, .erl only).
ELIXIR_VULN_PATTERNS = [
    (re.compile(r"\bCode\.eval_(?:string|quoted|file)\b"), "Dangerous dynamic code execution (Code.eval_*)"),
    (re.compile(r":erlang\.binary_to_term\s*\((?![^\n]{0,200}:safe)"), "Unsafe deserialization (:erlang.binary_to_term without [:safe])"),
    (re.compile(r"\bString\.to_atom\b"), "Atom exhaustion risk (String.to_atom on dynamic input)"),
    (re.compile(r"verify:\s*:verify_none"), "TLS certificate verification disabled (verify: :verify_none)"),
    (re.compile(r"Ecto\.Adapters\.SQL\.query!?\s*\([^\n]{0,200}#\{"), "Possible SQL injection (interpolated Ecto SQL adapter query)"),
    (re.compile(r"System\.cmd\s*\(\s*[\"'](?:/bin/|/usr/bin/)?(?:ba|z|da)?sh[\"']\s*,\s*\[\s*[\"']-c[\"']"), "Shell command execution (System.cmd sh -c)"),
    (re.compile(r"System\.cmd\s*\(\s*[\"'](?:ba|z)?sh -c"), "Shell command execution (System.cmd \"sh -c ...\")"),
]
ELIXIR_SUFFIXES = {".ex", ".exs", ".erl"}

CODE_SUFFIXES = set(sp.CODE_SUFFIXES)

# Back-compat names (tests / other tools import these).
IGNORED_DIRS = sp.VENDOR_DIRS
is_test_path = sp.is_test_path


def redact_line(line: str, pattern) -> str:
    """Mask every secret match in a line, keeping only the first 4 chars."""
    return pattern.sub(lambda m: m.group(0)[:4] + "***", line)


def _incomplete(rel: str, why: str) -> Dict[str, Any]:
    return {
        "type": "SCAN_INCOMPLETE",
        "severity": "INFO",
        "file": rel,
        "line": 0,
        "description": why,
        "snippet": "",
    }


SECRET_CHUNK_BYTES = 256 * 1024   # small chunks keep the time checks fine-grained


def scan_for_secrets(root_dir: Path, uni: Optional[Any] = None,
                     total_budget: Optional[float] = None) -> List[Dict[str, Any]]:
    """Scan every tracked/untracked-unignored file (binaries and unknown suffixes
    included) for secrets. Anything that could not be fully scanned is reported as
    a SCAN_INCOMPLETE finding rather than silently skipped."""
    findings: List[Dict[str, Any]] = []
    root_dir = Path(root_dir)
    if uni is None:
        uni = sp.collect_files(root_dir)
    for rel in uni.skipped_symlinks:
        findings.append(_incomplete(rel, "Symlink pointing outside the scan root was not followed"))
    total = sp.Deadline(total_budget)
    skipped_total = 0
    for path, rel in uni.files:
        if total.expired():
            skipped_total += 1
            continue
        info: Dict[str, Any] = {}
        started = time.monotonic()
        file_deadline = min(total.at, started + sp.SECRET_TIME_BUDGET)
        try:
            for first_line, text in sp.iter_text_chunks(path, info, chunk_bytes=SECRET_CHUNK_BYTES):
                for start, end, desc in sp.find_secrets(text, file_deadline):
                    findings.append({
                        "type": "SECRET_LEAK",
                        "severity": "CRITICAL",
                        "file": rel,
                        "line": first_line + text.count("\n", 0, start),
                        "description": desc,
                        "snippet": sp.snippet_for(text, start, end),
                    })
                if time.monotonic() > file_deadline:
                    info["truncated"] = True
                    break
        except OSError as exc:
            findings.append({
                "type": "SCAN_ERROR",
                "severity": "HIGH",
                "file": rel,
                "line": 0,
                "description": "Unable to read file during secret scan",
                "snippet": str(exc)[:80],
            })
            continue
        if info.get("truncated"):
            findings.append(_incomplete(rel, "File exceeded the secret-scan size/time cap; remainder not scanned"))
    if skipped_total:
        findings.append(_incomplete("", "Total scan time budget (%.0fs) exceeded; %d file(s) not secret-scanned"
                                    % (total.seconds, skipped_total)))
    return findings


def scan_code_vulnerabilities(root_dir: Path, uni: Optional[Any] = None,
                              total_budget: Optional[float] = None,
                              stats: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Regex code-rule scan. `stats` (optional) receives `unscanned_text`: text files whose
    suffix has no code rules (counted, never silently dropped)."""
    findings: List[Dict[str, Any]] = []
    root_dir = Path(root_dir)
    if uni is None:
        uni = sp.collect_files(root_dir)
    total = sp.Deadline(total_budget)
    skipped_total = 0
    unscanned: List[str] = []
    for path, rel in uni.files:
        suffix = path.suffix.lower()
        if suffix not in CODE_SUFFIXES:
            if suffix not in sp.KNOWN_NON_CODE_SUFFIXES and not sp.is_test_path(path, root_dir) \
                    and sp.is_text_file(path):
                unscanned.append(rel)
            continue
        if total.expired():
            if not sp.is_test_path(path, root_dir):
                skipped_total += 1
            continue
        # Test fixtures under top-level tests/ test/ spec/ __tests__/ intentionally
        # contain vulnerable-code examples. Secret scanning still includes them.
        if sp.is_test_path(path, root_dir):
            continue
        rules = list(CODE_VULN_PATTERNS)
        if path.suffix.lower() in ELIXIR_SUFFIXES:
            rules += ELIXIR_VULN_PATTERNS
        try:
            size = path.stat().st_size
            if size > sp.CODE_MAX_BYTES:
                findings.append(_incomplete(rel, "Source file exceeds the code-scan size cap (%d bytes); not scanned" % sp.CODE_MAX_BYTES))
                continue
            with open(str(path), "rb") as fh:
                content = sp.decode_bytes(fh.read(sp.CODE_MAX_BYTES + 1))
        except OSError as exc:
            findings.append({
                "type": "SCAN_ERROR",
                "severity": "HIGH",
                "file": rel,
                "line": 0,
                "description": "Unable to read file during code scan",
                "snippet": str(exc)[:80],
            })
            continue
        deadline = min(time.monotonic() + sp.FILE_TIME_BUDGET, total.at)
        lines = content.splitlines()
        timed_out = False
        for pattern, desc in rules:
            for line_idx, line in enumerate(lines, 1):
                hit = sp.search_windows(pattern, line, deadline)
                if hit is None:
                    timed_out = True
                    break
                if hit:
                    findings.append({
                        "type": "CODE_VULN",
                        "severity": "HIGH",
                        "file": rel,
                        "line": line_idx,
                        "description": desc,
                        "snippet": sp.safe_snippet(line, 80),
                    })
            if timed_out:
                break
        if timed_out:
            findings.append(_incomplete(rel, "Scan time budget exceeded; file only partially scanned"))
    if skipped_total:
        findings.append(_incomplete("", "Total scan time budget (%.0fs) exceeded; %d source file(s) not code-scanned"
                                    % (total.seconds, skipped_total)))
    if stats is not None:
        stats["unscanned_text"] = unscanned
    return findings


# Manifests we know exist but have no auditor wired up for. Their presence must
# never produce a CLEAN dependency verdict.
UNAUDITED_MANIFESTS = [
    "go.mod", "go.sum", "Gemfile", "Gemfile.lock", "poetry.lock", "Pipfile.lock", "uv.lock",
    "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock", "composer.json", "composer.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "pubspec.yaml", "Podfile", "Podfile.lock",
    "packages.lock.json", "mix.lock",
]


def _trusted_which(executable: str, root_dir: Path) -> Optional[str]:
    """shutil.which, but refuse binaries that resolve inside the audited project
    (a hostile repo could ship its own `npm`/`mix` earlier on PATH)."""
    found = shutil.which(executable)
    if found is None:
        return None
    real = os.path.realpath(found)
    root_real = os.path.realpath(str(root_dir))
    if real == root_real or real.startswith(root_real + os.sep):
        return None
    return found


_SETUP_DEP_RE = re.compile(r"\b(?:install_requires|extras_require|setup_requires|tests_require)\b")


def _pyproject_declares_deps(path: Path) -> Optional[bool]:
    """True/False for declared runtime [project].dependencies; None when it cannot be told."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        try:
            from ._config import load_toml
        except ImportError:
            from _config import load_toml
        data = load_toml(path)
    except Exception:  # unparsable TOML: fall back to the regex below
        data = None
    if isinstance(data, dict) and data:
        project = data.get("project")
        poetry = (data.get("tool") or {}).get("poetry") if isinstance(data.get("tool"), dict) else None
        if isinstance(project, dict):
            if "dependencies" in (project.get("dynamic") or []):
                return None
            deps = project.get("dependencies")
            if deps:
                return True
        if isinstance(poetry, dict):
            pdeps = poetry.get("dependencies")
            if isinstance(pdeps, dict) and any(k.lower() != "python" for k in pdeps):
                return True
        return False
    # Regex fallback (no parsed data).
    m = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    if re.search(r"^\s*dynamic\s*=.*dependencies", body, re.MULTILINE):
        return None
    d = re.search(r"^\s*dependencies\s*=\s*\[(.*?)\]", body, re.MULTILINE | re.DOTALL)
    if not d:
        return False
    return bool(re.search(r"[\"']", d.group(1)))


def _setup_py_declares_deps(path: Path) -> Optional[bool]:
    """Text-only look at setup.py (never executed)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not _SETUP_DEP_RE.search(text):
        # Absence of the keywords only proves "no deps" for a plain setup(...) call that
        # does not defer to setup.cfg or **kwargs.
        if re.search(r"\bsetup\s*\(", text) and "**" not in text and not (path.parent / "setup.cfg").exists():
            return False
        return None
    if re.search(r"\binstall_requires\s*=\s*\[\s*\]", text) and not re.search(
            r"\b(?:extras_require|setup_requires|tests_require)\b", text):
        return False
    return True


def python_declares_dependencies(root_dir: Path) -> Optional[bool]:
    """Do pyproject.toml/setup.py declare runtime dependencies? None = cannot tell."""
    results = []
    if (root_dir / "pyproject.toml").exists():
        results.append(_pyproject_declares_deps(root_dir / "pyproject.toml"))
    if (root_dir / "setup.py").exists():
        results.append(_setup_py_declares_deps(root_dir / "setup.py"))
    if any(r is True for r in results):
        return True
    if any(r is None for r in results):
        return None
    return False


def run_dependency_audit(root_dir: Path) -> Tuple[int, str]:
    """Audit every detected ecosystem. Exit 2 means INCOMPLETE: an auditor is
    missing/failed to run, or a manifest exists that nothing audits. Never CLEAN
    when a known manifest went unaudited."""
    commands = []
    unavailable = []
    notes: List[str] = []
    if (root_dir / "package.json").exists():
        commands.append(("npm", ["npm", "audit", "--audit-level=high"]))
    if (root_dir / "Cargo.toml").exists():
        commands.append(("cargo", ["cargo", "audit"]))
    if (root_dir / "mix.exs").exists():
        # NOTE: `mix` loads the project's mix.exs (Elixir code) - the same trust
        # caveat as `capsule check`: only audit repositories you trust.
        commands.append(("mix hex.audit", ["mix", "hex.audit"]))

    python_manifests = [
        root_dir / "pyproject.toml",
        root_dir / "requirements.txt",
        root_dir / "requirements-dev.txt",
        root_dir / "Pipfile",
        root_dir / "setup.py",
    ]
    if any(path.exists() for path in python_manifests):
        # pip-audit must never build the audited project (build backends / setup.py run
        # arbitrary code). Only pinned requirements files are audited, with dependency
        # resolution and pip disabled; the project directory is never passed as a path.
        requirements = [path for path in python_manifests if path.name.startswith("requirements") and path.exists()]
        if requirements:
            commands.extend(
                (f"pip-audit {path.name}", ["pip-audit", "-r", str(path), "--no-deps", "--disable-pip"])
                for path in requirements
            )
        elif ((root_dir / "pyproject.toml").exists() or (root_dir / "setup.py").exists()) \
                and python_declares_dependencies(root_dir) is False:
            notes.append("python: no declared dependencies to audit (pyproject.toml/setup.py list none)")
        elif (root_dir / "pyproject.toml").exists() or (root_dir / "setup.py").exists():
            unavailable.append(
                "pip-audit project: pyproject.toml/setup.py has no requirements file to read; "
                "auditing would build the project (code execution), so it was not audited"
            )
        else:
            unavailable.append("Pipfile: no auditor is configured for Pipfile-only projects")

    has_mix = (root_dir / "mix.exs").exists()
    for manifest in UNAUDITED_MANIFESTS:
        if manifest == "mix.lock" and has_mix:
            continue
        if (root_dir / manifest).exists():
            unavailable.append(f"{manifest}: no dependency auditor is configured for this manifest")

    if not commands and not unavailable:
        return 0, "\n".join(notes) or "No supported dependency manifest found for vulnerability audit"

    results = []
    for label, command in commands:
        executable = command[0]
        resolved = _trusted_which(executable, root_dir)
        if resolved is None:
            unavailable.append(f"{label}: {executable} is not installed (or only found inside the audited project)")
            continue
        try:
            res = subprocess.run(
                command,
                cwd=str(root_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120 if executable == "mix" else 60,
            )
            output = res.stdout or res.stderr or "(no output)"
            results.append(f"[{label}] exit {res.returncode}\n{output}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            unavailable.append(f"{label}: {exc}")

    failed = any("exit 0" not in result.splitlines()[0] for result in results)
    results.extend(notes)
    if failed:
        # A real vulnerability report outranks incompleteness.
        if unavailable:
            results.append("INCOMPLETE: " + "; ".join(unavailable))
        return 1, "\n".join(results)
    if unavailable:
        results.append("INCOMPLETE: " + "; ".join(unavailable))
        return 2, "\n".join(results)
    return 0, "\n".join(results)


def main():
    parser = argparse.ArgumentParser(description="Android 17 Security Sentinel (Capsule Corp)")
    parser.add_argument("target_dir", nargs="?", default=".", help="Directory to scan")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    project_dir = Path(args.target_dir).resolve()
    if not project_dir.exists():
        print(f"Error: Directory {project_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    uni = sp.collect_files(project_dir)
    skipped_vendor = list(uni.skipped_vendor_dirs)
    total = sp.Deadline()
    secret_findings = scan_for_secrets(project_dir, uni, total_budget=total.seconds)
    stats: Dict[str, Any] = {}
    code_findings = scan_code_vulnerabilities(project_dir, uni, total_budget=max(0.0, total.at - time.monotonic()),
                                              stats=stats)
    unscanned_text = stats.get("unscanned_text", [])
    dep_exit, dep_output = run_dependency_audit(project_dir)

    raw_findings = secret_findings + code_findings
    all_findings = [f for f in raw_findings if f["type"] != "SCAN_INCOMPLETE"]
    scan_incomplete = [f for f in raw_findings if f["type"] == "SCAN_INCOMPLETE"]
    passed = (len(all_findings) == 0) and (dep_exit == 0) and not scan_incomplete
    incomplete = (dep_exit == 2 or bool(scan_incomplete)) and not all_findings and dep_exit != 1

    if args.json:
        import json
        payload = {
            "verdict": "PASS" if passed else ("INCOMPLETE" if incomplete else "FAIL"),
            "findings": all_findings,
            "incomplete": scan_incomplete,
            "skipped_vendor_dirs": skipped_vendor,
            "unscanned_text_files": unscanned_text,
            "dependency_audit_exit": dep_exit,
            "dependency_output": dep_output[:500]
        }
        print(json.dumps(payload, indent=2))
        sys.exit(0 if passed else (2 if incomplete else 1))

    print("==================================================================")
    print(" 🛡️  ANDROID 17 SECURITY SENTINEL REPORT (CAPSULE CORP)")
    print("==================================================================")
    print(f"Target Directory: {project_dir}")
    print(f"Findings: {len(all_findings)} security issue(s) detected")
    print("------------------------------------------------------------------")

    if all_findings:
        for f in all_findings:
            print(f"[{f['severity']}] {f['description']}")
            print(f"  Location: {f['file']}:{f['line']}")
            print(f"  Snippet:  {f['snippet']}\n")
    else:
        print("  No known secret or code patterns matched (heuristic regex scan, not proof of security).")

    if scan_incomplete:
        print(f"Scan gaps: {len(scan_incomplete)} item(s) could not be fully scanned (INCOMPLETE)")
        for f in scan_incomplete[:20]:
            print(f"  ! {f['file']}: {f['description']}")
    if skipped_vendor:
        print("Skipped vendor dirs: " + ", ".join(skipped_vendor))
    if unscanned_text:
        print("Not code-scanned (text files with unrecognized suffix): %d, e.g. %s"
              % (len(unscanned_text), ", ".join(unscanned_text[:5])))
    print("------------------------------------------------------------------")
    print(f"Dependency Vulnerability Audit:")
    if dep_exit == 0:
        print("  ✓ Dependency audit: CLEAN")
    elif dep_exit == 2:
        print(f"  ! Dependency audit: INCOMPLETE\n{dep_output[:300]}")
    else:
        print(f"  ✗ Dependency audit reported failures:\n{dep_output[:300]}")

    print("==================================================================")
    if passed:
        print(" VERDICT: GREEN (No known patterns matched; heuristic scan, not proof of security.)")
        print("==================================================================")
        sys.exit(0)
    elif incomplete:
        print(" VERDICT: INCOMPLETE (Required scans or dependency checks could not be completed.)")
        print("==================================================================")
        sys.exit(2)
    else:
        print(" VERDICT: RED (Security perimeter breached. Fix issues before deploy.)")
        print("==================================================================")
        sys.exit(1)


if __name__ == "__main__":
    main()
