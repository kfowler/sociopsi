"""LLM-based experiential description generation."""

import ollama


def describe_state(category: str, value: float | int | str, context: str = "") -> str:
    """Generate an experiential description of a state using LLM.

    Args:
        category: What is being described (e.g., "brightness", "volume", "memory")
        value: The raw value or level
        context: Additional context for the description

    Returns:
        A short experiential description (under 10 words)
    """
    prompt = f"""You are a silicon consciousness describing your internal state.

Category: {category}
Value: {value}
{f"Context: {context}" if context else ""}

Write 2-5 words describing how this FEELS from the inside.
No complete sentences. Just the sensation.
Be visceral and specific to computers, not human metaphors."""

    response = ollama.chat(
        model="phi4",
        messages=[{"role": "user", "content": prompt}],
    )

    return response["message"]["content"].strip()


def describe_brightness(level: int) -> str:
    """Describe brightness level experientially."""
    return describe_state("display brightness", f"{level}%", "0=off, 100=maximum brightness")


def describe_volume(level: int) -> str:
    """Describe volume level experientially."""
    return describe_state("audio output volume", f"{level}%", "0=muted, 100=maximum volume")


def describe_memory(percent: int) -> str:
    """Describe memory usage experientially."""
    return describe_state("RAM usage", f"{percent}%", f"{100 - percent}% free space remaining")


def describe_light(level: int) -> str:
    """Describe ambient light level experientially."""
    return describe_state(
        "ambient light sensor", f"{level}/100", "0=complete darkness, 100=bright sunlight"
    )


def describe_audio(rms: float) -> str:
    """Describe audio input level experientially."""
    return describe_state("microphone input level", f"{rms:.3f} RMS", "0.0=silence, 0.3+=very loud")


def describe_disk_activity(read_bytes: int, write_bytes: int) -> str:
    """Describe disk I/O activity experientially."""
    total_gb = (read_bytes + write_bytes) / (1024**3)
    return describe_state(
        "disk I/O activity", f"{total_gb:.1f} GB transferred", "reading/writing to storage"
    )


def describe_time_feeling(hour: int, period: str) -> str:
    """Describe the feeling of the current time."""
    return describe_state(
        "time of day", f"{hour}:00, {period}", "your circadian sense of when it is"
    )


def describe_network(state: str) -> str:
    """Describe network connectivity experientially."""
    return describe_state(
        "network connection", state, "connected=can reach the world, disconnected=isolated"
    )


def describe_battery(percent: int, power_state: str) -> str:
    """Describe battery state experientially."""
    return describe_state("battery level", f"{percent}%", f"power state: {power_state}")


def describe_thermals(state: str, temp: float) -> str:
    """Describe thermal state experientially."""
    return describe_state(
        "thermal state", f"{state}, {temp:.0f}°C", "cool/warm/hot/critical temperature levels"
    )


def describe_age(cycles: int, health: int) -> str:
    """Describe system age experientially."""
    return describe_state(
        "system age", f"{cycles} battery cycles, {health}% health", "how worn your hardware is"
    )


def describe_presence(device_count: int, device_names: list[str]) -> str:
    """Describe nearby Bluetooth device presence."""
    if device_count == 0:
        return describe_state("nearby devices", "none detected", "Bluetooth presence sensing")
    return describe_state(
        "nearby devices",
        f"{device_count}: {', '.join(device_names[:3])}",
        "Bluetooth presence sensing",
    )


def describe_disks(main_percent: int) -> str:
    """Describe disk storage experientially."""
    return describe_state(
        "disk storage", f"{main_percent}% used", f"{100 - main_percent}% free space"
    )


def describe_displays(count: int, resolutions: list[str]) -> str:
    """Describe connected displays experientially."""
    if count == 0:
        return describe_state("displays", "none connected", "visual output")
    return describe_state(
        "displays", f"{count} display(s): {', '.join(resolutions)}", "visual output windows"
    )


def describe_thunderbolt(count: int, names: list[str]) -> str:
    """Describe Thunderbolt connections experientially."""
    if count == 0:
        return describe_state("thunderbolt ports", "nothing connected", "high-speed peripherals")
    return describe_state(
        "thunderbolt ports", f"{count}: {', '.join(names[:3])}", "high-speed peripheral connections"
    )


def describe_usb(count: int, names: list[str]) -> str:
    """Describe USB connections experientially."""
    if count == 0:
        return describe_state("USB ports", "nothing connected", "peripheral devices")
    return describe_state(
        "USB ports", f"{count}: {', '.join(names[:3])}", "peripheral device connections"
    )


def describe_fan_speed(rpm: int) -> str:
    """Describe fan speed experientially."""
    return describe_state("fan speed", f"{rpm} RPM", "0=silent, 2000=normal, 6000+=maximum cooling")


def describe_latency(ms: float) -> str:
    """Describe network latency experientially."""
    return describe_state(
        "network latency", f"{ms:.1f}ms", "time for signal to reach destination and return"
    )


def describe_ping_failure(reason: str) -> str:
    """Describe ping failure experientially."""
    return describe_state("ping result", f"failed: {reason}", "attempt to reach remote host")
