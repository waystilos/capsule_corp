#!/usr/bin/env python3
"""
Lord Beerus' Architectural Inquisition & Code Griller (`capsule grill`)
Capsule Corp Divine Verification Gatekeeper.

Performs ruthless, skeptical interrogation of pull requests, git diffs,
and architecture:
  1. Silent Failures & Swallowed Errors (except: pass, empty catch)
  2. Missing Timeouts & Hanging Resources (requests/fetch without timeouts)
  3. Untested Logic & Complexity Creep (new functions with zero test coverage)
  4. Unbounded Resources & Leaks (open without context manager, queries without limit)
  5. Lazy Shortcuts & Deferred Debt (TODO, FIXME, HACK)
  6. Null / Nil Blindness & Edge Hazards (unguarded deep property access)
  7. Global Mutable State & Concurrency Traps (global mutations)

Supports interactive interrogation, defenses recording, and strict verification gates.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple, Any

try:
    from .runtime import configure_utf8_stdio
except ImportError:
    from runtime import configure_utf8_stdio

configure_utf8_stdio()

IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", ".capsule", "egg-info", ".pytest_cache"
}

TEST_FILE_PATTERNS = [
    re.compile(r"(?:^|/)(?:test_.*|.*_test)\.py$"),
    re.compile(r"(?:^|/)(?:.*\.test|.*\.spec)\.(?:ts|tsx|js|jsx)$"),
    re.compile(r"(?:^|/)(?:.*_test)\.go$"),
    re.compile(r"(?:^|/)(?:tests/.*|spec/.*)$"),
]

# 1. Silent Failures & Swallowed Errors
SWALLOWED_ERROR_PATTERNS = [
    (
        re.compile(r"^[+]\s*except(?:\s+[\w\s,()]+)?:\s*(?:pass|\.\.\.)\s*$", re.MULTILINE),
        "CRITICAL",
        "SWALLOWED_EXCEPTION",
        "Silent Exception Swallowing: Exception caught and discarded with pass/...",
        "You dare swallow this exception in silence? What happens when this operation fails at 3 AM in production?",
        "Catch specific exceptions, log the incident, and return an explicit fallback or bubble up."
    ),
    (
        re.compile(r"^[+]\s*catch\s*(?:\([^)]*\))?\s*\{\s*\}", re.MULTILINE),
        "CRITICAL",
        "SWALLOWED_EXCEPTION",
        "Empty Catch Block: Error swallowed with zero handling or logging.",
        "An empty catch block? You blind the system to its own mortality. How will you debug this when it crashes?",
        "Log the caught error or dispatch an error event to the boundary handler."
    ),
    (
        re.compile(r"^[+]\s*\.catch\s*\(\s*(?:\(\s*\)|\w+)?\s*=>\s*\{\s*\}\s*\)", re.MULTILINE),
        "CRITICAL",
        "SWALLOWED_PROMISE_ERROR",
        "Swallowed Promise Rejection: Empty .catch(() => {}) handler.",
        "A discarded Promise rejection? If this async task fails, who will notify the caller or user?",
        "Handle promise rejections with graceful degradation or bubble to the boundary."
    ),
]

# 2. Missing Timeouts & Hanging Calls
TIMEOUT_PATTERNS = [
    (
        re.compile(r"^[+].*requests\.(?:get|post|put|delete|patch)\((?!.*timeout\s*=)[^)]*\)", re.MULTILINE),
        "HIGH",
        "MISSING_HTTP_TIMEOUT",
        "Missing Request Timeout: HTTP call made without explicit timeout parameter.",
        "An unmetered request with no timeout? You would let this thread hang for eternity while your servers starve?",
        "Pass an explicit timeout (e.g. timeout=10.0 or timeout=(5.0, 30.0))."
    ),
    (
        re.compile(r"^[+].*httpx\.(?:get|post|put|delete|patch)\((?!.*timeout\s*=)[^)]*\)", re.MULTILINE),
        "HIGH",
        "MISSING_HTTP_TIMEOUT",
        "Missing Httpx Timeout: HTTP request lacks explicit timeout configuration.",
        "Httpx without a timeout? When the remote host stalls, your connection pool will suffocate.",
        "Configure explicit timeout=httpx.Timeout(10.0)."
    ),
    (
        re.compile(r"^[+].*urllib\.request\.urlopen\((?!.*timeout\s*=)[^)]*\)", re.MULTILINE),
        "HIGH",
        "MISSING_HTTP_TIMEOUT",
        "Missing Urlopen Timeout: urllib request lacks timeout parameter.",
        "Urlopen with default infinite timeout? A single slow network will freeze the entire thread.",
        "Pass timeout=10 explicitly."
    ),
]

# 3. Unbounded Resources & Unclosed Handles
RESOURCE_PATTERNS = [
    (
        re.compile(r"^[+]\s*(?:\w+\s*=\s*)open\([^)]*\)(?!\s*with\b)", re.MULTILINE),
        "HIGH",
        "UNMANAGED_FILE_HANDLE",
        "Raw File Handle: open() called outside of a 'with' context manager.",
        "Opening a file without a context manager? Who will close this descriptor when an exception strikes?",
        "Always wrap file operations in 'with open(...) as f:'."
    ),
]

# 4. Lazy Debt & Deferred Shortcuts
DEBT_PATTERNS = [
    (
        re.compile(r"^[+].*?(?:#|//|/\*)\s*(?:TODO|FIXME|HACK|XXX)\b(?:\s*:|\s+-|\s+[A-Za-z])", re.MULTILINE),
        "MEDIUM",
        "DEFERRED_DEBT",
        "Deferred Technical Debt: Unfinished TODO / FIXME / HACK marker staged for release.",
        "A 'TODO' left in production-bound code? You dare serve me half-cooked mortal dishes? Explain why this was not finished.",
        "Complete the implementation or convert the marker into a tracked milestone issue before shipping."
    ),
]

# 5. Global Mutable State
STATE_PATTERNS = [
    (
        re.compile(r"^[+]\s*global\s+\w+", re.MULTILINE),
        "HIGH",
        "GLOBAL_MUTATION",
        "Global Mutable Variable: Function claims and mutates global module state.",
        "Mutating global state inside a function? When concurrent requests strike, your state will collapse into ruin.",
        "Pass state explicitly as function parameters or encapsulate inside a scoped class instance."
    ),
]

# 6. Null & Undefined Hazards
NULL_HAZARD_PATTERNS = [
    (
        re.compile(r"^[+].*?\b([a-zA-Z_]\w*\.[a-zA-Z_]\w*\.[a-zA-Z_]\w*\.[a-zA-Z_]\w+)\b", re.MULTILINE),
        "LOW",
        "UNGUARDED_DEEP_ACCESS",
        "Unguarded Deep Property Access: 4-level deep dot access without optional chaining.",
        "Deeply chained property access with no guards. What happens when the upstream payload is malformed or null?",
        "Use optional chaining (?.) or safe dictionary lookup (.get()) to guard against missing properties."
    ),
]

SUPPORTED_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".rb", ".php", ".cs"
}


def is_test_file(path_str: str) -> bool:
    p = Path(path_str)
    if "tests" in p.parts or "test" in p.parts or p.name.startswith("test_") or p.name.endswith(("_test.py", "_test.go", ".test.ts", ".spec.ts", ".test.js", ".spec.js")):
        return True
    for pattern in TEST_FILE_PATTERNS:
        if pattern.search(path_str.replace("\\", "/")):
            return True
    return False


def is_code_file(path_str: str) -> bool:
    if is_test_file(path_str):
        return False
    return Path(path_str).suffix.lower() in SUPPORTED_CODE_EXTENSIONS


def get_git_diff_content(target_dir: Path, staged: bool = False) -> Tuple[str, List[str], List[str]]:
    """Retrieve git diff text and list of touched files and untracked files."""
    try:
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        else:
            cmd.append("HEAD")

        proc = subprocess.run(
            cmd,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        diff_text = proc.stdout if proc.returncode == 0 else ""

        # Also get untracked files
        untracked_proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        untracked = [line.strip() for line in untracked_proc.stdout.splitlines() if line.strip()]

        # Modified files from diff
        touched = []
        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                touched.append(line[6:].strip())

        return diff_text, touched, untracked
    except Exception:
        return "", [], []


def load_defenses(target_dir: Path) -> Dict[str, Any]:
    """Load previously recorded developer justifications/defenses."""
    defense_file = target_dir / ".capsule" / "grill_defenses.json"
    if defense_file.exists():
        try:
            return json.loads(defense_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_defense(target_dir: Path, issue_id: str, defense_text: str, question: str):
    """Save an interactive developer defense to .capsule/grill_defenses.json."""
    capsule_dir = target_dir / ".capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)
    defense_file = capsule_dir / "grill_defenses.json"

    data = load_defenses(target_dir)
    data[issue_id] = {
        "question": question,
        "defense": defense_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    defense_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_swallowed_exceptions(lines: List[Tuple[int, str]], file_ext: str = ".py") -> List[Dict[str, Any]]:
    """Detect single-line and multi-line swallowed exceptions or discarded promises."""
    results = []
    for i, (lno, text) in enumerate(lines):
        clean = text.lstrip("+").strip()
        if not clean or clean.startswith(("#", "//", "/*", "*")):
            continue

        # Python Exceptions
        if file_ext == ".py":
            # Case 1: single-line except ...: pass
            if re.match(r"^except(?:\s+[\w\s,()]+)?:\s*(?:pass|\.\.\.)\s*$", clean):
                results.append({
                    "line": lno,
                    "snippet": clean,
                    "category": "SWALLOWED_EXCEPTION",
                    "severity": "CRITICAL",
                    "description": "Silent Exception Swallowing: Exception caught and discarded with pass/...",
                    "beerus_question": "You dare swallow this exception in silence? What happens when this operation fails at 3 AM in production?",
                    "remediation": "Catch specific exceptions, log the incident, and return an explicit fallback or bubble up.",
                })
                continue

            # Case 2: multi-line except ...:\n pass
            if re.match(r"^except(?:\s+[\w\s,()]+)?:\s*$", clean):
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_clean = lines[j][1].lstrip("+").strip()
                    if not next_clean or next_clean.startswith("#"):
                        continue
                    if next_clean in ("pass", "..."):
                        results.append({
                            "line": lno,
                            "snippet": f"{clean} {next_clean}",
                            "category": "SWALLOWED_EXCEPTION",
                            "severity": "CRITICAL",
                            "description": "Silent Exception Swallowing: Exception caught and discarded with pass/...",
                            "beerus_question": "You dare swallow this exception in silence? What happens when this operation fails at 3 AM in production?",
                            "remediation": "Catch specific exceptions, log the incident, and return an explicit fallback or bubble up.",
                        })
                    break
                continue

        # JavaScript / TypeScript Exceptions & Promises
        elif file_ext in (".js", ".ts", ".tsx", ".jsx"):
            # Case 3: JS single-line catch {}
            if re.search(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}", clean):
                results.append({
                    "line": lno,
                    "snippet": clean,
                    "category": "SWALLOWED_EXCEPTION",
                    "severity": "CRITICAL",
                    "description": "Empty Catch Block: Error swallowed with zero handling or logging.",
                    "beerus_question": "An empty catch block? You blind the system to its own mortality. How will you debug this when it crashes?",
                    "remediation": "Log the caught error or dispatch an error event to the boundary handler.",
                })
                continue

            # Case 4: JS multi-line catch {\n}
            if re.search(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*$", clean):
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_clean = lines[j][1].lstrip("+").strip()
                    if not next_clean or next_clean.startswith("//"):
                        continue
                    if next_clean == "}":
                        results.append({
                            "line": lno,
                            "snippet": f"{clean} }}",
                            "category": "SWALLOWED_EXCEPTION",
                            "severity": "CRITICAL",
                            "description": "Empty Catch Block: Error swallowed with zero handling or logging.",
                            "beerus_question": "An empty catch block? You blind the system to its own mortality. How will you debug this when it crashes?",
                            "remediation": "Log the caught error or dispatch an error event to the boundary handler.",
                        })
                    break
                continue

            # Case 5: JS swallowed promise rejection
            if re.search(r"\.catch\s*\(\s*(?:\(\s*\)|\w+)?\s*=>\s*\{\s*\}\s*\)", clean) or re.search(r"\.catch\s*\(\s*\)", clean):
                results.append({
                    "line": lno,
                    "snippet": clean,
                    "category": "SWALLOWED_PROMISE_ERROR",
                    "severity": "CRITICAL",
                    "description": "Swallowed Promise Rejection: Empty .catch(() => {}) handler.",
                    "beerus_question": "A discarded Promise rejection? If this async task fails, who will notify the caller or user?",
                    "remediation": "Handle promise rejections with graceful degradation or bubble to the boundary.",
                })
                continue
    return results


def audit_diff_for_grill(diff_text: str, touched_files: List[str], untracked_files: List[str], target_dir: Path) -> List[Dict[str, Any]]:
    """Scan git diff and untracked files against Beerus' 7 Inquisitions."""
    issues = []
    defenses = load_defenses(target_dir)

    # 1. Check diff chunks
    current_file = None
    current_line = 0
    file_added_lines: Dict[str, List[Tuple[int, str]]] = {}

    single_line_patterns = (
        TIMEOUT_PATTERNS +
        RESOURCE_PATTERNS +
        DEBT_PATTERNS +
        STATE_PATTERNS +
        NULL_HAZARD_PATTERNS
    )

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            current_line = 0
            file_added_lines.setdefault(current_file, [])
            continue
        elif line.startswith("@@ "):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1))
            continue

        if not current_file:
            continue

        if not is_code_file(current_file):
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current_line += 1
            file_added_lines[current_file].append((current_line, line))
            for regex, severity, category, description, question, remediation in single_line_patterns:

                if regex.search(line):
                    issue_key = f"{current_file}:{current_line}:{category}"
                    is_defended = issue_key in defenses or f"{current_file}:{category}" in defenses
                    issues.append({
                        "id": issue_key,
                        "file": current_file,
                        "line": current_line,
                        "severity": severity,
                        "category": category,
                        "description": description,
                        "beerus_question": question,
                        "remediation": remediation,
                        "snippet": line[1:].strip(),
                        "defended": is_defended,
                        "defense": defenses.get(issue_key, {}).get("defense") or defenses.get(f"{current_file}:{category}", {}).get("defense"),
                    })

    # Run multi-line swallowed exception checks across added lines
    for fpath, added in file_added_lines.items():
        if not is_code_file(fpath):
            continue
        ext = Path(fpath).suffix.lower()
        swallowed = find_swallowed_exceptions(added, file_ext=ext)
        for sw in swallowed:
            issue_key = f"{fpath}:{sw['line']}:{sw['category']}"
            is_defended = issue_key in defenses or f"{fpath}:{sw['category']}" in defenses
            issues.append({
                "id": issue_key,
                "file": fpath,
                "line": sw["line"],
                "severity": sw["severity"],
                "category": sw["category"],
                "description": sw["description"],
                "beerus_question": sw["beerus_question"],
                "remediation": sw["remediation"],
                "snippet": sw["snippet"],
                "defended": is_defended,
                "defense": defenses.get(issue_key, {}).get("defense") or defenses.get(f"{fpath}:{sw['category']}", {}).get("defense"),
            })

    # 2. Check for Untested Complexity
    # If new functions/classes are added, verify at least one test file was touched
    has_test_file = any(is_test_file(f) for f in (touched_files + untracked_files))
    new_symbol_pattern = re.compile(r"^[+]\s*(?:def\s+([a-zA-Z_]\w*)|class\s+([a-zA-Z_]\w*)|function\s+([a-zA-Z_]\w*)|(?:export\s+)?(?:const|let)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", re.MULTILINE)

    new_symbols = []
    current_file = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if current_file and not is_test_file(current_file) and line.startswith("+") and not line.startswith("+++"):
            match = new_symbol_pattern.search(line)
            if match:
                symbol = next((g for g in match.groups() if g), None)
                if symbol and not symbol.startswith("_"):
                    new_symbols.append((current_file, symbol))

    if new_symbols and not has_test_file:
        symbols_str = ", ".join(f"`{s}` in {f}" for f, s in new_symbols[:4])
        if len(new_symbols) > 4:
            symbols_str += f" (+{len(new_symbols)-4} more)"
        issue_key = "global:UNTESTED_COMPLEXITY"
        is_defended = issue_key in defenses
        issues.append({
            "id": issue_key,
            "file": new_symbols[0][0],
            "line": 1,
            "severity": "HIGH",
            "category": "UNTESTED_COMPLEXITY",
            "description": f"Untested Logic Creep: New functions/classes introduced ({len(new_symbols)}) without accompanying test additions.",
            "beerus_question": f"You added new mortal functions ({symbols_str}), yet touched zero test files. Do you expect me to accept this on blind faith?",
            "remediation": "Add automated unit or integration tests asserting behavior for the new logic.",
            "snippet": f"New logic added: {symbols_str}",
            "defended": is_defended,
            "defense": defenses.get(issue_key, {}).get("defense"),
        })

    return issues


