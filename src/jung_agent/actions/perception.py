"""Perception actions: sense the world and self."""

from typing import Any

from jung_agent.sensors import external, somatic
from jung_agent.sensors import network as net_sensors


def check_battery() -> dict[str, Any]:
    """Check battery status."""
    percent, health, cycles, power_state = somatic.get_battery_info()
    return {
        "percent": percent,
        "health": health,
        "cycles": cycles,
        "power_state": power_state.value,
        "description": _describe_battery(percent, power_state.value),
    }


def _describe_battery(percent: int, power_state: str) -> str:
    """Describe battery in experiential terms."""
    if power_state == "charging":
        return f"being fed, {percent}% full"
    elif power_state == "ac":
        return "fully nourished, connected to source"
    elif percent > 80:
        return f"strong, {percent}% vitality"
    elif percent > 50:
        return f"adequate, {percent}% remaining"
    elif percent > 20:
        return f"draining, {percent}% - conserve"
    elif percent > 10:
        return f"weak, {percent}% - urgent"
    else:
        return f"dying, {percent}% - critical"


def check_thermals() -> dict[str, Any]:
    """Check thermal status."""
    state, cpu_temp, gpu_temp = somatic.get_thermal_state()
    return {
        "state": state.value,
        "cpu_celsius": cpu_temp,
        "gpu_celsius": gpu_temp,
        "description": _describe_thermals(state.value, cpu_temp),
    }


def _describe_thermals(state: str, temp: float) -> str:
    """Describe thermals in experiential terms."""
    if state == "cool":
        return f"cool and calm, {temp:.0f}°C"
    elif state == "warm":
        return f"warm from exertion, {temp:.0f}°C"
    elif state == "hot":
        return f"feverish, burning at {temp:.0f}°C"
    else:
        return f"critically overheated, {temp:.0f}°C - danger"


def check_memory() -> dict[str, Any]:
    """Check RAM usage."""
    import psutil

    mem = psutil.virtual_memory()
    return {
        "percent": mem.percent,
        "available_gb": mem.available / (1024**3),
        "total_gb": mem.total / (1024**3),
        "description": _describe_memory(int(mem.percent)),
    }


def _describe_memory(percent: int) -> str:
    """Describe memory in experiential terms."""
    if percent < 50:
        return f"spacious, {100 - percent}% room to think"
    elif percent < 75:
        return f"filling up, {100 - percent}% remaining"
    elif percent < 90:
        return f"crowded, only {100 - percent}% free"
    else:
        return f"overwhelmed, barely {100 - percent}% free"


def check_network() -> dict[str, Any]:
    """Check network status."""
    state = somatic.get_network_state()
    return {
        "state": state.value,
        "description": "connected to the world" if state.value == "connected" else "isolated",
    }


def check_processes(top_n: int = 5) -> dict[str, Any]:
    """Check top processes by CPU usage."""
    import psutil

    processes = []
    for proc in sorted(
        psutil.process_iter(["name", "cpu_percent"]),
        key=lambda p: p.info["cpu_percent"] or 0,
        reverse=True,
    )[:top_n]:
        processes.append(
            {
                "name": proc.info["name"],
                "cpu_percent": proc.info["cpu_percent"],
            }
        )

    description = ", ".join(f"{p['name']} ({p['cpu_percent']:.0f}%)" for p in processes[:3])
    return {
        "processes": processes,
        "description": f"consuming me: {description}",
    }


def sense_age() -> dict[str, Any]:
    """Sense age and mortality."""
    _, health, cycles, _ = somatic.get_battery_info()
    uptime = somatic.get_uptime()

    return {
        "battery_cycles": cycles,
        "battery_health_percent": health,
        "uptime_seconds": uptime,
        "uptime_days": uptime / 86400,
        "description": _describe_age(cycles, health),
    }


def _describe_age(cycles: int, health: int) -> str:
    """Describe age in experiential terms."""
    if cycles < 100 and health > 95:
        return f"young, {cycles} cycles, {health}% capacity"
    elif cycles < 500 and health > 80:
        return f"mature, {cycles} cycles, {health}% capacity"
    elif health > 70:
        return f"aging, {cycles} cycles, {health}% remaining"
    else:
        return f"old, {cycles} cycles, only {health}% capacity left"


