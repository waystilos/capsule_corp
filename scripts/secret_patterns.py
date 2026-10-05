#!/usr/bin/env python3
"""
Shared secret patterns and safe file-scanning helpers for the Capsule Corp gates
(`capsule security`, `capsule attack`, `capsule verify`, `capsule check`).

Design goals: one pattern list for every gate, a file universe that cannot be
dodged by directory/suffix naming, bounded work per file (no ReDoS), and
"fail closed": anything that could not be scanned is reported, never ignored.
"""

import bisect
import codecs
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

_BOUNDARY = r"(?<![A-Za-z0-9])"

_PLACEHOLDER_WORDS = (r"changeme|example|xxx|your[_-]|placeholder|dummy|redacted|"
                      r"replace[_-]?me|insert[_-]|todo\b")
_MAX_VALUE = 1024   # longest credential value considered (bounded: regex work stays linear per name hit)


def _not_placeholder(v: str, end: str) -> str:
    """Negative lookahead: the value (chars `v`, ended by `end`) is a placeholder only when
    it STARTS with a placeholder word and is short, or is short (<=40) and contains a placeholder
    word at a word boundary / `_here`. A placeholder word late inside a long real-looking value does not count."""
    return (r"(?!(?:" + _PLACEHOLDER_WORDS + r")" + v + r"{0,60}?" + end
            + r"|(?=" + v + r"{0,40}" + end + r")" + v + r"{0,40}?(?:(?<![A-Za-z0-9])(?:" + _PLACEHOLDER_WORDS
            + r")|_here\b))")


_NOT_PLACEHOLDER = _not_placeholder(r"[^\s\"']", r"(?![^\s\"'])")
# Sensitive-looking variable name; starts at a word boundary so scanning stays linear.
_NAME = (r"(?<![A-Za-z0-9_])[A-Za-z0-9_]{0,40}"
         r"(?:secret|token|password|passwd|api_?key|jwt_secret)[A-Za-z0-9_]{0,30}")
# Value must not be a path or an identifier-like word
# (snake_case / kebab-case / CONSTANT_CASE / camelCase / file name).
_IDENT_GUARD = (
    r"(?![/~]|\.{1,2}/|[A-Za-z]:[\\/])"
    + r"(?![^\s\"']{0,100}?\.(?:json|ya?ml|pem|txt|key|crt|cfg|conf|ini|env|toml|p12)(?![A-Za-z0-9]))"
    + r"(?!(?-i:[a-z]{1,30}(?:[_-][a-z]{1,30}){1,10}|[A-Z]{1,30}(?:_[A-Z]{1,30}){1,10}"
      r"|[a-z]{1,20}(?:[A-Z][a-z]{1,20}){1,6})(?![A-Za-z0-9_+/=:@%^&*!~.-]))"
    + r"(?![${<])"   # template / substitution / placeholder openers: ${X} $(cmd) {x} <token>
)
_VALUE_GUARD = _NOT_PLACEHOLDER + _IDENT_GUARD
_QVALUE_GUARD = _not_placeholder(r"[^\"'\n]", r"(?=[\"']|\Z)") + _IDENT_GUARD
_PLAIN = r"[^\s\"'<>${}()]"       # plain quoted-value chars
_QV = r"[^\"'\n]"                 # any quoted-value chars (spaces and $ ( ) < > { } allowed)
_UNQ = r"[A-Za-z0-9_+/=@%^&*!~-]"  # plain unquoted-value chars
_UNQ_WIDE = r"[A-Za-z0-9_+/=@%^&*!~#$(){}<>.-]"
_M = str(_MAX_VALUE)