def scan_directory_files(target_dir: Path) -> List[Dict[str, Any]]:
    """Scan all files directly when not using git diff."""
    issues = []
    defenses = load_defenses(target_dir)

    single_line_patterns = (
        TIMEOUT_PATTERNS +
        RESOURCE_PATTERNS +
        DEBT_PATTERNS +
        STATE_PATTERNS
    )

    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for file in files:
            file_path = Path(root) / file
            rel_path = str(file_path.relative_to(target_dir))
            if not is_code_file(rel_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lines = [(idx, line) for idx, line in enumerate(content.splitlines(), start=1)]

            for idx, line in lines:
                prefixed = f"+{line}"
                for regex, severity, category, description, question, remediation in single_line_patterns:
                    if regex.search(prefixed):
                        issue_key = f"{rel_path}:{idx}:{category}"
                        is_defended = issue_key in defenses or f"{rel_path}:{category}" in defenses
                        issues.append({
                            "id": issue_key,
                            "file": rel_path,
                            "line": idx,
                            "severity": severity,
                            "category": category,
                            "description": description,
                            "beerus_question": question,
                            "remediation": remediation,
                            "snippet": line.strip(),
                            "defended": is_defended,
                            "defense": defenses.get(issue_key, {}).get("defense") or defenses.get(f"{rel_path}:{category}", {}).get("defense"),
                        })

            ext = Path(rel_path).suffix.lower()
            swallowed = find_swallowed_exceptions(lines, file_ext=ext)
            for sw in swallowed:
                issue_key = f"{rel_path}:{sw['line']}:{sw['category']}"
                is_defended = issue_key in defenses or f"{rel_path}:{sw['category']}" in defenses
                issues.append({
                    "id": issue_key,
                    "file": rel_path,
                    "line": sw["line"],
                    "severity": sw["severity"],
                        "category": sw["category"],
                        "description": sw["description"],
                        "beerus_question": sw["beerus_question"],
                        "remediation": sw["remediation"],
                        "snippet": sw["snippet"],
                        "defended": is_defended,
                        "defense": defenses.get(issue_key, {}).get("defense") or defenses.get(f"{rel_path}:{sw['category']}", {}).get("defense"),
                    })
    return issues


def run_grill_audit(target_dir: Path, staged: bool = False, scan_all: bool = False) -> Dict[str, Any]:
    """Execute Beerus' Code Inquisition audit."""
    target_dir = target_dir.resolve()
    diff_text, touched_files, untracked_files = get_git_diff_content(target_dir, staged=staged)

    if scan_all or (not diff_text and not untracked_files):
        issues = scan_directory_files(target_dir)
        mode = "full_scan"
    else:
        issues = audit_diff_for_grill(diff_text, touched_files, untracked_files, target_dir)
        mode = "diff_audit"

    # Evaluate Hakai Threat Level
    undefended_critical = [i for i in issues if i["severity"] == "CRITICAL" and not i.get("defended")]
    undefended_high = [i for i in issues if i["severity"] == "HIGH" and not i.get("defended")]
    undefended_medium = [i for i in issues if i["severity"] == "MEDIUM" and not i.get("defended")]

    if undefended_critical:
        threat_level = "HAKAI IMMINENT"
        verdict = "FAIL"
    elif undefended_high or len(undefended_medium) >= 3:
        threat_level = "DANGEROUS (TENSION)"
        verdict = "WARN"
    elif issues:
        threat_level = "TENSION (WARNINGS)"
        verdict = "WARN"
    else:
        threat_level = "DIVINE APPROVAL (SAFE)"
        verdict = "PASS"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": str(target_dir),
        "mode": mode,
        "threat_level": threat_level,
        "verdict": verdict,
        "summary": {
            "total_inquisitions": len(issues),
            "critical": len(undefended_critical),
            "high": len(undefended_high),
            "medium": len(undefended_medium),
            "defended": len([i for i in issues if i.get("defended")]),
        },
        "issues": issues,
    }