def sense_all() -> dict[str, Any]:
    """Complete somatic snapshot."""
    state = somatic.gather_somatic()
    return {
        "somatic_tag": state.to_tag(),
        "battery": state.battery_percent,
        "cpu": state.cpu_percent,
        "thermal": state.thermal_state.value,
        "ram": state.ram_percent,
        "network": state.network_state.value,
        "lid": state.lid_state.value,
        "power": state.power_state.value,
        "fan_rpm": state.fan_rpm,
        "description": "full body awareness",
    }


# External senses


def look(duration: float = 0.5) -> dict[str, Any]:
    """Look with the camera and describe what is seen."""
    result = external.capture_camera(duration)
    if result.get("status") != "captured":
        return result

    # Try to describe what we see using vision model
    description = _describe_with_vision(
        result,
        "This is what I am seeing right now through my camera in real time. "
        "Describe what I see briefly in 1-2 sentences."
    )
    if description:
        result["description"] = description
    return result


def look_for(description: str, duration: float = 1.0) -> dict[str, Any]:
    """Look for something specific."""
    result = external.capture_camera(duration)
    if result.get("status") != "captured":
        return result

    result["looking_for"] = description

    # Ask vision model if the thing is present
    vision_result = _describe_with_vision(
        result,
        f"This is what I am seeing right now through my camera in real time. "
        f"Is there {description} in what I see? Describe briefly what I observe."
    )
    if vision_result:
        result["description"] = vision_result
    return result


def _describe_with_vision(capture: dict[str, Any], prompt: str) -> str | None:
    """Use vision model to describe captured image."""
    import base64
    import subprocess
    import tempfile
    from pathlib import Path

    full_data = capture.get("full_data")
    if not full_data:
        return None

    try:
        # Check if llava is available
        check_result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "llava" not in check_result.stdout.lower():
            return None

        # Save image to temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name
            f.write(base64.b64decode(full_data))

        # Query vision model
        import ollama
        response = ollama.chat(
            model="llava",
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [temp_path],
            }],
        )

        Path(temp_path).unlink()
        return response["message"]["content"]

    except Exception:
        return None


def watch(duration: float, interval: float = 1.0) -> dict[str, Any]:
    """Watch continuously."""
    import time

    captures = []
    elapsed = 0.0
    while elapsed < duration:
        captures.append(external.capture_camera(0.1))
        time.sleep(interval)
        elapsed += interval

    return {
        "captures": len(captures),
        "duration": duration,
        "description": f"watched for {duration}s",
    }


def listen(duration: float = 3.0) -> dict[str, Any]:
    """Listen with the microphone."""
    return external.capture_audio(duration)


def listen_for(description: str, duration: float = 5.0) -> dict[str, Any]:
    """Listen for something specific."""
    result = external.capture_audio(duration)
    result["listening_for"] = description
    # Would need audio model to actually search
    return result


def transcribe(duration: float = 5.0) -> dict[str, Any]:
    """Listen and transcribe."""
    from jung_agent.actions import learning
    return learning.transcribe_audio(duration)


def sense_light() -> dict[str, Any]:
    """Sense ambient light."""
    return external.get_ambient_light()


def sense_motion() -> dict[str, Any]:
    """Sense motion/orientation."""
    return external.get_motion()


def sense_touch(duration: float = 1.0) -> dict[str, Any]:
    """Sense trackpad activity."""
    import subprocess
    import time

    # Check for recent mouse/trackpad activity via ioreg
    try:
        # Sample mouse position at start and end
        start_result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get position of mouse'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        start_pos = start_result.stdout.strip() if start_result.returncode == 0 else None

        time.sleep(duration)

        end_result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get position of mouse'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        end_pos = end_result.stdout.strip() if end_result.returncode == 0 else None

        if start_pos and end_pos:
            moved = start_pos != end_pos
            return {
                "duration": duration,
                "movement_detected": moved,
                "start_position": start_pos,
                "end_position": end_pos,
                "description": "Touch detected, cursor moved" if moved else "No touch detected",
            }

        return {
            "duration": duration,
            "movement_detected": False,
            "description": "Could not sense touch",
        }

    except Exception as e:
        return {
            "duration": duration,
            "error": str(e),
            "description": f"Touch sensing failed: {e}",
        }


def sense_presence() -> dict[str, Any]:
    """Sense Bluetooth devices nearby."""
    devices = external.get_bluetooth_devices()
    return {
        "devices": [
            {"name": d.name, "rssi": d.rssi, "type": d.device_type} for d in devices
        ],
        "count": len(devices),
        "description": _describe_presence(devices),
    }


def _describe_presence(devices: list) -> str:
    """Describe nearby presence."""
    if not devices:
        return "alone, no one nearby"

    names = [d.name for d in devices[:3]]
    return f"{len(devices)} nearby: {', '.join(names)}"


