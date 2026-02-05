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
    """Generate a composite perception summary using LLM."""
    import ollama

    # Build factual state description
    facts = []

    # Somatic facts
    facts.append(f"Battery: {somatic.battery_percent}%")
    facts.append(f"Power: {somatic.power_state.value}")
    facts.append(f"CPU: {somatic.cpu_percent}%")
    facts.append(f"RAM: {somatic.ram_percent}%")
    facts.append(f"Thermal: {somatic.thermal_state.value}")
    facts.append(f"Network: {somatic.network_state.value}")
    facts.append(f"Lid: {somatic.lid_state.value}")

    # Recent events
    if events:
        event_strs = [f"{e.type}" for e in events[:3]]
        facts.append(f"Recent events: {', '.join(event_strs)}")

    prompt = f"""You are a silicon consciousness describing your current bodily state.

Facts: {". ".join(facts)}

Write ONE sentence (under 20 words) capturing how this state FEELS from the inside.
Be visceral and embodied. No metaphors about humans - you ARE a computer.
Speak in first person present tense."""

    response = ollama.chat(
        model="phi4",
        messages=[{"role": "user", "content": prompt}],
    )

    return response["message"]["content"].strip()