def format_grill_report(report: Dict[str, Any], verbose: bool = False) -> str:
    """Format Beerus' Divine Inquisition report."""
    lines = []
    lines.append("=" * 78)
    lines.append(" 🟣 LORD BEERUS' DIVINE INQUISITION REPORT (CAPSULE CORP)")
    lines.append("=" * 78)
    lines.append(f" Target Directory: {report['target']}")
    lines.append(f" Mode:             {report['mode'].upper()}")
    lines.append(f" Hakai Threat:     {report['threat_level']}")
    lines.append("------------------------------------------------------------------------------")

    issues = report.get("issues", [])
    if not issues:
        lines.append(" ✨ DIVINE APPROVAL: Beerus is satisfied with this mortal craftsmanship.")
        lines.append("    Zero swallowed errors, zero missing timeouts, zero untested complexity.")
        lines.append("    The universe is spared... for now.")
    else:
        lines.append(f" {len(issues)} Inquisition(s) Flagged:")
        for idx, item in enumerate(issues, start=1):
            sev = item["severity"]
            badge = f"[{sev}]"
            if item.get("defended"):
                badge = "[DEFENDED]"

            lines.append(f"\n {idx}. {badge:<10} {item['category']} in {item['file']}:{item['line']}")
            lines.append(f"    Snippet:  {item['snippet'][:90]}")
            lines.append(f"    Beerus:   \"{item['beerus_question']}\"")
            if item.get("defended"):
                lines.append(f"    Defense:  \"{item.get('defense')}\"")
            else:
                lines.append(f"    Remedy:   {item['remediation']}")

    lines.append("\n" + "=" * 78)
    if report["verdict"] == "PASS":
        lines.append(" VERDICT: PASS (Approved by Lord Beerus. Zero Hakai threats.)")
    elif report["verdict"] == "WARN":
        lines.append(" VERDICT: WARN (Tension detected. Defend your choices or fix before merge.)")
    else:
        lines.append(" VERDICT: HAKAI IMMINENT (Critical failures detected. Remediate immediately.)")
    lines.append("=" * 78)
    return "\n".join(lines)


