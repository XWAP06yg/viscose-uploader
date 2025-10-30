from __future__ import annotations

try:
    from colorama import init as colorama_init  # type: ignore

    colorama_init()
except Exception:
    # colorama is optional; fall back to raw ANSI sequences when unavailable.
    pass

RESET = "\033[0m"
BOLD = "\033[1m"
ACCENT = "\033[96m"  # cyan
SUCCESS = "\033[92m"  # green
INFO = "\033[94m"  # blue
WARNING = "\033[93m"  # yellow
ERROR = "\033[91m"  # red
PROMPT = "\033[95m"  # magenta
MUTED = "\033[90m"  # dim gray