# (regex body, description). Most specific first: a match whose start offset was
# already claimed by an earlier pattern is not reported twice.
SECRET_SPECS = [
    (r"sk-ant-api\d{2}-[a-zA-Z0-9_\-]{80,}", "Anthropic API Key"),
    (r"github_pat_[a-zA-Z0-9_]{82}", "GitHub Fine-Grained Personal Access Token"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gh[ousr]_[a-zA-Z0-9]{36}", "GitHub OAuth/App Token"),
    (r"glpat-[A-Za-z0-9_-]{20,}", "GitLab Personal Access Token"),
    (r"npm_[A-Za-z0-9]{36}", "npm Access Token"),
    (r"SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}", "SendGrid API Key"),
    (r"ya29\.[A-Za-z0-9_-]{20,}", "Google OAuth Access Token"),
    (r"SK[0-9a-f]{32}", "Twilio API Key SID"),
    (r"whsec_[0-9a-zA-Z]{24,}", "Stripe Webhook Secret"),
    (r"sk_test_[0-9a-zA-Z]{24,}", "Stripe Secret Test Key"),
    (r"AIza[0-9A-Za-z_-]{35}", "Google API Key"),
    (r"(?:AKIA|ASIA)[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"rk_live_[0-9a-zA-Z]{24,}", "Stripe Restricted Live Key"),
    (r"sk_live_[0-9a-zA-Z]{24,}", "Stripe Secret Live Key"),
    (r"xox[baprs]-[0-9a-zA-Z]{10,48}", "Slack Token"),
    (r"hf_[a-zA-Z0-9]{34,}", "HuggingFace Access Token"),
    (r"aws_secret_access_key[\"']?\s{0,5}[:=]\s{0,5}[\"']?[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])",
     "AWS Secret Access Key"),
    # Includes sk-proj-..., sk-svcacct-... (hyphens/underscores are part of the key).
    (r"sk-[A-Za-z0-9_-]{20,}", "OpenAI / Service Secret Key"),
    # Vendor-specific tokens (prefix-anchored, bounded).
    (r"key-[0-9a-f]{32}(?![0-9a-zA-Z])", "Mailgun API Key"),
    (r"AccountKey=[A-Za-z0-9+/]{40,100}={0,2}", "Azure Storage Account Key"),
    (r"do[opr]_v1_[a-f0-9]{64}", "DigitalOcean Token"),
    (r"shp(?:at|ca|pa|ss)_[a-f0-9]{32}", "Shopify Access Token"),
    (r"pypi-AgE[A-Za-z0-9_-]{50,}", "PyPI API Token"),
    (r"sq0(?:atp-[0-9A-Za-z_-]{22}|csp-[0-9A-Za-z_-]{43})", "Square Access Token"),
    (r"(?<![A-Za-z0-9_-])(?-i:eyJ)[A-Za-z0-9_-]{10,300}\.(?-i:eyJ)[A-Za-z0-9_-]{10,2000}\.[A-Za-z0-9_-]{10,600}",
     "JSON Web Token"),
    (r"(?<![A-Za-z0-9_-])(?-i:[MNO])(?=[A-Za-z0-9_-]{0,25}?(?-i:[A-Z0-9]))[A-Za-z0-9_-]{23,25}"
     r"\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,38}(?![A-Za-z0-9_-])", "Discord Bot Token"),
    # Authorization: Bearer <token> (not placeholders / ${VAR} / <token>).
    (r"Authorization[\"']?\s{0,5}[:=]\s{0,5}[\"']?Bearer\s{1,5}" + _NOT_PLACEHOLDER +
     r"(?:(?=[A-Za-z0-9._~+/=-]{0,200}?(?:\d|(?-i:[A-Z])))|(?=[A-Za-z0-9._~+/=-]{30}))[A-Za-z0-9._~+/=-]{20,300}",
     "Bearer Authorization Token"),
    # Database / URL userinfo: scheme://user:password@host
    (r"[a-z][a-z0-9+.-]{1,20}://[^\s:/@\"'<>${}()]{1,64}:"
     r"(?![^\s@/\"'<>${}()]{0,30}?(?:changeme|example|xxx|your[_-]|placeholder|dummy|redacted)[^\s@]{0,10}@)"
     r"(?!(?:pass(?:word)?|secret|user|root|admin|test|\*{1,}|x{1,}|\.{3})@)"
     r"[^\s@/\"'<>${}()]{3,100}@[A-Za-z0-9._\[\]-]{1,100}",
     "Credentials in URL"),
    # Generic quoted assignment: sensitive name = quoted literal (>=12 chars).
    # Plain values need a digit or mixed case; values with spaces / $ ( ) < > { } need a digit.
    # Placeholders, paths and identifiers are excluded. Also matches subscripts: cfg['secret'] = '...'.
    (_NAME + r"[\"']?\]?\s{0,5}[:=]\s{0,5}[\"']" + _QVALUE_GUARD +
     r"(?:(?:(?=" + _PLAIN + r"{0,200}?\d)|(?=" + _PLAIN + r"{0,200}?(?-i:[A-Z]))"
     r"(?=" + _PLAIN + r"{0,200}?(?-i:[a-z])))" + _PLAIN + r"{12," + _M + r"}"
     r"|(?=" + _QV + r"{0,200}?\d)" + _QV + r"{12," + _M + r"})[\"']",
     "Hardcoded Credential Assignment"),
    # Unquoted KEY=value (.env) and YAML `password: value` for sensitive names. Atomic (lookahead + backref)
    # so an over-long run fails in one pass instead of backtracking.
    (_NAME + r"\s{0,5}(?:=|:\s)\s{0,5}" + _VALUE_GUARD + r"(?![=])"
     r"(?:(?=(?P<u1>" + _UNQ + r"{16," + _M + r"}))(?P=u1)(?![A-Za-z0-9_+/=@%^&*!~.-])"
     r"|(?![A-Za-z_][A-Za-z0-9_.]{0,60}\([^\s]{0,100}\)(?![^\s]))"   # not a call: get_password(1)
     r"(?=" + _UNQ_WIDE + r"{0,200}?\d)(?=" + _UNQ_WIDE + r"{0,200}?[#$(){}<>.])"
     r"(?=(?P<u2>" + _UNQ_WIDE + r"{16," + _M + r"}))(?P=u2)(?!" + _UNQ_WIDE + r")"
     r"|(?=(?P<u3>[A-Za-z0-9_-]{8,400}(?:\.[A-Za-z0-9_-]{8,400}){2,8}))(?P=u3)(?![A-Za-z0-9_.-]))",
     "Hardcoded Credential Assignment (unquoted)"),
]
PRIVATE_KEY_SPEC = (
    r"-----BEGIN (?:(?:RSA|EC|OPENSSH|DSA|PGP|ENCRYPTED) )?PRIVATE KEY",
    "Private Key Block",
)

SECRET_PATTERNS = [
    (re.compile(_BOUNDARY + body, re.IGNORECASE), desc) for body, desc in SECRET_SPECS
] + [(re.compile(PRIVATE_KEY_SPEC[0]), PRIVATE_KEY_SPEC[1])]

# Regexes usable directly against a unified-diff text (lines starting with '+').
# Bounded prefix (no unbounded `.*`) so a hostile long line cannot blow up. Known limit: a secret that
# starts more than 4000 chars into a '+' line is not seen by these diff regexes; the full-content scan
# (find_secrets over file chunks/line windows) has no such window and covers the same text.
DIFF_SECRET_PATTERNS = [
    (re.compile(r"^\+[^\n]{0,4000}?" + _BOUNDARY + body, re.MULTILINE | re.IGNORECASE), "Exposed " + desc)
    for body, desc in SECRET_SPECS
] + [
    (re.compile(r"^\+[^\n]{0,4000}?" + PRIVATE_KEY_SPEC[0], re.MULTILINE), "Private Key block"),
]

# Vendored/tooling directories. Skipped at any depth only when their files are not
# tracked by git. build/, dist/, .cache/, .next/ are deliberately NOT here.
# Vendor dirs worth surfacing in reports when skipped (tool caches/.git are noise).
REPORTED_VENDOR_DIRS = {"node_modules", ".venv", "venv", "site-packages", ".tox"}

VENDOR_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", ".mypy_cache",
    ".pytest_cache", "site-packages",
}

CONVENTIONAL_TEST_DIRS = {"tests", "test", "spec", "__tests__"}

MAX_FILE_BYTES = 128 * 1024 * 1024   # absolute secret-scan cap per file
CHUNK_BYTES = 1024 * 1024
CHUNK_OVERLAP = 4096
LINE_WINDOW = 1000                    # code-rule scanning window per line
LINE_WINDOW_OVERLAP = 200
CODE_MAX_BYTES = 4 * 1024 * 1024      # code-rule scanning cap per file
FILE_TIME_BUDGET = 5.0                # seconds of regex work per file for code rules
SECRET_TIME_BUDGET = 30.0
TOTAL_TIME_BUDGET = 60.0              # seconds of regex work across ALL files in one scan
TOTAL_BUDGET_ENV = "CAPSULE_SCAN_TOTAL_BUDGET"

# Suffixes the code-rule scanners (`capsule security`, `capsule attack`) understand.
CODE_SUFFIXES = {
    ".py", ".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".go", ".rs",
    ".rb", ".php", ".ex", ".exs", ".erl", ".sh", ".java", ".cs", ".kt", ".vue", ".svelte",
}
# Text/data suffixes that are deliberately not code-scanned (still secret-scanned).
KNOWN_NON_CODE_SUFFIXES = {
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".lock",
    ".html", ".htm", ".css", ".scss", ".svg", ".csv", ".tsv", ".xml", ".env", ".gitignore",
    ".gitattributes", ".log", ".pem", ".crt", ".key", ".map", ".pyi", ".pyc", ".ps1", ".bat",
    ".cmd", ".sql", ".lockb", ".example", ".sample", ".in", ".conf",
}


def total_time_budget() -> float:
    """Total regex-time budget for one scan: env CAPSULE_SCAN_TOTAL_BUDGET or the default."""
    raw = os.environ.get(TOTAL_BUDGET_ENV)
    if not raw:
        return TOTAL_TIME_BUDGET
    try:
        value = float(raw)
    except ValueError:
        return TOTAL_TIME_BUDGET
    return value if value == value else TOTAL_TIME_BUDGET   # NaN -> default


class Deadline(object):
    """Monotonic deadline shared by every file of one scan."""

    def __init__(self, seconds: Optional[float] = None) -> None:
        self.seconds = total_time_budget() if seconds is None else seconds
        self.at = time.monotonic() + self.seconds

    def expired(self) -> bool:
        return time.monotonic() > self.at


def is_text_file(path: Path) -> bool:
    """Heuristic: no NUL byte in the first 4 KB (or looks like UTF-16/32 text)."""
    try:
        with open(str(path), "rb") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    return b"\0" not in head or detect_wide_codec(head) is not None


def search_windows(regex: "re.Pattern", line: str, deadline: float) -> Optional[bool]:
    """Search a (possibly huge) line window by window, checking the clock before
    every window. True = matched, False = no match, None = deadline hit mid-line."""
    for window in iter_line_windows(line):
        if time.monotonic() > deadline:
            return None
        if regex.search(window):
            return True
    return False


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------

def detect_wide_codec(data: bytes) -> Optional[str]:
    """Return a utf-16/32 codec name when bytes look like wide text, else None."""
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return "utf-32"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    sample = data[:4096]
    if b"\0" not in sample:
        return None
    n = len(sample) // 2
    if n < 4:
        return None
    evens = sample[0::2].count(0)
    odds = sample[1::2].count(0)
    if odds > n * 0.3 and evens * 4 < odds:
        return "utf-16-le"
    if evens > n * 0.3 and odds * 4 < evens:
        return "utf-16-be"
    return None


def decode_bytes(data: bytes) -> str:
    """Decode any bytes for scanning: BOM/UTF-16 aware, lossy otherwise."""
    codec = detect_wide_codec(data)
    if codec:
        return data.decode(codec, errors="ignore")
    return data.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# Secret matching
# ---------------------------------------------------------------------------

def redact_text(text: str) -> str:
    """Mask every secret match, keeping only the first 4 chars of each."""
    for pattern, _ in SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group(0)[:4] + "***", text)
    return text


