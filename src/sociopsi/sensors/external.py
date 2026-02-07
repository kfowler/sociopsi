"""External sensors: camera, microphone, Bluetooth, etc."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sociopsi.platform import get_device_backend, get_display_backend, get_thermal_backend
from sociopsi.types import BluetoothDevice

logger = logging.getLogger(__name__)


def get_ambient_light() -> dict[str, Any]:
    """Get ambient light level."""
    backend = get_device_backend()
    raw = backend.get_ambient_light()
    if raw is None:
        return {"raw": 0, "normalized": 50, "description": "unavailable"}
    normalized = min(100, raw // 10)
    return {
        "raw": raw,
        "normalized": normalized,
        "description": _describe_light_level(normalized),
    }


def _describe_light_level(level: int) -> str:
    """Describe light level experientially."""
    from sociopsi.describe import describe_light

    return describe_light(level)


def get_bluetooth_devices() -> list[BluetoothDevice]:
    """Get nearby Bluetooth devices."""
    backend = get_device_backend()
    return backend.list_bluetooth()


def get_location() -> dict[str, Any]:
    """Get approximate location."""
    # Try whereami tool first (precise, needs location permissions)
    try:
        result = subprocess.run(
            ["whereami"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            location: dict[str, Any] = {}
            for line in result.stdout.split("\n"):
                if "Latitude:" in line:
                    location["latitude"] = float(line.split(":")[-1].strip())
                elif "Longitude:" in line:
                    location["longitude"] = float(line.split(":")[-1].strip())
                elif "Address:" in line:
                    location["address"] = line.split(":", 1)[-1].strip()
            if location:
                location["source"] = "gps"
                location["description"] = f"Located at {location.get('address', 'unknown address')}"
                return location
    except subprocess.TimeoutExpired, ValueError, FileNotFoundError:
        pass

    # Fallback: IP-based geolocation
    try:
        import json as json_lib

        result = subprocess.run(
            ["curl", "-s", "https://ipinfo.io/json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json_lib.loads(result.stdout)
            loc = data.get("loc", "").split(",")
            return {
                "city": data.get("city", "unknown"),
                "region": data.get("region", "unknown"),
                "country": data.get("country", "unknown"),
                "latitude": float(loc[0]) if len(loc) == 2 else None,
                "longitude": float(loc[1]) if len(loc) == 2 else None,
                "source": "ip",
                "description": f"Approximately in {data.get('city', 'unknown')}, {data.get('region', '')}",
            }
    except subprocess.TimeoutExpired:
        logger.warning("IP geolocation timed out")
    except json.JSONDecodeError as e:
        logger.warning(f"IP geolocation returned invalid JSON: {e}")
    except FileNotFoundError:
        logger.warning("curl not found")
    except (ValueError, OSError) as e:
        logger.warning(f"IP geolocation error: {e}")

    return {"status": "unavailable", "description": "Could not determine location"}


def get_motion() -> dict[str, Any]:
    """Get accelerometer/motion data."""
    backend = get_device_backend()
    data = backend.get_motion()
    if data is None:
        return {"status": "unavailable"}
    return data


def get_usb_connections() -> list[dict[str, Any]]:
    """Get USB-C port connections."""
    backend = get_device_backend()
    devices = backend.list_usb()
    return [
        {
            "name": d.name,
            "vendor": d.vendor,
            "serial": d.serial,
        }
        for d in devices
    ]


def capture_camera(duration: float = 0.5) -> dict[str, Any]:
    """Capture an image from the camera."""
    import time

    try:
        import cv2

        # Open the default camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return {"status": "unavailable", "description": "Camera not available"}

        # Let camera warm up
        time.sleep(duration)

        # Capture frame
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"status": "failed", "description": "Failed to capture frame"}

        # Get frame info
        height, width = frame.shape[:2]

        # Save to temp file for potential vision processing
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name
        cv2.imwrite(temp_path, frame)

        # Encode for storage
        import base64

        with open(temp_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        Path(temp_path).unlink()

        return {
            "status": "captured",
            "format": "jpeg",
            "width": width,
            "height": height,
            "data": image_data[:100] + "...",  # Truncated for display
            "full_data": image_data,  # Full data for vision model
            "description": f"Captured {width}x{height} image",
        }

    except ImportError:
        return {"status": "unavailable", "description": "opencv not installed"}
    except Exception as e:
        return {"status": "failed", "error": str(e), "description": f"Camera error: {e}"}


def capture_audio(duration: float = 3.0) -> dict[str, Any]:
    """Capture audio from the microphone."""
    try:
        import numpy as np
        import sounddevice as sd
        import soundfile as sf

        sample_rate = 44100

        # Record audio
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.float32,
        )
        sd.wait()  # Wait until recording is finished

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        sf.write(temp_path, recording, sample_rate)
        size = Path(temp_path).stat().st_size

        # Calculate audio level (RMS)
        rms = float(np.sqrt(np.mean(recording**2)))
        peak = float(np.max(np.abs(recording)))

        return {
            "status": "captured",
            "duration": duration,
            "size_bytes": size,
            "sample_rate": sample_rate,
            "rms_level": rms,
            "peak_level": peak,
            "temp_path": temp_path,  # Keep for transcription
            "description": _describe_audio_level(rms),
        }

    except ImportError:
        return {"status": "unavailable", "description": "sounddevice not installed"}
    except Exception as e:
        return {"status": "failed", "error": str(e), "description": f"Microphone error: {e}"}


def _describe_audio_level(rms: float) -> str:
    """Describe audio level experientially."""
    from sociopsi.describe import describe_audio

    return describe_audio(rms)


def get_fan_speed() -> dict[str, Any]:
    """Get fan speed in RPM."""
    backend = get_thermal_backend()
    rpm = backend.get_fan_speed()
    if rpm is None:
        return {"rpm": 0, "description": "unknown"}
    if rpm == 0:
        return {"rpm": 0, "description": "silent"}
    return {"rpm": rpm, "description": _describe_fan_speed(rpm)}


def _describe_fan_speed(rpm: int) -> str:
    """Describe fan speed experientially."""
    from sociopsi.describe import describe_fan_speed

    return describe_fan_speed(rpm)


def get_disk_io() -> dict[str, Any]:
    """Get disk I/O activity."""
    try:
        import psutil

        counters = psutil.disk_io_counters()
        if counters:
            return {
                "read_bytes": counters.read_bytes,
                "write_bytes": counters.write_bytes,
                "read_count": counters.read_count,
                "write_count": counters.write_count,
                "read_mb": counters.read_bytes / (1024 * 1024),
                "write_mb": counters.write_bytes / (1024 * 1024),
                "description": _describe_disk_activity(counters.read_bytes, counters.write_bytes),
            }
        return {"status": "unavailable"}
    except ImportError:
        logger.warning("psutil not available for disk I/O")
        return {"status": "unavailable"}
    except PermissionError as e:
        logger.warning(f"Disk I/O permission error: {e}")
        return {"status": "unavailable"}
    except OSError as e:
        logger.warning(f"Disk I/O error: {e}")
        return {"status": "unavailable"}


def _describe_disk_activity(read: int, write: int) -> str:
    """Describe disk activity experientially."""
    from sociopsi.describe import describe_disk_activity

    return describe_disk_activity(read, write)


def get_disks() -> list[dict[str, Any]]:
    """Get disk/volume information."""
    disks: list[dict[str, Any]] = []
    try:
        import psutil

        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append(
                    {
                        "mountpoint": partition.mountpoint,
                        "device": partition.device,
                        "fstype": partition.fstype,
                        "total_gb": usage.total / (1024**3),
                        "used_gb": usage.used / (1024**3),
                        "free_gb": usage.free / (1024**3),
                        "percent_used": usage.percent,
                    }
                )
            except (PermissionError, OSError) as e:
                logger.debug(f"Could not access partition {partition.mountpoint}: {e}")
    except ImportError:
        logger.warning("psutil not available for disk info")
    except OSError as e:
        logger.warning(f"Disk info error: {e}")
    return disks


def get_displays() -> list[dict[str, Any]]:
    """Get connected displays."""
    backend = get_display_backend()
    infos = backend.list_displays()
    return [
        {
            "name": d.name,
            "resolution": d.resolution,
            "type": d.connection_type,
            "main": d.is_main,
            "mirror": d.mirror,
        }
        for d in infos
    ]


def get_thunderbolt_devices() -> list[dict[str, Any]]:
    """Get Thunderbolt device connections."""
    backend = get_device_backend()
    devices = backend.list_thunderbolt()
    return [
        {
            "name": d.name,
            "vendor": d.vendor,
            "device_id": d.device_id,
            "speed": d.speed,
        }
        for d in devices
    ]


def get_io_summary() -> dict[str, Any]:
    """Get comprehensive I/O status summary."""
    usb = get_usb_connections()
    thunderbolt = get_thunderbolt_devices()
    displays = get_displays()
    disks = get_disks()
    disk_io = get_disk_io()

    # Build summary
    connections = []
    if usb:
        connections.extend([f"USB: {d['name']}" for d in usb[:3]])
    if thunderbolt:
        connections.extend([f"TB: {d['name']}" for d in thunderbolt[:2]])
    if len(displays) > 1:
        connections.append(f"{len(displays)} displays")

    return {
        "usb_count": len(usb),
        "thunderbolt_count": len(thunderbolt),
        "display_count": len(displays),
        "disk_count": len(disks),
        "disk_io": disk_io,
        "connections": connections,
        "description": _describe_io_state(len(usb), len(thunderbolt), len(displays)),
    }


def _describe_io_state(usb: int, tb: int, displays: int) -> str:
    """Describe I/O state in experiential terms."""
    total = usb + tb
    if total == 0 and displays == 1:
        return "alone, unextended"
    elif total == 0:
        return f"unextended, {displays} windows to the world"
    elif total < 3:
        return f"{total} extensions reaching out"
    else:
        return f"well-connected, {total} extensions"
