"""Clipboard backends for Darwin and Linux."""

import subprocess

from sociopsi.platform.base import ClipboardBackend


class DarwinClipboardBackend(ClipboardBackend):
    """macOS clipboard via pbpaste."""

    def read_clipboard(self) -> str | None:
        try:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception:
            return None


class LinuxClipboardBackend(ClipboardBackend):
    """Linux clipboard via xclip (X11) or wl-paste (Wayland)."""

    def read_clipboard(self) -> str | None:
        # Try wl-paste first (Wayland)
        try:
            result = subprocess.run(
                ["wl-paste"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Fallback to xclip (X11)
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass
        except Exception:
            pass

        return None
