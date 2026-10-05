"""Shared config helpers for check/verify: TOML loading and safe command splitting."""

import os
import re
import shlex
import warnings
from pathlib import Path
from typing import Any, Dict, List

try:  # Python 3.11+
    import tomllib as _tomllib  # type: ignore
except ImportError:  # pragma: no cover - exercised on 3.8-3.10
    _tomllib = None


def _strip_inline_comment(value: str) -> str:
    quote = None
    for i, ch in enumerate(value):
        if quote:
            if ch == "\\" and quote == '"':
                continue
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "#":
            return value[:i].rstrip()
    return value.strip()


def _parse_value(raw: str) -> Any:
    raw = _strip_inline_comment(raw.strip())
    if raw == "true":
        return True
    if raw == "false":
        return False
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        inner = raw[1:-1]
        if raw[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    if re.fullmatch(r"[+-]?\d+", raw):
        return int(raw)
    return _UNPARSED


_UNPARSED = object()


def _bracket_depth(text: str) -> int:
    depth, quote = 0, None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and not (quote == '"' and text[i - 1] == "\\"):
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "#":
            break
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth


def _split_array_items(inner: str) -> List[str]:
    items, buf, quote = [], "", None
    for i, ch in enumerate(inner):
        if quote:
            buf += ch
            if ch == quote and not (quote == '"' and inner[i - 1] == "\\"):
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf)
    return [i.strip() for i in items if i.strip()]


def _parse_array(raw: str) -> Any:
    """Parse a flat array of scalars; return _UNPARSED for nested arrays / inline tables."""
    lines = [_strip_inline_comment(l.strip()) for l in raw.splitlines()]
    body = " ".join(l for l in lines if l)
    if not (body.startswith("[") and body.endswith("]")):
        return _UNPARSED
    out = []
    for item in _split_array_items(body[1:-1]):
        if item[0] in "[{":
            return _UNPARSED
        val = _parse_value(item)
        if val is _UNPARSED:
            return _UNPARSED
        out.append(val)
    return out


def parse_toml_fallback(text: str) -> Dict[str, Any]:
    """Minimal TOML subset parser for Python < 3.11.

    Supports tables, booleans, ints, quoted strings, flat (also multi-line) arrays of
    scalars and comments. Unsupported constructs (arrays of tables, inline tables, nested
    arrays, multi-line strings, floats/dates, dotted keys) emit a RuntimeWarning and the
    key is skipped rather than being silently mangled.
    """
    root: Dict[str, Any] = {}
    current = root
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        if line.startswith("[["):
            warnings.warn("TOML fallback: arrays of tables are unsupported, skipping %r" % line, RuntimeWarning)
            current = {}  # keys under it are discarded (with the warning above)
            continue
        if line.startswith("["):
            header = _strip_inline_comment(line)
            if header.endswith("]"):
                current = root
                for part in header[1:-1].strip().split("."):
                    part = part.strip().strip('"').strip("'")
                    nxt = current.setdefault(part, {})
                    if not isinstance(nxt, dict):
                        nxt = current[part] = {}
                    current = nxt
                continue
        if "=" in line:
            key, val = line.split("=", 1)
            raw_key = key.strip()
            key = raw_key.strip('"').strip("'")
            if "." in raw_key and raw_key[0] not in "\"'":
                warnings.warn("TOML fallback: dotted key %r unsupported, skipping" % raw_key, RuntimeWarning)
                while _bracket_depth(val) > 0 and i < len(lines):
                    val += "\n" + lines[i]
                    i += 1
                continue
            val = val.strip()
            if '"' * 3 in val or "'" * 3 in val:
                warnings.warn("TOML fallback: multi-line strings unsupported, skipping key %r" % key, RuntimeWarning)
                fence = val[val.index('"' * 3):][:3] if '"' * 3 in val else "'" * 3
                if val.count(fence) < 2:
                    while i < len(lines) and fence not in lines[i]:
                        i += 1
                    i += 1
                continue
            if val.startswith("[") or val.startswith("{"):
                while _bracket_depth(val) > 0 and i < len(lines):
                    val += "\n" + lines[i]
                    i += 1
                parsed = _parse_array(val) if val.startswith("[") else _UNPARSED
                if parsed is _UNPARSED:
                    warnings.warn("TOML fallback: unsupported value for key %r, skipping" % key, RuntimeWarning)
                else:
                    current[key] = parsed
                continue
            parsed = _parse_value(val)
            if parsed is _UNPARSED:
                warnings.warn("TOML fallback: unsupported value for key %r, skipping" % key, RuntimeWarning)
            else:
                current[key] = parsed
    return root


def load_toml(path: Path) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if _tomllib is not None:
        return _tomllib.loads(text)
    return parse_toml_fallback(text)


def split_command(value: Any) -> List[str]:
    """Split a configured command into argv. Raises ValueError on bad input."""
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, str) for v in value):
        return list(value)
    if not isinstance(value, str):
        raise ValueError("command must be a string, got %s" % type(value).__name__)
    posix = os.name != "nt"
    parts = shlex.split(value, posix=posix)
    if not posix:
        parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    return parts
