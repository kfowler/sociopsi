"""Voice renderer — speech-only headless output via platform TTS."""

import logging
import threading
from typing import Any

from sociopsi.platform.base import AudioBackend
from sociopsi.types import (
    Action,
    ActionResult,
    Event,
    SomaticState,
    StreamSegment,
    ThermalState,
)
from sociopsi.ux.base import UXRenderer

logger = logging.getLogger(__name__)

# Component labels for spoken stream segments
_COMPONENT_LABEL: dict[str, str] = {
    "shadow": "Shadow",
    "anima": "Anima",
    "persona": "Persona",
    "self": "Self",
}


class VoiceRenderer(UXRenderer):
    """Renders agent state via TTS for headless ambient operation.

    Not every render call produces speech — filtering rules prevent
    overwhelming the listener.  Only critical, high-urgency, or
    substantive content is spoken aloud.

    Args:
        audio: Platform audio backend for TTS.
        voice: Voice name/identifier (None for system default).
        rate: Speech rate in words per minute.
    """

    def __init__(
        self,
        audio: AudioBackend,
        voice: str | None = None,
        rate: int = 200,
    ) -> None:
        self._audio = audio
        self._voice = voice
        self._rate = rate
        self._lock = threading.Lock()

    def _speak(self, text: str) -> None:
        """Speak text through the audio backend, serialising calls."""
        if not text or not text.strip():
            return
        with self._lock:
            try:
                self._audio.speak(text, voice=self._voice, rate=self._rate)
            except Exception:
                logger.exception("TTS speak failed")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def render_startup(self, config_summary: dict[str, Any]) -> None:
        self._speak("Starting up.")

    def render_shutdown(self, message: str) -> None:
        self._speak(message)

    # ------------------------------------------------------------------
    # Cycle framing — silent
    # ------------------------------------------------------------------

    def render_cycle_header(self, cycle_count: int, timestamp: str) -> None:
        pass  # Silent

    # ------------------------------------------------------------------
    # Perception
    # ------------------------------------------------------------------

    def render_somatic(self, somatic: SomaticState) -> None:
        # Only speak if critical
        if somatic.battery_percent < 15:
            self._speak(f"Warning: battery at {somatic.battery_percent} percent.")
        if somatic.thermal_state in (ThermalState.HOT, ThermalState.CRITICAL):
            self._speak(f"Warning: thermal state is {somatic.thermal_state.value}.")

    def render_drives(self, drive_text: str) -> None:
        # Parse lines for urgencies > 0.7
        urgent: list[str] = []
        for line in drive_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Drive lines look like: "curiosity    0.70 URGE  want to learn"
            parts = line.split()
            if len(parts) >= 2:
                try:
                    urgency = float(parts[1])
                    if urgency > 0.7:
                        drive_name = parts[0]
                        # Grab the description if present (after status word)
                        desc = " ".join(parts[3:]) if len(parts) > 3 else drive_name
                        urgent.append(desc if desc else drive_name)
                except ValueError, IndexError:
                    continue
        if urgent:
            self._speak("Feeling: " + ". ".join(urgent) + ".")

    def render_modulators(self, modulator_text: str) -> None:
        pass  # Silent — modulators are background state

    def render_planning(self, goals_text: str) -> None:
        pass  # Silent — planning is internal

    def render_events(self, events: list[Event]) -> None:
        pass  # Silent — events are context, not spoken

    # ------------------------------------------------------------------
    # Inner life
    # ------------------------------------------------------------------

    def render_stream(self, segments: list[StreamSegment]) -> None:
        # Speak full monologue with component labels
        for segment in segments:
            label = _COMPONENT_LABEL.get(segment.component, segment.component)
            self._speak(f"{label} says: {segment.text}")

    def render_ego(self, mediated_thought: str, harmony: float, ego_strength: float) -> None:
        # Speak mediated thought — this is the primary output
        if mediated_thought:
            self._speak(mediated_thought)

    def render_reflection(self, reflection_text: str) -> None:
        pass  # Silent — reflection is internal metacognition

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def render_compulsive(self, actions: list[Action]) -> None:
        if actions:
            names = ", ".join(a.type for a in actions)
            self._speak(f"Survival override: {names}.")

    def render_impulse_inhibition(self, suppressed: list[Action]) -> None:
        pass  # Silent — inhibition is internal

    def render_actions(
        self,
        actions: list[Action],
        compulsive: list[Action],
        planned: list[Action],
        primed: list[Action],
    ) -> None:
        if not actions:
            return
        # Summarise action list into a natural sentence
        names = [a.type.replace("_", " ") for a in actions]
        if len(names) == 1:
            summary = names[0]
        elif len(names) == 2:
            summary = f"{names[0]} and {names[1]}"
        else:
            summary = ", ".join(names[:-1]) + f", and {names[-1]}"
        self._speak(f"I will {summary}.")

    def render_results(self, results: list[ActionResult]) -> None:
        for result in results:
            if result.success and isinstance(result.result, dict):
                # Speak perception results (e.g., look, listen)
                # Skip routine successes with no interesting data
                interesting = {
                    k: v
                    for k, v in result.result.items()
                    if k != "full_data" and isinstance(v, str) and v.strip()
                }
                if interesting:
                    parts = ". ".join(str(v)[:200] for v in interesting.values())
                    self._speak(parts)
            elif not result.success and result.error:
                self._speak(f"Error in {result.action_type}: {result.error}")

    # ------------------------------------------------------------------
    # Heartbeat — silent
    # ------------------------------------------------------------------

    def render_heartbeat_change(self, old_mode: str, new_mode: str, interval: float) -> None:
        pass  # Silent

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------

    def render_speech(self, text: str, is_final: bool) -> None:
        if is_final:
            self._speak(f"I heard you say: {text}")

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    def render_error(self, error: str | Exception) -> None:
        self._speak(f"Error: {error}")
