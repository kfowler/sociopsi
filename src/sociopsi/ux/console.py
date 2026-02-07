"""Console renderer — colored terminal output matching the original agent output."""

import sys
from datetime import datetime
from typing import Any, Final

from sociopsi.terminal import colors
from sociopsi.types import (
    Action,
    ActionResult,
    Event,
    PsycheComponent,
    SomaticState,
    StreamSegment,
)
from sociopsi.ux.base import UXRenderer

# Emoji and color maps for stream segments (previously in JungAgent)
_COMPONENT_EMOJI: Final[dict[PsycheComponent, str]] = {
    "shadow": "\U0001f311",
    "anima": "\u2728",
    "persona": "\U0001f3ad",
    "self": "\u2600\ufe0f",
    "default": "\U0001f4ad",
}
_COMPONENT_COLOR: Final[dict[PsycheComponent, str]] = {
    "shadow": colors.RED,
    "anima": colors.CYAN,
    "persona": colors.YELLOW,
    "self": colors.MAGENTA,
    "default": colors.WHITE,
}


class ConsoleRenderer(UXRenderer):
    """Renders all agent output to the terminal with ANSI colors.

    Produces output identical to the original inline ``print()`` calls.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def render_startup(self, config_summary: dict[str, Any]) -> None:
        for _key, value in config_summary.items():
            if isinstance(value, list):
                for line in value:
                    print(line)
            else:
                print(value)
        print("-" * 60)

    def render_shutdown(self, message: str) -> None:
        print(message)

    # ------------------------------------------------------------------
    # Cycle framing
    # ------------------------------------------------------------------

    def render_cycle_header(self, cycle_count: int, timestamp: str) -> None:
        print(f"\n{'=' * 70}")
        print(f"{colors.BOLD}[CYCLE {cycle_count}] {timestamp}{colors.RESET}")
        print("=" * 70)

    # ------------------------------------------------------------------
    # Perception
    # ------------------------------------------------------------------

    def render_somatic(self, somatic: SomaticState) -> None:
        print(f"\n{colors.BLUE}[SOMATIC]{colors.RESET} {somatic.to_tag()}")
        print(f"  Battery: {somatic.battery_percent}% ({somatic.power_state.value})")
        print(f"  CPU: {somatic.cpu_percent:.1f}% | RAM: {somatic.ram_percent:.1f}%")
        print(f"  Thermal: {somatic.thermal_state.value} | Fan: {somatic.fan_rpm} RPM")
        print(f"  Network: {somatic.network_state.value} | Lid: {somatic.lid_state.value}")

    def render_drives(self, drive_text: str) -> None:
        print(f"\n{colors.MAGENTA}[DRIVES]{colors.RESET}")
        for line in drive_text.split("\n")[1:]:
            if line.strip():
                print(f"  {line}")

    def render_modulators(self, modulator_text: str) -> None:
        print(f"\n{colors.MAGENTA}[MODULATORS]{colors.RESET}")
        for line in modulator_text.split("\n")[1:]:
            if line.strip():
                print(f"  {line}")

    def render_planning(self, goals_text: str) -> None:
        print(f"\n{colors.GREEN}[PLANNING]{colors.RESET}")
        for line in goals_text.split("\n")[1:]:
            if line.strip():
                print(f"  {line}")

    def render_events(self, events: list[Event]) -> None:
        print(f"\n{colors.CYAN}[EVENTS]{colors.RESET}")
        for event in events:
            ts = event.timestamp.strftime("%H:%M:%S")
            print(f"  [{ts}] {event.type}: {event.description}")

    # ------------------------------------------------------------------
    # Inner life
    # ------------------------------------------------------------------

    def render_stream(self, segments: list[StreamSegment]) -> None:
        print()  # Blank line before stream
        for segment in segments:
            timestamp = datetime.now().strftime("%H:%M:%S")
            color = _COMPONENT_COLOR.get(segment.component, colors.WHITE)
            emoji = _COMPONENT_EMOJI.get(segment.component, "\U0001f4ad")
            label = segment.component.upper()
            print(f"[{timestamp}] {color}{emoji} {label}{colors.RESET}: {segment.text}")
        print()  # Blank line after stream

    def render_ego(self, mediated_thought: str, harmony: float, ego_strength: float) -> None:
        print(f"\n{colors.DIM}[HARMONY] {harmony:.2f} | Ego: {ego_strength:.2f}{colors.RESET}")

    def render_reflection(self, reflection_text: str) -> None:
        print(f"\n{colors.DIM}[META] {reflection_text}{colors.RESET}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def render_compulsive(self, actions: list[Action]) -> None:
        print(f"\n{colors.RED}[COMPULSIVE - SURVIVAL]{colors.RESET}")
        for action in actions:
            print(f"  ! {action.type} (drive override)")

    def render_impulse_inhibition(self, suppressed: list[Action]) -> None:
        print(f"\n{colors.RED}[IMPULSE INHIBITION]{colors.RESET}")
        for action in suppressed:
            print(f"  \u2717 {action.type} (predicted net-negative)")

    def render_actions(
        self,
        actions: list[Action],
        compulsive: list[Action],
        planned: list[Action],
        primed: list[Action],
    ) -> None:
        if actions:
            print(f"\n{colors.YELLOW}[ACTIONS]{colors.RESET}")
            for i, action in enumerate(actions, 1):
                if action in compulsive:
                    source = f" {colors.RED}(compulsive){colors.RESET}"
                elif action in planned:
                    source = f" {colors.GREEN}(planned){colors.RESET}"
                elif action in primed:
                    source = f" {colors.MAGENTA}(primed){colors.RESET}"
                else:
                    source = ""
                params_str = ", ".join(f"{k}={v!r}" for k, v in action.params.items())
                if params_str:
                    print(f"  {i}. {action.type}({params_str}){source}")
                else:
                    print(f"  {i}. {action.type}(){source}")
        else:
            print(f"\n{colors.YELLOW}[ACTIONS]{colors.RESET} (none)")

    def render_results(self, results: list[ActionResult]) -> None:
        print(f"\n{colors.GREEN}[RESULTS]{colors.RESET}")
        for result in results:
            status_color = colors.GREEN if result.success else colors.RED
            status = "\u2713" if result.success else "\u2717"
            print(f"  {status_color}{status} {result.action_type}{colors.RESET}")
            if result.success and isinstance(result.result, dict):
                for key, value in result.result.items():
                    if key != "full_data":
                        if isinstance(value, str) and len(value) > 100:
                            value = value[:100] + "..."
                        print(f"      {colors.DIM}{key}: {value}{colors.RESET}")
            elif not result.success and result.error:
                print(f"      {colors.DIM}Error: {result.error}{colors.RESET}")

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def render_heartbeat_change(self, old_mode: str, new_mode: str, interval: float) -> None:
        if new_mode == "override":
            print(f"  [HEARTBEAT] Set to {interval}s by psyche")
        else:
            print(f"  [HEARTBEAT] {old_mode} -> {new_mode} ({interval}s)")

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------

    def render_speech(self, text: str, is_final: bool) -> None:
        if is_final:
            sys.stdout.write(f'\r\033[K{colors.GREEN}[SPEECH]{colors.RESET} "{text}"\n')
            sys.stdout.flush()
        else:
            sys.stdout.write(
                f"\r\033[K{colors.DIM}[HEARING]{colors.RESET} {colors.DIM}{text}{colors.RESET}"
            )
            sys.stdout.flush()

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    def render_error(self, error: str | Exception) -> None:
        print(f"{colors.RED}[LLM ERROR]{colors.RESET} {error}")