_QUOTED_LITERAL = re.compile(r"([\"'])([^\s\"'\\]{8,100})\1")


def redact_quoted_literals(text: str) -> str:
    """Mask quoted secret-like literals (>=8 chars, no whitespace) in code snippets.
    Plain snake_case words (identifiers/option names) are kept for readability."""
    def _sub(m):
        word = m.group(2)
        if "_" in word and word.replace("_", "").isalpha() and word.islower():
            return m.group(0)
        q = m.group(1)
        return q + m.group(2)[:2] + "***" + q
    return _QUOTED_LITERAL.sub(_sub, text)


def safe_snippet(text: str, width: int = 80) -> str:
    """One-line snippet for code-pattern findings: secret matches and quoted
    secret-like literals are masked before truncation."""
    return redact_quoted_literals(redact_text(text))[:width].strip()


def find_secrets(text: str, deadline: Optional[float] = None) -> List[Tuple[int, int, str]]:
    """Return (start, end, description) for each secret, one per start offset.
    A later (more generic) hit that contains an earlier specific hit is dropped.
    With `deadline` (time.monotonic value) it stops between patterns once passed;
    callers must re-check the clock and treat that as INCOMPLETE."""
    seen: Set[int] = set()
    hits: List[Tuple[int, int, str]] = []
    starts: List[int] = []   # sorted start offsets of `hits` (kept in step for bisect)
    spans: List[Tuple[int, int, str]] = []
    for pattern, desc in SECRET_PATTERNS:
        if deadline is not None and time.monotonic() > deadline:
            break
        for m in pattern.finditer(text):
            if m.start() in seen:
                continue
            i = bisect.bisect_left(starts, m.start())
            contained = False
            while i < len(spans) and spans[i][0] < m.end():
                if spans[i][1] <= m.end():
                    contained = True
                    break
                i += 1
            if contained:
                continue
            seen.add(m.start())
            j = bisect.bisect_left(starts, m.start())
            starts.insert(j, m.start())
            spans.insert(j, (m.start(), m.end(), desc))
            hits.append((m.start(), m.end(), desc))
    hits.sort()
    return hits


