"""Runtime helpers shared by Capsule's Python entry points."""

import sys


def configure_utf8_stdio() -> None:
    """Keep human-readable output UTF-8 in consoles, pipes, and redirected files."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