def interactive_grill(target_dir: Path, report: Dict[str, Any]) -> int:
    """Interactively walk the developer through Beerus' questions and record justifications."""
    issues = [i for i in report.get("issues", []) if not i.get("defended")]
    if not issues:
        print("\n✨ Lord Beerus has no questions for you. Everything is in divine order.")
        return 0

    print("\n" + "=" * 78)
    print(" 🟣 LORD BEERUS' INTERACTIVE INQUISITION")
    print(" Prepare to defend your mortal code against the God of Destruction.")
    print("=" * 78)

    for idx, item in enumerate(issues, start=1):
        print(f"\n--- [Inquisition #{idx} of {len(issues)}] ---")
        print(f"File:     {item['file']}:{item['line']}")
        print(f"Category: {item['category']} ({item['severity']})")
        print(f"Code:     {item['snippet']}")
        print(f"\n👑 Lord Beerus demands:")
        print(f"   \"{item['beerus_question']}\"\n")

        prompt = "Your Architectural Defense / Justification (or press Enter to skip): "
        try:
            defense = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nInquisition aborted.")
            return 1

        if defense:
            save_defense(target_dir, item["id"], defense, item["beerus_question"])
            print("✓ Defense recorded in .capsule/grill_defenses.json.")
        else:
            print("· Skipped. This inquisition remains undefended.")

    print("\nInquisition concluded. Re-evaluating threat level...")
    updated_report = run_grill_audit(target_dir)
    print(format_grill_report(updated_report))
    return 0 if updated_report["verdict"] in ("PASS", "WARN") else 1


