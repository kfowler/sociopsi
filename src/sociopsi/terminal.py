"""Terminal output utilities with ANSI color codes."""

import os
import sys
from typing import Final

# Check if we're in a terminal that supports colors
_SUPPORTS_COLOR = (
    hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.getenv("TERM") != "dumb"
)


class Colors:
    """ANSI color codes for terminal output.

    All colors will be empty strings if the terminal doesn't support colors.
    """

    RESET: Final[str] = "\033[0m" if _SUPPORTS_COLOR else ""
    BOLD: Final[str] = "\033[1m" if _SUPPORTS_COLOR else ""
    DIM: Final[str] = "\033[2m" if _SUPPORTS_COLOR else ""

    # Basic colors
    RED: Final[str] = "\033[31m" if _SUPPORTS_COLOR else ""
    GREEN: Final[str] = "\033[32m" if _SUPPORTS_COLOR else ""
    YELLOW: Final[str] = "\033[33m" if _SUPPORTS_COLOR else ""
    BLUE: Final[str] = "\033[34m" if _SUPPORTS_COLOR else ""
    MAGENTA: Final[str] = "\033[35m" if _SUPPORTS_COLOR else ""
    CYAN: Final[str] = "\033[36m" if _SUPPORTS_COLOR else ""
    WHITE: Final[str] = "\033[37m" if _SUPPORTS_COLOR else ""


# Singleton instance for convenience
colors = Colors()
