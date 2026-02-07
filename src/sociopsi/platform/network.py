"""Network control backends for Darwin and Linux."""

import subprocess

from sociopsi.platform.base import NetworkControlBackend


class DarwinNetworkBackend(NetworkControlBackend):
    """macOS network control via networksetup."""

    def connect_wifi(self, ssid: str | None = None) -> dict:
        try:
            # Get the WiFi interface name
            result = subprocess.run(
                ["networksetup", "-listallhardwareports"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            wifi_device = None
            lines = result.stdout.split("\n")
            for i, line in enumerate(lines):
                if "Wi-Fi" in line:
                    for j in range(i, min(i + 3, len(lines))):
                        if "Device:" in lines[j]:
                            wifi_device = lines[j].split(":")[-1].strip()
                            break
                    break

            if not wifi_device:
                return {"error": "WiFi device not found"}

            # Enable the interface
            subprocess.run(
                ["networksetup", "-setairportpower", wifi_device, "on"],
                capture_output=True,
                timeout=5,
            )

            if ssid:
                # Connect to specific SSID
                subprocess.run(
                    ["networksetup", "-setairportnetwork", wifi_device, ssid],
                    capture_output=True,
                    timeout=10,
                )
                return {"connected": True, "device": wifi_device, "ssid": ssid}

            return {"connected": True, "device": wifi_device}
        except Exception as e:
            return {"error": str(e)}

    def list_interfaces(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["networksetup", "-listallhardwareports"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            interfaces = []
            lines = result.stdout.split("\n")
            i = 0
            while i < len(lines):
                if lines[i].startswith("Hardware Port:"):
                    port = lines[i].split(":", 1)[1].strip()
                    device = ""
                    if i + 1 < len(lines) and "Device:" in lines[i + 1]:
                        device = lines[i + 1].split(":", 1)[1].strip()
                    interfaces.append({"name": port, "device": device})
                i += 1
            return interfaces
        except Exception:
            return []


class LinuxNetworkBackend(NetworkControlBackend):
    """Linux network control via nmcli/ip."""

    def connect_wifi(self, ssid: str | None = None) -> dict:
        try:
            if ssid:
                result = subprocess.run(
                    ["nmcli", "device", "wifi", "connect", ssid],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    return {"connected": True, "ssid": ssid}
                return {"error": result.stderr.strip()}
            else:
                # Enable WiFi
                subprocess.run(
                    ["nmcli", "radio", "wifi", "on"],
                    capture_output=True,
                    timeout=5,
                )
                return {"connected": True}
        except FileNotFoundError:
            return {"error": "nmcli not found"}
        except Exception as e:
            return {"error": str(e)}

    def list_interfaces(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["ip", "-j", "link", "show"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)
                return [
                    {
                        "name": iface.get("ifname", ""),
                        "device": iface.get("ifname", ""),
                        "state": iface.get("operstate", "unknown"),
                    }
                    for iface in data
                ]
        except Exception:
            pass

        # Fallback: plain ip link
        try:
            result = subprocess.run(
                ["ip", "link", "show"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            interfaces = []
            for line in result.stdout.split("\n"):
                if ": " in line and not line.startswith(" "):
                    parts = line.split(": ")
                    if len(parts) >= 2:
                        interfaces.append({"name": parts[1], "device": parts[1]})
            return interfaces
        except Exception:
            return []
