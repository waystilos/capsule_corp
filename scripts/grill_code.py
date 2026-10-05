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
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple, Any

try:
    from .runtime import configure_utf8_stdio
    from . import secret_patterns as sp
except ImportError:
    from runtime import configure_utf8_stdio
    import secret_patterns as sp

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
        re.compile(r"^[+]\s*except(?:\s[\w\s,()]+)?:\s*(?:pass|\.\.\.)\s*$", re.MULTILINE),
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
        re.compile(r"requests\.(?:get|post|put|delete|patch)\("),
        "HIGH",
        "MISSING_HTTP_TIMEOUT",
        "Missing Request Timeout: HTTP call made without explicit timeout parameter.",
        "An unmetered request with no timeout? You would let this thread hang for eternity while your servers starve?",
        "Pass an explicit timeout (e.g. timeout=10.0 or timeout=(5.0, 30.0))."
    ),
    (
        re.compile(r"httpx\.(?:get|post|put|delete|patch)\("),
        "HIGH",
        "MISSING_HTTP_TIMEOUT",
        "Missing Httpx Timeout: HTTP request lacks explicit timeout configuration.",
        "Httpx without a timeout? When the remote host stalls, your connection pool will suffocate.",
        "Configure explicit timeout=httpx.Timeout(10.0)."
    ),
    (
        re.compile(r"urllib\.request\.urlopen\("),
        "HIGH",
        "MISSING_HTTP_TIMEOUT",
        "Missing Urlopen Timeout: urllib request lacks timeout parameter.",
        "Urlopen with default infinite timeout? A single slow network will freeze the entire thread.",
        "Pass timeout=10 explicitly."
    ),
]

# The TIMEOUT regexes only find the call start (linear). A match counts when the call
# closes on the same line within POST_CHECK_CHARS and no `timeout=` follows it.
POST_CHECK_CHARS = 500
_TIMEOUT_KW = re.compile(r"timeout\s*=")
TIMEOUT_REGEXES = {id(t[0]) for t in TIMEOUT_PATTERNS}


def _call_missing_timeout(prefixed: str, regex: "re.Pattern") -> bool:
    for m in regex.finditer(prefixed):
        rest = prefixed[m.end():m.end() + POST_CHECK_CHARS]
        if ")" in rest and not _TIMEOUT_KW.search(rest):
            return True
    return False


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


MAX_SCAN_BYTES = 1_000_000  # cap per-file read size for untracked / full-scan files

TRIVIAL_DEFENSES = {
    "n/a", "na", "none", "no", "yes", "ok", "okay", "fine", "skip", "todo", "idk",
    "because", "test", "wontfix", "later", "intentional", "needed", "legacy",
}
MIN_DEFENSE_LENGTH = 15
MIN_DEFENSE_WORDS = 3


def is_valid_defense(text: Any) -> bool:
    """A defense must be a real justification: non-trivial, min length, multiple words."""
    if not isinstance(text, str):
        return False
    t = " ".join(text.split())
    if len(t) < MIN_DEFENSE_LENGTH:
        return False
    if t.lower().strip(".!") in TRIVIAL_DEFENSES:
        return False
    words = re.findall(r"[A-Za-z0-9]+", t)
    if len(words) < MIN_DEFENSE_WORDS or len(set(w.lower() for w in words)) < 2:
        return False
    return True


def content_fingerprint(text: str) -> str:
    """Short hash of whitespace-normalized flagged content (stable across line shifts)."""
    norm = " ".join(text.split())
    return hashlib.sha1(norm.encode("utf-8", errors="ignore")).hexdigest()[:12]


def make_issue_id(file: str, category: str, snippet: str) -> str:
    return f"{file}:{category}:{content_fingerprint(snippet)}"


def _run_git(target_dir: Path, args: List[str], input_text: Optional[str] = None) -> Tuple[int, str, str]:
    """Run git; never raises. Returns (returncode, stdout, stderr); rc=-1 when git cannot run."""
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false"] + args,
            cwd=str(target_dir),
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, ValueError) as exc:
        return -1, "", str(exc)


