"""Screenshot backends for Darwin and Linux."""

import shutil
import subprocess

from sociopsi.platform.base import ScreenshotBackend


class DarwinScreenshotBackend(ScreenshotBackend):
    """macOS screenshot via screencapture."""

    def take_screenshot(self, path: str) -> bool:
        try:
            result = subprocess.run(
                ["screencapture", "-x", path],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False


class LinuxScreenshotBackend(ScreenshotBackend):
    """Linux screenshot via scrot/gnome-screenshot/spectacle."""

    def take_screenshot(self, path: str) -> bool:
        # Try tools in order of preference
        tools = [
            ["scrot", path],
            ["gnome-screenshot", "-f", path],
            ["spectacle", "-b", "-n", "-o", path],
        ]

        for cmd in tools:
            if shutil.which(cmd[0]) is None:
                continue
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                continue

        return False