def snippet_for(text: str, start: int, end: int, width: int = 80) -> str:
    """Redacted one-line context around a match."""
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    if le == -1:
        le = len(text)
    ls = max(ls, start - 40)
    le = min(le, end + 40)
    return redact_text(text[ls:le])[:width].strip()


# ---------------------------------------------------------------------------
# Chunked reading
# ---------------------------------------------------------------------------

def _iter_wide_chunks(fh: Any, head: bytes, codec: str, chunk_bytes: int, max_total: int,
                      info: Dict[str, Any]) -> Iterator[Tuple[int, str]]:
    decoder = codecs.getincrementaldecoder(codec)(errors="ignore")
    total = 0
    pending = ""
    line_no = 1
    data = head
    while data:
        total += len(data)
        if total > max_total:
            info["truncated"] = True
            data = data[:len(data) - (total - max_total)]
            final = True
        else:
            final = False
        pending += decoder.decode(data, final)
        cut = pending.rfind("\n")
        if cut != -1 or len(pending) > chunk_bytes:
            if cut == -1:
                text, pending = pending[:chunk_bytes], pending[chunk_bytes - CHUNK_OVERLAP:]
            else:
                text, pending = pending[:cut + 1], pending[cut + 1:]
            yield line_no, text
            line_no += text.count("\n")
        if final:
            break
        data = fh.read(chunk_bytes)
    if pending:
        yield line_no, pending