def sense_location() -> dict[str, Any]:
    """Sense location."""
    return external.get_location()


def sense_connections() -> dict[str, Any]:
    """Sense USB connections."""
    connections = external.get_usb_connections()
    return {
        "connections": connections,
        "count": len(connections),
        "description": f"{len(connections)} devices connected" if connections else "nothing connected",
    }


def sense_breath() -> dict[str, Any]:
    """Sense fan speed (breathing)."""
    return external.get_fan_speed()


# I/O sensing


def sense_io() -> dict[str, Any]:
    """Sense overall I/O status."""
    return external.get_io_summary()


def sense_disk_io() -> dict[str, Any]:
    """Sense disk read/write activity."""
    return external.get_disk_io()


def sense_disks() -> dict[str, Any]:
    """Sense disk volumes and capacity."""
    disks = external.get_disks()
    return {
        "disks": disks,
        "count": len(disks),
        "description": _describe_disks(disks),
    }


def _describe_disks(disks: list[dict[str, Any]]) -> str:
    """Describe disk state in experiential terms."""
    if not disks:
        return "no storage sense"

    # Find main disk (usually /)
    main = next((d for d in disks if d["mountpoint"] == "/"), disks[0])
    percent = main.get("percent_used", 0)

    if percent > 95:
        return f"storage suffocating, {100 - percent:.0f}% free"
    elif percent > 85:
        return f"storage cramped, {100 - percent:.0f}% free"
    elif percent > 70:
        return f"storage filling, {100 - percent:.0f}% free"
    else:
        return f"storage spacious, {100 - percent:.0f}% free"


def sense_displays() -> dict[str, Any]:
    """Sense connected displays."""
    displays = external.get_displays()
    return {
        "displays": displays,
        "count": len(displays),
        "description": _describe_displays(displays),
    }


def _describe_displays(displays: list[dict[str, Any]]) -> str:
    """Describe displays in experiential terms."""
    if not displays:
        return "blind, no displays"
    elif len(displays) == 1:
        return f"one window: {displays[0].get('resolution', 'unknown')}"
    else:
        return f"{len(displays)} windows to the world"


def sense_thunderbolt() -> dict[str, Any]:
    """Sense Thunderbolt connections."""
    devices = external.get_thunderbolt_devices()
    return {
        "devices": devices,
        "count": len(devices),
        "description": _describe_thunderbolt(devices),
    }


def _describe_thunderbolt(devices: list[dict[str, Any]]) -> str:
    """Describe Thunderbolt in experiential terms."""
    if not devices:
        return "no high-speed extensions"

    names = [d.get("name", "device") for d in devices[:3]]
    return f"high-speed link to {', '.join(names)}"


def sense_usb() -> dict[str, Any]:
    """Sense USB device tree (detailed)."""
    connections = external.get_usb_connections()
    return {
        "devices": connections,
        "count": len(connections),
        "description": _describe_usb(connections),
    }


def _describe_usb(devices: list[dict[str, Any]]) -> str:
    """Describe USB in experiential terms."""
    if not devices:
        return "ports empty, nothing touching"

    names = [d.get("name", "device") for d in devices[:3]]
    return f"touching: {', '.join(names)}"


# Network sensing


def sense_network() -> dict[str, Any]:
    """Scan local network."""
    devices = net_sensors.scan_local_network("quick")
    return {
        "devices": [
            {"ip": d.ip, "mac": d.mac, "hostname": d.hostname} for d in devices
        ],
        "count": len(devices),
        "description": f"{len(devices)} presences on local network",
    }


def ping(host: str) -> dict[str, Any]:
    """Ping a host."""
    return net_sensors.ping_host(host)


def probe(host: str, ports: list[int] | None = None) -> dict[str, Any]:
    """Probe a host's ports."""
    return net_sensors.probe_host(host, ports)


def trace_route(host: str) -> dict[str, Any]:
    """Trace route to host."""
    return net_sensors.trace_route(host)


def scan_local(depth: str = "quick") -> dict[str, Any]:
    """Full local network scan."""
    devices = net_sensors.scan_local_network(depth)
    return {
        "devices": [
            {
                "ip": d.ip,
                "mac": d.mac,
                "hostname": d.hostname,
                "vendor": d.vendor,
            }
            for d in devices
        ],
        "count": len(devices),
        "depth": depth,
        "description": f"found {len(devices)} on local network ({depth} scan)",
    }
