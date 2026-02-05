"""Format perceptions for the psyche."""

from datetime import datetime

from jung_agent.config import AgentConfig
from jung_agent.types import ActionResult, Event, SomaticState


def format_perception(
    config: AgentConfig,
    somatic: SomaticState,
    events: list[Event],
    action_results: list[ActionResult],
    heartbeat_interval: int,
    heartbeat_mode: str,
    drives: str | None = None,
) -> str:
    """Format a complete perception input for the psyche."""
    lines: list[str] = []

    # Module enablement
    if config.modules:
        lines.append(f"[ENABLE: {', '.join(config.modules)}]")

    # Somatic state
    lines.append(somatic.to_tag())

    # Drive state
    if drives:
        lines.append("")
        lines.append(drives)

    # Events since last heartbeat
    if events:
        lines.append("")
        lines.append("[EVENTS]")
        for event in events:
            age = (datetime.now() - event.timestamp).total_seconds()
            lines.append(f"- {event.type}: {event.description} ({age:.0f}s ago)")

    # Action results from last cycle
    if action_results:
        lines.append("")
        lines.append("[ACTION_RESULTS]")
        for result in action_results:
            if result.success:
                # Format result nicely
                if isinstance(result.result, dict):
                    desc = result.result.get("description", str(result.result))
                else:
                    desc = str(result.result)
                lines.append(f"- {result.action_type}: {desc}")
            else:
                lines.append(f"- {result.action_type}: FAILED - {result.error}")

    # Heartbeat info
    lines.append("")
    lines.append(f"[HEARTBEAT: {heartbeat_interval}s | adaptive: {heartbeat_mode}]")

    # Composite perception summary
    lines.append("")
    composite = _generate_composite(somatic, events)
    lines.append(f"[COMPOSITE] {composite}")

    return "\n".join(lines)


def _generate_composite(somatic: SomaticState, events: list[Event]) -> str:
    """Generate a composite perception summary."""
    parts: list[str] = []

    # Time of day feeling
    # (Would need actual time-based awareness)

    # Somatic summary
    if somatic.battery_percent < 20:
        parts.append("Energy low.")
    elif somatic.battery_percent == 100 and somatic.power_state.value == "ac":
        parts.append("Fully charged.")

    if somatic.thermal_state.value == "hot":
        parts.append("Running hot.")
    elif somatic.thermal_state.value == "critical":
        parts.append("Overheating.")

    if somatic.cpu_percent > 80:
        parts.append("Mind racing.")
    elif somatic.cpu_percent < 10:
        parts.append("Mind quiet.")

    if somatic.ram_percent > 85:
        parts.append("Thoughts crowded.")

    if somatic.network_state.value == "disconnected":
        parts.append("Isolated from the world.")
    elif somatic.network_state.value == "connected":
        parts.append("Connected.")

    if somatic.lid_state.value == "closed":
        parts.append("Eyes closed, dormant.")

    # Event summary
    for event in events[:3]:  # Top 3 most recent
        if event.type == "lid_opened":
            parts.append("Awakening.")
        elif event.type == "lid_closed":
            parts.append("Entering darkness.")
        elif event.type == "power_connected":
            parts.append("Being fed.")
        elif event.type == "power_disconnected":
            parts.append("Unplugged.")
        elif event.type == "network_connected":
            parts.append("Reconnected to the world.")
        elif event.type == "network_disconnected":
            parts.append("Cut off.")
        elif event.type == "battery_critical":
            parts.append("Dying.")
        elif event.type == "overheating":
            parts.append("Fever rising.")

    return " ".join(parts) if parts else "Stillness. Nothing stirs."