def _read_capped_ex(path: Path) -> Tuple[Optional[str], bool]:
    """Read a regular file up to MAX_SCAN_BYTES. Returns (text, truncated); text is None for
    symlink-to-nowhere, dirs, or OSError. BOM/UTF-16 aware (sp.decode_bytes)."""
    try:
        if not path.is_file():
            return None, False
        with open(str(path), "rb") as fh:
            data = fh.read(MAX_SCAN_BYTES + 1)
    except OSError:
        return None, False
    return sp.decode_bytes(data[:MAX_SCAN_BYTES]), len(data) > MAX_SCAN_BYTES


def _read_capped(path: Path) -> Optional[str]:
    return _read_capped_ex(path)[0]


def _split_lines(content: str) -> List[str]:
    """Split on "\\n" only. str.splitlines also splits on \\x0b/\\x0c/\\x1c/\\x85/\\u2028 and
    would let a payload hide behind a line-separator control character."""
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


_HIDDEN_FLAGS = ("h", "s", "S")  # git ls-files -v: assume-unchanged / skip-worktree
_C_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
              "\\": "\\", '"': '"'}


def _unquote_git_path(raw: str) -> str:
    """Undo git's C-style quoting of unusual path names ("a\\tb")."""
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        return raw
    body, out, i = raw[1:-1], bytearray(), 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in "01234567":
                j = i + 1
                while j < len(body) and j < i + 4 and body[j] in "01234567":
                    j += 1
                out.append(int(body[i + 1:j], 8) & 0xFF)
                i = j
                continue
            out.extend(_C_ESCAPES.get(nxt, nxt).encode("utf-8"))
            i += 2
            continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="replace")