def iter_text_chunks(path: Path, info: Dict[str, Any], chunk_bytes: int = CHUNK_BYTES,
                     max_total: Optional[int] = None) -> Iterator[Tuple[int, str]]:
    """Yield (first_line_number, text) chunks of a file, cut on newlines, with
    overlap for newline-free runs. Sets info["truncated"] when the cap was hit."""
    if max_total is None:
        max_total = MAX_FILE_BYTES
    with open(str(path), "rb") as fh:
        head = fh.read(chunk_bytes)
        if not head:
            return
        codec = detect_wide_codec(head)
        if codec:
            # Wide text: decode incrementally in chunks (bounded memory/time), then rescan
            # the same bytes as UTF-8 so a BOM-looking prefix cannot hide ASCII secrets.
            for item in _iter_wide_chunks(fh, head, codec, chunk_bytes, max_total, info):
                yield item
            fh.seek(0)
            head = fh.read(chunk_bytes)
        total = len(head)
        buf = head
        line_no = 1
        while True:
            cut = buf.rfind(b"\n")
            if cut == -1:
                text = buf.decode("utf-8", errors="ignore")
                carry = buf[-CHUNK_OVERLAP:]
            else:
                text = buf[:cut + 1].decode("utf-8", errors="ignore")
                carry = buf[cut + 1:]
            yield line_no, text
            line_no += text.count("\n")
            data = fh.read(chunk_bytes)
            if not data:
                if carry and cut != -1:
                    yield line_no, carry.decode("utf-8", errors="ignore")
                return
            total += len(data)
            if total > max_total:
                info["truncated"] = True
                return
            buf = carry + data


def iter_line_windows(line: str, size: int = LINE_WINDOW, overlap: int = LINE_WINDOW_OVERLAP) -> Iterator[str]:
    """Yield the line itself, or overlapping windows for very long lines, so no
    regex ever runs over more than `size` characters at once."""
    if len(line) <= size:
        yield line
        return
    step = size - overlap
    for i in range(0, len(line), step):
        yield line[i:i + size]
        if i + size >= len(line):
            break


