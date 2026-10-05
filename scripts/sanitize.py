"""Shared untrusted-text sanitizer used by room, messaging, envelope, models, route and scaffold output.

Removes ANSI escapes and every invisible / formatting code point that can smuggle hidden text or spoof
rendering: Unicode categories Cf (format, incl. bidi, zero-width, soft hyphen, BOM, word joiner, U+061C, U+180E),
Cc (controls), Cs (lone surrogates), Co (private use), Cn (unassigned), the Unicode tag block U+E0000-E007F,
variation-selector supplement U+E0100-E01EF, and the blank "filler" glyphs (U+034F, U+115F/1160, U+17B4/17B5,
U+2800, U+3164, U+FFA0). Non-ASCII space separators (Zs, e.g. U+00A0) become a normal space; line/paragraph
separators (Zl/Zp) become a newline (when newlines are kept) or a space.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

_ANSI_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")
_FILLERS = frozenset("͏ᅟᅠ឴឵᠎⠀ㅤﾠ")
_STRIP_CATS = frozenset(("Cf", "Cs", "Co", "Cn"))


def _is_hidden(ch: str) -> bool:
    cp = ord(ch)
    return (0xE0000 <= cp <= 0xE007F or 0xE0100 <= cp <= 0xE01EF or ch in _FILLERS
            or unicodedata.category(ch) in _STRIP_CATS)


def scrub(value: Any, keep_newlines: bool = False, control_to_space: bool = False) -> str:
    """Return ``value`` as text with ANSI and invisible/format characters removed.

    Tabs and newlines (and Zl/Zp) are kept only with ``keep_newlines``, otherwise they become a space. Other Cc controls are dropped (or become a space with ``control_to_space``).
    """
    if value is None:
        return ""
    text = _ANSI_RE.sub("", value if isinstance(value, str) else str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for ch in text:
        if ch == "\n":
            out.append("\n" if keep_newlines else " ")
        elif ch == "\t":
            out.append("\t" if keep_newlines else " ")
        elif ch == " ":
            out.append(" ")
        elif ch.isascii() and ch.isprintable():
            out.append(ch)
        elif _is_hidden(ch):
            continue
        else:
            cat = unicodedata.category(ch)
            if cat == "Zs":
                out.append(" ")
            elif cat in ("Zl", "Zp"):
                out.append("\n" if keep_newlines else " ")
            elif cat == "Cc":
                if control_to_space:
                    out.append(" ")
            else:
                out.append(ch)
    return "".join(out)


def cap(text: str, limit: Optional[int], marker: str = "...[truncated]") -> str:
    if limit is not None and len(text) > limit:
        return text[: max(0, limit - len(marker))] + marker
    return text


def is_clean(value: str, keep_newlines: bool = False) -> bool:
    """True when sanitizing would not change ``value`` (used for the ``sanitized`` flag)."""
    return scrub(value, keep_newlines) == value
