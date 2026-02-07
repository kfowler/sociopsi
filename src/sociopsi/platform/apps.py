"""Application control backends for Darwin and Linux."""

import shutil
import subprocess

from sociopsi.platform.base import AppBackend


class DarwinAppBackend(AppBackend):
    """macOS app control via open/osascript."""

    def open_app(self, name: str) -> dict:
        try:
            subprocess.run(
                ["open", "-a", name],
                capture_output=True,
                timeout=10,
            )
            return {"opened": True, "app": name}
        except Exception as e:
            return {"error": str(e)}

    def close_app(self, name: str) -> dict:
        try:
            script = f'''
            tell application "{name}"
                quit
            end tell
            '''
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=10,
            )
            return {"closed": True, "app": name}
        except Exception as e:
            return {"error": str(e)}


class LinuxAppBackend(AppBackend):
    """Linux app control via xdg-open/wmctrl/pkill."""

    def open_app(self, name: str) -> dict:
        try:
            subprocess.Popen(
                ["xdg-open", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"opened": True, "app": name}
        except FileNotFoundError:
            # Fallback: try running the command directly
            try:
                subprocess.Popen(
                    [name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return {"opened": True, "app": name}
            except Exception as e:
                return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def close_app(self, name: str) -> dict:
        # Try wmctrl first (graceful close)
        if shutil.which("wmctrl"):
            try:
                result = subprocess.run(
                    ["wmctrl", "-c", name],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return {"closed": True, "app": name}
            except Exception:
                pass

        # Fallback to pkill
        try:
            subprocess.run(
                ["pkill", "-f", name],
                capture_output=True,
                timeout=5,
            )
            return {"closed": True, "app": name}
        except Exception as e:
            return {"error": str(e)}
