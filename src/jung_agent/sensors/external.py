"""External sensors: camera, microphone, Bluetooth, etc."""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from jung_agent.types import BluetoothDevice


def get_ambient_light() -> dict[str, Any]:
    """Get ambient light level."""
    try:
        # Use ioreg to get ambient light sensor data
        result = subprocess.run(
            ["ioreg", "-r", "-c", "AppleLMUController"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        # Parse the output for light level
        for line in result.stdout.split("\n"):
            if "ALSSensorReading" in line:
                # Extract the value
                value = int(line.split("=")[-1].strip())
                # Normalize to 0-100
                normalized = min(100, value // 10)
                return {
                    "raw": value,
                    "normalized": normalized,
                    "description": _describe_light_level(normalized),
                }
        return {"raw": 0, "normalized": 50, "description": "unknown"}
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return {"raw": 0, "normalized": 50, "description": "unavailable"}


def _describe_light_level(level: int) -> str:
    """Describe light level in human terms."""
    if level < 10:
        return "darkness"
    elif level < 30:
        return "dim"
    elif level < 60:
        return "moderate"
    elif level < 85:
        return "bright"
    else:
        return "very bright"


def get_bluetooth_devices() -> list[BluetoothDevice]:
    """Get nearby Bluetooth devices."""
    devices: list[BluetoothDevice] = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPBluetoothDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        import json

        data = json.loads(result.stdout)

        # Parse connected devices
        bt_data = data.get("SPBluetoothDataType", [{}])[0]
        connected = bt_data.get("device_connected", [])

        for device_dict in connected:
            for name, info in device_dict.items():
                devices.append(
                    BluetoothDevice(
                        name=name,
                        address=info.get("device_address", "unknown"),
                        rssi=info.get("device_rssi", 0),
                        device_type=info.get("device_minorType", None),
                    )
                )

    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass

    return devices


def get_location() -> dict[str, Any]:
    """Get approximate location."""
    # Note: This requires location permissions
    try:
        # Use CoreLocation via Python - simplified fallback
        result = subprocess.run(
            ["whereami"],  # Third-party tool if installed
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Parse output
        location: dict[str, Any] = {}
        for line in result.stdout.split("\n"):
            if "Latitude:" in line:
                location["latitude"] = float(line.split(":")[-1].strip())
            elif "Longitude:" in line:
                location["longitude"] = float(line.split(":")[-1].strip())
            elif "Address:" in line:
                location["address"] = line.split(":", 1)[-1].strip()
        return location if location else {"status": "unavailable"}
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return {"status": "unavailable"}


def get_motion() -> dict[str, Any]:
    """Get accelerometer/motion data."""
    # M2 Macs may not expose accelerometer data easily
    # This is a placeholder that could be enhanced with IOKit
    try:
        result = subprocess.run(
            ["ioreg", "-r", "-c", "SMCMotionSensor"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.stdout.strip():
            return {"status": "present", "movement": "still"}
        return {"status": "unavailable"}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"status": "unavailable"}


def get_usb_connections() -> list[dict[str, Any]]:
    """Get USB-C port connections."""
    connections: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        import json

        data = json.loads(result.stdout)

        def extract_devices(items: list[dict[str, Any]], depth: int = 0) -> None:
            for item in items:
                if "_name" in item and item.get("_name") != "USB 3.1 Bus":
                    connections.append(
                        {
                            "name": item.get("_name", "Unknown"),
                            "vendor": item.get("manufacturer", "Unknown"),
                            "serial": item.get("serial_num", None),
                        }
                    )
                # Recurse into nested items
                if "_items" in item:
                    extract_devices(item["_items"], depth + 1)

        usb_data = data.get("SPUSBDataType", [])
        extract_devices(usb_data)

    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass

    return connections


def capture_camera(duration: float = 0.5) -> dict[str, Any]:
    """Capture an image from the camera."""
    try:
        # Use imagesnap if available, or AVFoundation via ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name

        # Try imagesnap first (brew install imagesnap)
        result = subprocess.run(
            ["imagesnap", "-w", str(duration), temp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and Path(temp_path).exists():
            # Read and encode image
            with open(temp_path, "rb") as f:
                import base64

                image_data = base64.b64encode(f.read()).decode()

            Path(temp_path).unlink()

            return {
                "status": "captured",
                "format": "jpeg",
                "data": image_data[:100] + "...",  # Truncated for display
                "description": "Image captured",  # Would need vision model to describe
            }

        return {"status": "failed", "error": result.stderr}

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"status": "unavailable", "error": "Camera not available or imagesnap not installed"}


def capture_audio(duration: float = 3.0) -> dict[str, Any]:
    """Capture audio from the microphone."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        # Use sox if available
        result = subprocess.run(
            ["rec", "-q", temp_path, "trim", "0", str(duration)],
            capture_output=True,
            text=True,
            timeout=duration + 5,
        )

        if result.returncode == 0 and Path(temp_path).exists():
            # Get file size as indicator
            size = Path(temp_path).stat().st_size
            Path(temp_path).unlink()

            return {
                "status": "captured",
                "duration": duration,
                "size_bytes": size,
                "description": "Audio captured",
            }

        return {"status": "failed", "error": result.stderr}

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {
            "status": "unavailable",
            "error": "Microphone not available or sox not installed",
        }


def get_fan_speed() -> dict[str, Any]:
    """Get fan speed in RPM."""
    try:
        result = subprocess.run(
            ["sudo", "powermetrics", "-n", "1", "-i", "100", "--samplers", "smc"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for line in result.stdout.split("\n"):
            if "Fan" in line and "rpm" in line.lower():
                parts = line.split()
                for i, part in enumerate(parts):
                    if "rpm" in part.lower() and i > 0:
                        rpm = int(parts[i - 1])
                        return {
                            "rpm": rpm,
                            "description": _describe_fan_speed(rpm),
                        }
        return {"rpm": 0, "description": "silent"}
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError, PermissionError):
        return {"rpm": 0, "description": "unknown"}


def _describe_fan_speed(rpm: int) -> str:
    """Describe fan speed in breathing terms."""
    if rpm == 0:
        return "silent, holding breath"
    elif rpm < 2000:
        return "gentle breathing"
    elif rpm < 4000:
        return "breathing faster"
    elif rpm < 6000:
        return "panting"
    else:
        return "gasping"