def find_hidden_changes(target_dir: Path) -> Tuple[List[str], Optional[str]]:
    """Files git was told to ignore changes in (assume-unchanged / skip-worktree): their
    edits never appear in a diff. Returns (paths, error)."""
    try:
        res = subprocess.run(["git", "ls-files", "-v", "-z"], cwd=str(target_dir),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        return [], str(exc)
    if res.returncode != 0:
        return [], res.stderr.decode("utf-8", errors="replace").strip() or "git ls-files -v failed"
    hidden = []
    for entry in res.stdout.split(b"\0"):
        if len(entry) > 2 and chr(entry[0]) in _HIDDEN_FLAGS:
            hidden.append(os.fsdecode(entry[2:]))
    return hidden, None


def get_git_diff_content(target_dir: Path, staged: bool = False,
                         notes: Optional[List[str]] = None) -> Tuple[str, List[str], List[str], Optional[str]]:
    """Retrieve (diff_text, touched_files, untracked_files, error).

    Untracked files are returned as paths AND appended to diff_text as synthetic
    all-added hunks so they are scanned exactly like tracked additions (not for --staged,
    since untracked files are by definition not staged). `error` is a human-readable
    string when git could not produce a trustworthy diff; callers must not treat that as all-clear.
    `notes` (optional) collects INCOMPLETE reasons (e.g. truncated untracked files).
    """
    rc, out, err = _run_git(target_dir, ["rev-parse", "--is-inside-work-tree"])
    if rc == -1:
        return "", [], [], f"git unavailable: {err.strip()}"
    if rc != 0 or out.strip() != "true":
        return "", [], [], "not a git repository"

    diff_flags = ["--no-color", "--no-ext-diff", "--no-textconv", "--text", "--src-prefix=a/", "--dst-prefix=b/"]
    if staged:
        cmd = ["diff", "--cached"] + diff_flags
    else:
        hrc, _, _ = _run_git(target_dir, ["rev-parse", "--verify", "--quiet", "HEAD"])
        if hrc == 0:
            base = "HEAD"
        else:
            # Fresh repo with no commits: diff against the empty tree.
            trc, tree, terr = _run_git(target_dir, ["hash-object", "-t", "tree", "--stdin"], input_text="")
            if trc != 0 or not tree.strip():
                return "", [], [], f"git could not resolve empty tree: {terr.strip()}"
            base = tree.strip()
        cmd = ["diff"] + diff_flags + [base]

    rc, diff_text, err = _run_git(target_dir, cmd)
    if rc != 0:
        return "", [], [], f"git diff failed (exit {rc}): {err.strip()}"

    untracked: List[str] = []
    if not staged:
        urc, uout, uerr = _run_git(target_dir, ["ls-files", "--others", "--exclude-standard"])
        if urc != 0:
            return "", [], [], f"git ls-files failed (exit {urc}): {uerr.strip()}"
        untracked = [line.strip() for line in uout.splitlines() if line.strip()]
        synthetic = []
        for rel in untracked:
            if not is_code_file(rel):
                continue
            content, truncated = _read_capped_ex(target_dir / rel)
            if content is None:
                continue
            if truncated and notes is not None:
                notes.append("%s: untracked file exceeds the %d byte scan cap; remainder not scanned" % (rel, MAX_SCAN_BYTES))
            body = _split_lines(content)
            if not body:
                continue
            synthetic.append(f"diff --git a/{rel} b/{rel}")
            synthetic.append("new file mode 100644")
            synthetic.append("--- /dev/null")
            synthetic.append(f"+++ b/{rel}")
            synthetic.append(f"@@ -0,0 +1,{len(body)} @@")
            synthetic.extend("+" + b for b in body)
        if synthetic:
            if diff_text and not diff_text.endswith("\n"):
                diff_text += "\n"
            diff_text += "\n".join(synthetic) + "\n"

    touched = list(_parse_diff(diff_text).keys())
    return diff_text, touched, untracked, None


def _parse_diff(diff_text: str) -> Dict[str, List[Tuple[int, str]]]:
    """Map each b/-side path in a unified diff to its added (new_lineno, '+' + content) lines.
    Splits on "\\n" only and tracks hunk state, so an added line whose content starts with
    '++' (diff text '+++ ...') or a line holding \\x0b/\\x0c is never mistaken for a header
    or dropped. Every file with a header is present even when it has no hunks."""
    files: Dict[str, List[Tuple[int, str]]] = {}
    current: Optional[str] = None
    current_line = 0
    in_hunk = False
    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            in_hunk = False
            current = None
            continue
        if not in_hunk:
            if line.startswith("+++ "):
                path = _unquote_git_path(line[4:].rstrip("\t").strip())
                current = path[2:] if path.startswith("b/") else None
                if current is not None:
                    files.setdefault(current, [])
                continue
            if line.startswith("@@ "):
                match = re.search(r"\+(\d+)", line)
                current_line = (int(match.group(1)) if match else 1) - 1
                in_hunk = True
            continue
        if line.startswith("@@ "):
            match = re.search(r"\+(\d+)", line)
            current_line = (int(match.group(1)) if match else 1) - 1
            continue
        if current is None:
            continue
        if line.startswith(" "):
            current_line += 1
        elif line.startswith("+"):
            current_line += 1
            files[current].append((current_line, line))
    return files


def load_defenses(target_dir: Path) -> Dict[str, Any]:
    """Load previously recorded developer justifications/defenses."""
    defense_file = target_dir / ".capsule" / "grill_defenses.json"
    if defense_file.exists():
        try:
            data = json.loads(defense_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def save_defense(target_dir: Path, issue_id: str, defense_text: str, question: str):
    """Save an interactive developer defense to .capsule/grill_defenses.json.

    Raises ValueError if the defense is not a real justification.
    """
    defense_text = " ".join(str(defense_text).split())
    if not is_valid_defense(defense_text):
        raise ValueError(
            f"Defense rejected: provide a real justification (>= {MIN_DEFENSE_LENGTH} chars, "
            f">= {MIN_DEFENSE_WORDS} words, not a stock phrase)."
        )
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


def build_issue(defenses: Dict[str, Any], file: str, line: int, severity: str, category: str,
                description: str, question: str, remediation: str, snippet: str) -> Dict[str, Any]:
    """Assemble an issue; defended only when a valid justification exists for its content-hash id."""
    issue_id = make_issue_id(file, category, snippet)
    entry = defenses.get(issue_id)
    defense = entry.get("defense") if isinstance(entry, dict) else None
    return {
        "id": issue_id,
        "file": file,
        "line": line,
        "severity": severity,
        "category": category,
        "description": description,
        "beerus_question": question,
        "remediation": remediation,
        "snippet": sp.safe_snippet(snippet, 200),
        "defended": is_valid_defense(defense),
        "defense": defense if is_valid_defense(defense) else None,
    }


def find_swallowed_exceptions(lines: List[Tuple[int, str]], file_ext: str = ".py",
                              deadline: Optional[float] = None) -> List[Dict[str, Any]]:
    """Detect single-line and multi-line swallowed exceptions or discarded promises.
    Stops early when `deadline` (time.monotonic value) passes."""
    results = []
    for i, (lno, text) in enumerate(lines):
        if deadline is not None and time.monotonic() > deadline:
            break
        clean = text.lstrip("+").strip()
        if not clean or clean.startswith(("#", "//", "/*", "*")):
            continue

        # Python Exceptions
        if file_ext == ".py":
            # Case 1: single-line except ...: pass
            if re.match(r"^except(?:\s[\w\s,()]+)?:\s*(?:pass|\.\.\.)\s*$", clean):
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
            if re.match(r"^except(?:\s[\w\s,()]+)?:\s*$", clean):
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


SINGLE_LINE_PATTERNS = (
    TIMEOUT_PATTERNS + RESOURCE_PATTERNS + DEBT_PATTERNS + STATE_PATTERNS + NULL_HAZARD_PATTERNS
)


def _expand_long_lines(lines: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """Cut lines longer than the scan window into overlapping '+'-prefixed windows so every
    regex runs over a bounded string (no quadratic blow-up on one giant line)."""
    out: List[Tuple[int, str]] = []
    for idx, prefixed in lines:
        if len(prefixed) <= sp.LINE_WINDOW + 1:
            out.append((idx, prefixed))
        else:
            for window in sp.iter_line_windows(prefixed[1:]):
                out.append((idx, "+" + window))
    return out


def _scan_lines(defenses: Dict[str, Any], rel_path: str, lines: List[Tuple[int, str]],
                incomplete: Optional[List[str]] = None, total_deadline: Optional[float] = None) -> List[Dict[str, Any]]:
    """Run single-line and swallowed-exception checks over (lineno, '+'-prefixed text) pairs.
    Bounded by a per-file and a total time budget; a hit budget is recorded in `incomplete`."""
    found = []
    seen = set()
    deadline = time.monotonic() + sp.FILE_TIME_BUDGET
    if total_deadline is not None:
        deadline = min(deadline, total_deadline)
    lines = _expand_long_lines(lines)
    for pos, (idx, prefixed) in enumerate(lines):
        if time.monotonic() > deadline:
            if incomplete is not None:
                incomplete.append("%s: scan time budget exceeded; scanned up to line %d" % (rel_path, idx))
            return found
        for regex, severity, category, description, question, remediation in SINGLE_LINE_PATTERNS:
            if id(regex) in TIMEOUT_REGEXES:
                hit = _call_missing_timeout(prefixed, regex)
            else:
                hit = bool(regex.search(prefixed))
            if hit and (idx, category, description) not in seen:
                seen.add((idx, category, description))
                found.append(build_issue(defenses, rel_path, idx, severity, category,
                                         description, question, remediation, prefixed[1:].strip()))
    ext = Path(rel_path).suffix.lower()
    for sw in find_swallowed_exceptions(lines, file_ext=ext, deadline=deadline):
        key = (sw["line"], sw["category"], sw["description"])
        if key in seen:
            continue
        seen.add(key)
        found.append(build_issue(defenses, rel_path, sw["line"], sw["severity"], sw["category"],
                                 sw["description"], sw["beerus_question"], sw["remediation"], sw["snippet"]))
    if time.monotonic() > deadline and incomplete is not None:
        incomplete.append("%s: scan time budget exceeded; swallowed-error checks partially run" % rel_path)
    return found


def audit_diff_for_grill(diff_text: str, touched_files: List[str], untracked_files: List[str], target_dir: Path,
                         incomplete: Optional[List[str]] = None,
                         total_deadline: Optional[float] = None) -> List[Dict[str, Any]]:
    """Scan git diff (incl. synthetic untracked hunks) against Beerus' 7 Inquisitions."""
    issues = []
    defenses = load_defenses(target_dir)
    if incomplete is None:
        incomplete = []
    if total_deadline is None:
        total_deadline = sp.Deadline().at

    new_symbols = []
    new_symbol_pattern = re.compile(r"^[+]\s*(?:def\s+([a-zA-Z_]\w*)|class\s+([a-zA-Z_]\w*)|function\s+([a-zA-Z_]\w*)|(?:export\s+)?(?:const|let)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)")

    file_added_lines: Dict[str, List[Tuple[int, str]]] = {}
    for fpath, added in _parse_diff(diff_text).items():
        if not is_code_file(fpath):
            continue
        file_added_lines[fpath] = added
        for _lno, line in added:
            if len(line) > 2000:
                continue   # a symbol declaration is never a multi-KB line; keep this linear
            m = new_symbol_pattern.search(line)
            if m:
                symbol = next((g for g in m.groups() if g), None)
                if symbol and not symbol.startswith("_"):
                    new_symbols.append((fpath, symbol))

    for fpath, added in file_added_lines.items():
        issues.extend(_scan_lines(defenses, fpath, added, incomplete, total_deadline))

    # Untested Complexity: new public symbols require at least one touched/untracked test file
    has_test_file = any(is_test_file(f) for f in (touched_files + untracked_files))
    if new_symbols and not has_test_file:
        symbols_str = ", ".join(f"`{s}` in {f}" for f, s in new_symbols[:4])
        if len(new_symbols) > 4:
            symbols_str += f" (+{len(new_symbols)-4} more)"
        issues.append(build_issue(
            defenses, "global", 1, "HIGH", "UNTESTED_COMPLEXITY",
            f"Untested Logic Creep: New functions/classes introduced ({len(new_symbols)}) without accompanying test additions.",
            f"You added new mortal functions ({symbols_str}), yet touched zero test files. Do you expect me to accept this on blind faith?",
            "Add automated unit or integration tests asserting behavior for the new logic.",
            f"New logic added: {symbols_str}",
        ))
        issues[-1]["file"] = new_symbols[0][0]

    return issues


def scan_directory_files(target_dir: Path, incomplete: Optional[List[str]] = None,
                         total_deadline: Optional[float] = None) -> List[Dict[str, Any]]:
    """Scan all files directly when not using git diff.

    Runs every single-line check (including NULL_HAZARD) plus swallowed-exception checks.
    UNTESTED_COMPLEXITY is intentionally diff-only: it asks whether *newly added* symbols
    came with tests, and a full scan has no baseline of "new" symbols to compare against.
    Files over the read cap, and anything left unscanned when a time budget runs out, are
    recorded in `incomplete` (never silently dropped).
    """
    issues = []
    if incomplete is None:
        incomplete = []
    if total_deadline is None:
        total_deadline = sp.Deadline().at

    def scan_one(file_path: Path, rel_path: str, defenses: Dict[str, Any]) -> None:
        content, truncated = _read_capped_ex(file_path)
        if content is None:
            return
        if truncated:
            incomplete.append("%s: file exceeds the %d byte scan cap; remainder not scanned" % (rel_path, MAX_SCAN_BYTES))
        lines = [(idx, "+" + line) for idx, line in enumerate(_split_lines(content), start=1)]
        issues.extend(_scan_lines(defenses, rel_path, lines, incomplete, total_deadline))

    if target_dir.is_file():
        # Single-file target: scan just that file (defenses live next to it).
        if is_code_file(target_dir.name):
            scan_one(target_dir, target_dir.name, load_defenses(target_dir.parent))
        return issues
    defenses = load_defenses(target_dir)

    skipped_total = 0
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(target_dir).as_posix()
            if not is_code_file(rel_path):
                continue
            if time.monotonic() > total_deadline:
                skipped_total += 1
                continue
            scan_one(file_path, rel_path, defenses)
    if skipped_total:
        incomplete.append("Total scan time budget exceeded; %d file(s) not scanned" % skipped_total)
    return issues


def run_grill_audit(target_dir: Path, staged: bool = False, scan_all: bool = False,
                    total_budget: Optional[float] = None) -> Dict[str, Any]:
    """Execute Beerus' Code Inquisition audit. `total_budget` (seconds; default env
    CAPSULE_SCAN_TOTAL_BUDGET or 60) caps regex time across all files."""
    target_dir = target_dir.resolve()
    error = None
    note = None
    issues: List[Dict[str, Any]] = []
    incomplete: List[str] = []
    nothing_staged = False
    total_deadline = sp.Deadline(total_budget).at

    if scan_all or target_dir.is_file():
        issues = scan_directory_files(target_dir, incomplete, total_deadline)
        mode = "full_scan"
    else:
        diff_text, touched_files, untracked_files, error = get_git_diff_content(
            target_dir, staged=staged, notes=incomplete)
        if error == "not a git repository":
            # Honest fallback: no diff exists, so scan everything and say so.
            note = "Not a git repository: no diff available, performed full scan."
            error = None
            issues = scan_directory_files(target_dir, incomplete, total_deadline)
            mode = "full_scan"
        elif error:
            mode = "error"
        else:
            hidden, hidden_err = find_hidden_changes(target_dir)
            if hidden_err:
                incomplete.append("Unable to inspect assume-unchanged/skip-worktree flags: %s" % hidden_err[:100])
            for rel in hidden:
                incomplete.append("%s: marked assume-unchanged/skip-worktree; git diff cannot see its changes" % rel)
            if staged:
                mode = "diff_audit"
                if diff_text.strip():
                    issues = audit_diff_for_grill(diff_text, touched_files, untracked_files, target_dir,
                                                  incomplete, total_deadline)
                else:
                    nothing_staged = True
            elif not diff_text.strip() and not untracked_files:
                issues = scan_directory_files(target_dir, incomplete, total_deadline)
                mode = "full_scan"
            else:
                issues = audit_diff_for_grill(diff_text, touched_files, untracked_files, target_dir,
                                              incomplete, total_deadline)
                mode = "diff_audit"

    # Evaluate Hakai Threat Level
    undefended_critical = [i for i in issues if i["severity"] == "CRITICAL" and not i.get("defended")]
    undefended_high = [i for i in issues if i["severity"] == "HIGH" and not i.get("defended")]
    undefended_medium = [i for i in issues if i["severity"] == "MEDIUM" and not i.get("defended")]
    defended_critical = [i for i in issues if i["severity"] == "CRITICAL" and i.get("defended")]

    if error:
        threat_level = "INQUISITION FAILED (GIT ERROR)"
        verdict = "FAIL"
    elif nothing_staged:
        threat_level = "NOTHING TO GRILL (NOTHING STAGED)"
        verdict = "PASS"
    elif undefended_critical:
        threat_level = "HAKAI IMMINENT"
        verdict = "FAIL"
    elif incomplete:
        threat_level = "INCOMPLETE (SCAN GAPS)"
        verdict = "INCOMPLETE"
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
        "error": error,
        "note": note,
        "nothing_to_grill": nothing_staged,
        "incomplete": incomplete,
        "summary": {
            "total_inquisitions": len(issues),
            "critical": len(undefended_critical),
            "high": len(undefended_high),
            "medium": len(undefended_medium),
            "defended": len([i for i in issues if i.get("defended")]),
            "defended_critical": len(defended_critical),
        },
        "defended_critical": [
            {"id": i["id"], "file": i["file"], "line": i["line"], "category": i["category"], "defense": i.get("defense")}
            for i in defended_critical
        ],
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

    if report.get("note"):
        lines.append(f" Note:             {report['note']}")
    issues = report.get("issues", [])
    if report.get("error"):
        lines.append(f" ERROR: {report['error']}")
        lines.append("    Beerus cannot judge what he cannot see. This is NOT an all-clear.")
    elif report.get("nothing_to_grill"):
        lines.append(" Nothing is staged: there is nothing to grill. (Not a divine approval.)")
    elif not issues and report.get("incomplete"):
        lines.append(" No known patterns matched, but the scan was INCOMPLETE: this is NOT an approval.")
    elif not issues:
        lines.append(" ✨ DIVINE APPROVAL: no known patterns matched (heuristic regex scan, not proof).")
        lines.append("    No swallowed errors, missing timeouts or untested new symbols were detected.")
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

    for gap in report.get("incomplete", [])[:20]:
        lines.append(f" ! INCOMPLETE: {gap}")

    defended_crit = report.get("defended_critical", [])
    if defended_crit:
        lines.append(f"\n {len(defended_crit)} CRITICAL finding(s) DEFENDED (still on record, review them):")
        for d in defended_crit:
            lines.append(f"  - {d['category']} in {d['file']}:{d['line']} -- \"{d['defense']}\"")

    lines.append("\n" + "=" * 78)
    if report.get("error"):
        lines.append(" VERDICT: FAIL (Inquisition could not run; fix the error above.)")
    elif report["verdict"] == "INCOMPLETE":
        lines.append(" VERDICT: INCOMPLETE (Some changes could not be inspected; not an approval.)")
    elif report["verdict"] == "PASS":
        lines.append(" VERDICT: PASS (No known patterns matched; heuristic scan, not proof.)")
    elif report["verdict"] == "WARN":
        lines.append(" VERDICT: WARN (Tension detected. Defend your choices or fix before merge.)")
    else:
        lines.append(" VERDICT: HAKAI IMMINENT (Critical failures detected. Remediate immediately.)")
    lines.append("=" * 78)
    return "\n".join(lines)


def interactive_grill(target_dir: Path, report: Dict[str, Any], staged: bool = False, scan_all: bool = False) -> int:
    """Interactively walk the developer through Beerus' questions and record justifications."""
    if report.get("error"):
        print(f"\nInquisition could not run: {report['error']}")
        return 1
    if report.get("nothing_to_grill"):
        print("\nNothing is staged: nothing to grill.")
        return 0
    issues = [i for i in report.get("issues", []) if not i.get("defended")]
    if not issues:
        if report.get("incomplete"):
            print("\nLord Beerus has no questions, but the scan was INCOMPLETE (not an approval):")
            for gap in report["incomplete"][:20]:
                print(f"  ! {gap}")
            return 2
        print("\nLord Beerus has no questions for you (no known patterns matched; heuristic scan, not proof).")
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
        print("\n👑 Lord Beerus demands:")
        print(f"   \"{item['beerus_question']}\"\n")

        prompt = "Your Architectural Defense / Justification (or press Enter to skip): "
        try:
            defense = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nInquisition aborted.")
            return 1

        if defense:
            try:
                save_defense(target_dir, item["id"], defense, item["beerus_question"])
                print("✓ Defense recorded in .capsule/grill_defenses.json.")
            except ValueError as exc:
                print(f"✗ {exc} This inquisition remains undefended.")
        else:
            print("· Skipped. This inquisition remains undefended.")

    print("\nInquisition concluded. Re-evaluating threat level...")
    updated_report = run_grill_audit(target_dir, staged=staged, scan_all=scan_all)
    print(format_grill_report(updated_report))
    return 0 if updated_report["verdict"] in ("PASS", "WARN") else (2 if updated_report["verdict"] == "INCOMPLETE" else 1)


def main():
    parser = argparse.ArgumentParser(description="Lord Beerus' Architectural Inquisition & Code Griller")
    parser.add_argument("target_dir", nargs="?", default=".", help="Project root or directory to grill")
    parser.add_argument("--diff", action="store_true", help="Audit git diff (default behavior if diff exists)")
    parser.add_argument("--staged", action="store_true", help="Audit only staged git changes")
    parser.add_argument("--all", action="store_true", help="Audit all files in project, not just git diff (full scan runs all single-line checks; UNTESTED_COMPLEXITY is diff-only)")
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
        sys.exit(interactive_grill(target, report, staged=args.staged, scan_all=args.all))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_grill_report(report, verbose=args.verbose))

    if report["verdict"] == "INCOMPLETE":
        sys.exit(2)
    if args.strict:
        sys.exit(0 if report["verdict"] == "PASS" else 1)
    else:
        sys.exit(0 if report["verdict"] in ("PASS", "WARN") else 1)


if __name__ == "__main__":
    main()