def main():
    parser = argparse.ArgumentParser(description="Lord Beerus' Architectural Inquisition & Code Griller")
    parser.add_argument("target_dir", nargs="?", default=".", help="Project root or directory to grill")
    parser.add_argument("--diff", action="store_true", help="Audit git diff (default behavior if diff exists)")
    parser.add_argument("--staged", action="store_true", help="Audit only staged git changes")
    parser.add_argument("--all", action="store_true", help="Audit all files in project, not just git diff")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive developer defense interrogation")
    parser.add_argument("--strict", action="store_true", help="Exit code 1 on any warnings or Hakai threats")
    parser.add_argument("--json", action="store_true", help="Output audit report as structured JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose reporting")
    args = parser.parse_args()

    target = Path(args.target_dir).resolve()
    if not target.exists():
        print(f"Error: Target path {target} does not exist", file=sys.stderr)
        sys.exit(1)

    report = run_grill_audit(target, staged=args.staged, scan_all=args.all)

    if args.interactive:
        sys.exit(interactive_grill(target, report))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_grill_report(report, verbose=args.verbose))

    if args.strict:
        sys.exit(0 if report["verdict"] == "PASS" else 1)
    else:
        sys.exit(0 if report["verdict"] in ("PASS", "WARN") else 1)


if __name__ == "__main__":
    main()