# ---------------------------------------------------------------------------
# File universe
# ---------------------------------------------------------------------------

def is_test_path(path: Path, root_dir: Path) -> bool:
    """True only for files under a top-level conventional test dir (tests/, test/,
    spec/, __tests__/). Names like test_x.py elsewhere are NOT exempt."""
    try:
        parts = path.relative_to(root_dir).parts
    except ValueError:
        return False
    return len(parts) > 1 and parts[0] in CONVENTIONAL_TEST_DIRS


def _git_lines(root: Path, args: List[str]) -> Optional[List[str]]:
    try:
        res = subprocess.run(
            ["git"] + args, cwd=str(root),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    return [os.fsdecode(p) for p in res.stdout.split(b"\0") if p]


def _git_toplevel_is_root(root: Path) -> bool:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(root),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if res.returncode != 0:
        return False
    try:
        return Path(os.fsdecode(res.stdout).strip()).resolve() == root.resolve()
    except OSError:
        return False


class FileUniverse(object):
    def __init__(self) -> None:
        self.files: List[Tuple[Path, str]] = []   # (absolute path, relative posix string)
        self.skipped_symlinks: List[str] = []
        self.skipped_vendor_dirs: List[str] = []   # reportable vendor dir names actually skipped
        self.used_git = False


def _classify(root: Path, root_real: str, rel: str, uni: FileUniverse) -> None:
    path = root / rel
    if path.is_symlink():
        try:
            target = os.path.realpath(str(path))
        except OSError:
            return
        if os.path.lexists(target) and not (target == root_real or target.startswith(root_real + os.sep)):
            uni.skipped_symlinks.append(rel)
        return  # in-root targets are scanned directly; dangling links hold nothing
    if path.is_file():
        uni.files.append((path, rel))


def collect_files(root_dir: Path, extra_vendor: Optional[Set[str]] = None) -> FileUniverse:
    """Files to scan. In a git repo: tracked + untracked-not-ignored. Otherwise a
    walk. Vendor dirs are skipped at any depth unless git tracks their files;
    symlinks that leave the root are never followed (reported instead)."""
    root = Path(root_dir).resolve()
    root_real = os.path.realpath(str(root))
    vendor = set(VENDOR_DIRS) | set(extra_vendor or ())
    uni = FileUniverse()

    if _git_toplevel_is_root(root):
        tracked = _git_lines(root, ["ls-files", "-z", "--cached"])
        others = _git_lines(root, ["ls-files", "-z", "--others", "--exclude-standard"])
        if tracked is not None and others is not None:
            uni.used_git = True
            seen: Set[str] = set()
            skipped: Set[str] = set()
            tracked_vendor: Set[str] = set()
            for rel in tracked:
                if rel not in seen:
                    seen.add(rel)
                    tracked_vendor.update(Path(rel).parts[:-1])
                    _classify(root, root_real, rel, uni)
            for rel in others:
                if rel in seen:
                    continue
                seen.add(rel)
                hit = [part for part in Path(rel).parts[:-1] if part in vendor]
                if hit:
                    skipped.update(hit)
                    continue
                _classify(root, root_real, rel, uni)
            # Gitignored vendor dirs that exist on disk are skipped too: say so.
            for name in REPORTED_VENDOR_DIRS & vendor:
                if name not in tracked_vendor and (root / name).is_dir():
                    skipped.add(name)
            uni.skipped_vendor_dirs = sorted(skipped & REPORTED_VENDOR_DIRS)
            return uni

    skipped_walk: Set[str] = set()
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        rel_dir = os.path.relpath(dirpath, str(root))
        keep = []
        for d in sorted(dirnames):
            if d in vendor:
                skipped_walk.add(d)
                continue
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                rel = d if rel_dir == "." else os.path.join(rel_dir, d)
                _classify(root, root_real, rel, uni)
                continue
            keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            rel = name if rel_dir == "." else os.path.join(rel_dir, name)
            _classify(root, root_real, rel, uni)
    uni.skipped_vendor_dirs = sorted(skipped_walk & REPORTED_VENDOR_DIRS)
    return uni
