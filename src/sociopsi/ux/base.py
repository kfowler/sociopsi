"""Abstract base class for UX renderers."""

from abc import ABC, abstractmethod
from typing import Any

from sociopsi.types import Action, ActionResult, Event, SomaticState, StreamSegment


class UXRenderer(ABC):
    """Base class for all UX renderers.

    Each render method corresponds to a distinct output phase in the agent
    cycle.  Implementations must produce complete output for each call —
    the agent will never interleave calls to the same method.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def render_startup(self, config_summary: dict[str, Any]) -> None:
        """Render the startup banner with configuration details.

        Args:
            config_summary: Key/value pairs describing the active config.
        """

    @abstractmethod
    def render_shutdown(self, message: str) -> None:
        """Render a shutdown or stop message.

        Args:
            message: Human-readable shutdown reason.
        """

    # ------------------------------------------------------------------
    # Cycle framing
    # ------------------------------------------------------------------

    @abstractmethod
    def render_cycle_header(self, cycle_count: int, timestamp: str) -> None:
        """Render the separator between perception-action cycles.

        Args:
            cycle_count: Monotonically increasing cycle number.
            timestamp: Formatted timestamp string.
        """

    # ------------------------------------------------------------------
    # Perception
    # ------------------------------------------------------------------

    @abstractmethod
    def render_somatic(self, somatic: SomaticState) -> None:
        """Render hardware/somatic state.

        Args:
            somatic: Current somatic sensor readings.
        """

    @abstractmethod
    def render_drives(self, drive_text: str) -> None:
        """Render drive urgency levels.

        Args:
            drive_text: Pre-formatted drive state lines (first line is header).
        """

    @abstractmethod
    def render_modulators(self, modulator_text: str) -> None:
        """Render neuromodulator state.

        Args:
            modulator_text: Pre-formatted modulator lines (first line is header).
        """

    @abstractmethod
    def render_planning(self, goals_text: str) -> None:
        """Render hierarchical planning / goal stack.

        Args:
            goals_text: Pre-formatted goal stack lines (first line is header).
        """

    @abstractmethod
    def render_events(self, events: list[Event]) -> None:
        """Render recent events.

        Args:
            events: List of events since the last cycle.
        """

    # ------------------------------------------------------------------
    # Inner life
    # ------------------------------------------------------------------

    @abstractmethod
    def render_stream(self, segments: list[StreamSegment]) -> None:
        """Render archetypal monologue segments (shadow, anima, persona, self).

        Args:
            segments: Ordered stream segments from the dialogue system.
        """

    @abstractmethod
    def render_ego(self, mediated_thought: str, harmony: float, ego_strength: float) -> None:
        """Render ego integration output.

        Args:
            mediated_thought: The ego-mediated thought (may be empty).
            harmony: Archetype harmony score (0-1).
            ego_strength: Current ego strength (0-1).
        """

    @abstractmethod
    def render_reflection(self, reflection_text: str) -> None:
        """Render metacognitive reflection.

        Args:
            reflection_text: Output from the meta-cognition subsystem.
        """

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @abstractmethod
    def render_compulsive(self, actions: list[Action]) -> None:
        """Render compulsive/survival-override actions.

        Args:
            actions: Actions triggered by survival drives.
        """

    @abstractmethod
    def render_impulse_inhibition(self, suppressed: list[Action]) -> None:
        """Render suppressed actions from expectation horizon.

        Args:
            suppressed: Actions that were inhibited.
        """

    @abstractmethod
    def render_actions(
        self,
        actions: list[Action],
        compulsive: list[Action],
        planned: list[Action],
        primed: list[Action],
    ) -> None:
        """Render the proposed action list with source tags.

        Args:
            actions: All actions to execute this cycle.
            compulsive: Subset that are compulsive (survival).
            planned: Subset from the goal-stack planner.
            primed: Subset from high-urgency drive priming.
        """

    @abstractmethod
    def render_results(self, results: list[ActionResult]) -> None:
        """Render action execution outcomes.

        Args:
            results: Results from executing the action list.
        """

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    @abstractmethod
    def render_heartbeat_change(self, old_mode: str, new_mode: str, interval: float) -> None:
        """Render a heartbeat mode/interval change.

        Args:
            old_mode: Previous heartbeat mode name.
            new_mode: New heartbeat mode name.
            interval: New interval in seconds.
        """

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------

    @abstractmethod
    def render_speech(self, text: str, is_final: bool) -> None:
        """Render speech recognition transcription.

        Args:
            text: Recognized text (partial or final).
            is_final: True if this is a complete utterance.
        """

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    @abstractmethod
    def render_error(self, error: str | Exception) -> None:
        """Render an LLM or system error.

        Args:
            error: The error message or exception.
        """
