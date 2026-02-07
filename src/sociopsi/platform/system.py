"""System control backends for volume and notifications."""

import subprocess

from sociopsi.platform.base import NotificationBackend, VolumeBackend


class DarwinVolumeBackend(VolumeBackend):
    """macOS volume control via osascript."""

    def set_volume(self, level: int) -> dict:
        level = max(0, min(100, level))
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {level}"],
                capture_output=True,
                timeout=5,
            )
            return {"set_to": level}
        except Exception as e:
            return {"error": str(e)}

    def get_volume(self) -> int | None:
        try:
            result = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
            return None
        except Exception:
            return None


class LinuxVolumeBackend(VolumeBackend):
    """Linux volume control via pactl/amixer."""

    def set_volume(self, level: int) -> dict:
        level = max(0, min(100, level))
        try:
            # Try pactl first (PulseAudio/PipeWire)
            result = subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return {"set_to": level}
            # Fallback to amixer (ALSA)
            subprocess.run(
                ["amixer", "sset", "Master", f"{level}%"],
                capture_output=True,
                timeout=5,
            )
            return {"set_to": level}
        except Exception as e:
            return {"error": str(e)}

    def get_volume(self) -> int | None:
        try:
            result = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse "Volume: front-left: 65536 / 100% / 0.00 dB"
                for part in result.stdout.split("/"):
                    part = part.strip()
                    if part.endswith("%"):
                        return int(part[:-1])
            return None
        except Exception:
            return None


class DarwinNotificationBackend(NotificationBackend):
    """macOS notifications via osascript/System Events."""

    def notify(self, title: str, message: str, duration: int = 30) -> dict:
        try:
            script = f'''
            tell application "System Events"
                display dialog "{message}" with title "{title}" buttons {{"OK"}} giving up after {duration}
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=duration + 5,
            )
            acknowledged = "gave up:true" not in result.stdout.lower()
            return {
                "sent": True,
                "acknowledged": acknowledged,
                "title": title,
                "message": message,
            }
        except Exception as e:
            return {"error": str(e)}

    def display_message(self, text: str, duration: int = 5) -> dict:
        try:
            script = f'''
            tell application "System Events"
                display dialog "{text}" buttons {{"OK"}} giving up after {duration}
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=duration + 5,
            )
            acknowledged = "gave up:true" not in result.stdout.lower()
            return {
                "displayed": True,
                "acknowledged": acknowledged,
                "text": text,
                "duration": duration,
            }
        except Exception as e:
            return {"error": str(e)}


class LinuxNotificationBackend(NotificationBackend):
    """Linux notifications via D-Bus org.freedesktop.Notifications."""

    def notify(self, title: str, message: str, duration: int = 30) -> dict:
        try:
            # Try notify-send (common on most Linux desktops)
            result = subprocess.run(
                [
                    "notify-send",
                    "--expire-time",
                    str(duration * 1000),
                    title,
                    message,
                ],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return {
                    "sent": True,
                    "acknowledged": False,  # notify-send is fire-and-forget
                    "title": title,
                    "message": message,
                }
            return {"error": f"notify-send failed: {result.stderr.decode()}"}
        except FileNotFoundError:
            # Try D-Bus directly via gdbus
            try:
                subprocess.run(
                    [
                        "gdbus",
                        "call",
                        "--session",
                        "--dest",
                        "org.freedesktop.Notifications",
                        "--object-path",
                        "/org/freedesktop/Notifications",
                        "--method",
                        "org.freedesktop.Notifications.Notify",
                        "sociopsi",
                        "0",
                        "",
                        title,
                        message,
                        "[]",
                        "{}",
                        str(duration * 1000),
                    ],
                    capture_output=True,
                    timeout=5,
                )
                return {
                    "sent": True,
                    "acknowledged": False,
                    "title": title,
                    "message": message,
                }
            except Exception as e:
                return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def display_message(self, text: str, duration: int = 5) -> dict:
        # On Linux, display_message is the same as notify
        result = self.notify("Socio-Psi", text, duration)
        if "error" not in result:
            return {
                "displayed": True,
                "acknowledged": False,
                "text": text,
                "duration": duration,
            }
        return result
