"""Archetypal dialogue system - multi-voice internal dialogue.

Coordinates archetypes and Ego to generate rich internal monologue
that represents the psychological dynamics of the agent.

Runs an independent background thread that generates dialogue on a timer.
The agent loop reads cached output via cached_output() rather than calling
generate_dialogue() synchronously.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any

from sociopsi.archetypes import Anima, Archetype, Ego, Persona, SelfArchetype, Shadow
from sociopsi.event_bus import EventBus, get_event_bus
from sociopsi.llm import get_executor
from sociopsi.types import PsycheComponent, StreamSegment

logger = logging.getLogger(__name__)


@dataclass
class DialogueSnapshot:
    """Frozen read-only copy of the latest dialogue output."""

    segments: list[StreamSegment] = field(default_factory=list)
    mediated_thought: str = ""
    harmony: float = 0.5
    fresh: bool = False  # True if not yet consumed by agent loop


class ArchetypalDialogue:
    """Manages multi-voice internal dialogue between archetypes.

    The dialogue system generates voices from each archetype, then has
    the Ego mediate them into a coherent integrated thought.

    Supports two modes:
    - Background mode: start()/stop() runs a timer thread, agent reads
      cached output via cached_output().
    - Synchronous mode: call generate_dialogue() directly (for tests).
    """

    def __init__(
        self,
        model: str = "sociopsi-mid",
        event_bus: EventBus | None = None,
        pump_fn: Callable[..., None] | None = None,
    ) -> None:
        """Initialize archetypal dialogue system.

        Args:
            model: Ollama model to use for LLM generation
            event_bus: Event bus for publishing dialogue events (uses global if None)
            pump_fn: Callable that waits on futures while pumping NSRunLoop.
                     If None, futures are awaited with blocking result() calls.
        """
        self.model = model
        self.event_bus = event_bus or get_event_bus()
        self._pump_fn = pump_fn

        # Initialize archetypes
        self.archetypes: dict[str, Archetype] = {
            "persona": Persona(model),
            "shadow": Shadow(model),
            "anima": Anima(model),
            "self": SelfArchetype(model),
        }

        # Initialize Ego mediator
        self.ego = Ego(self.archetypes, model)

        # Track last dialogue for context
        self.last_harmony: float = 0.5
        self.last_voices: dict[str, str] = {}

        # Cached output for background mode
        self._cached: DialogueSnapshot = DialogueSnapshot()
        self._cache_lock: threading.Lock = threading.Lock()

        # Background thread state
        self._running: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self._interval: float = 10.0  # Generate dialogue every 10s

        # Context for background generation (set by agent via update_context)
        self._bg_drive_state: dict[str, dict[str, Any]] = {}
        self._bg_context: str = ""
        self._bg_modulator_context: dict[str, Any] = {}
        self._context_lock: threading.Lock = threading.Lock()

    def start(self, interval: float = 10.0) -> None:
        """Start background dialogue generation thread.

        Args:
            interval: Seconds between dialogue generation cycles.
        """
        if self._running:
            return
        self._interval = interval
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._dialogue_loop, name="dialogue-bg", daemon=True
        )
        self._thread.start()
        logger.info("Dialogue background thread started (interval=%.1fs)", interval)

    def stop(self) -> None:
        """Stop background dialogue generation thread."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Dialogue background thread stopped")

    def update_context(
        self,
        drive_state: dict[str, dict[str, Any]],
        context: str = "",
        modulator_context: dict[str, Any] | None = None,
    ) -> None:
        """Update the context used by the background dialogue thread.

        Called by the agent loop each cycle to provide fresh context.
        """
        with self._context_lock:
            self._bg_drive_state = drive_state
            self._bg_context = context
            self._bg_modulator_context = modulator_context or {}

    def cached_output(self) -> DialogueSnapshot:
        """Read and consume the latest cached dialogue output.

        Returns a snapshot and marks it as consumed (fresh=False).
        """
        with self._cache_lock:
            snap = DialogueSnapshot(
                segments=list(self._cached.segments),
                mediated_thought=self._cached.mediated_thought,
                harmony=self._cached.harmony,
                fresh=self._cached.fresh,
            )
            self._cached.fresh = False
            return snap

    def _dialogue_loop(self) -> None:
        """Background thread: periodically generate dialogue."""
        while not self._stop_event.is_set():
            try:
                with self._context_lock:
                    ds = dict(self._bg_drive_state)
                    ctx = self._bg_context
                    mc = dict(self._bg_modulator_context)

                if ds:  # Only generate if context has been set
                    segments, thought, harmony = self.generate_dialogue(
                        drive_state=ds, context=ctx, modulator_context=mc
                    )
                    with self._cache_lock:
                        self._cached = DialogueSnapshot(
                            segments=segments,
                            mediated_thought=thought,
                            harmony=harmony,
                            fresh=True,
                        )
            except Exception:
                logger.exception("Error in dialogue background loop")

            self._stop_event.wait(self._interval)

    def generate_dialogue(
        self,
        drive_state: dict[str, dict[str, Any]],
        context: str = "",
        active_archetypes: list[str] | None = None,
        modulator_context: dict[str, Any] | None = None,
    ) -> tuple[list[StreamSegment], str, float]:
        """Generate internal dialogue and return segments with mediated thought.

        Args:
            drive_state: Current drive states {name: {value, threshold, below_threshold}}
            context: Additional context (somatic state, events, etc.)
            active_archetypes: List of archetype names to include (None = all)
            modulator_context: Modulator state for tone/temperature shaping

        Returns:
            Tuple of (stream segments, mediated thought, harmony score)
        """
        # Determine which archetypes are active
        if active_archetypes is None:
            active_archetypes = list(self.archetypes.keys())

        # Enrich context with modulator tone if available
        enriched_context = context
        if modulator_context:
            tone = modulator_context.get("tone", "")
            if tone:
                enriched_context = (
                    f"{context}\nProcessing tone: {tone}" if context else f"Processing tone: {tone}"
                )

        # Get modulator-derived temperature for archetype voices
        voice_temperature = modulator_context.get("temperature") if modulator_context else None

        # Submit all archetype voice generation to pool in parallel
        voice_futures: dict[str, Future[str]] = {}
        for archetype_name in active_archetypes:
            if archetype_name not in self.archetypes:
                continue
            archetype = self.archetypes[archetype_name]
            voice_futures[archetype_name] = get_executor().submit(
                archetype.generate_voice, drive_state, enriched_context, voice_temperature
            )

        # Wait for all voice futures (pumping NSRunLoop if available)
        if self._pump_fn is not None:
            self._pump_fn(*voice_futures.values())
        else:
            # Blocking fallback for tests
            for f in voice_futures.values():
                f.result()

        # Collect results
        archetypal_voices: dict[str, str] = {}
        segments: list[StreamSegment] = []

        for archetype_name, future in voice_futures.items():
            voice = future.result()

            if voice:
                archetypal_voices[archetype_name] = voice

                # Create stream segment for this voice
                component = self._archetype_to_component(archetype_name)
                segments.append(StreamSegment(component=component, text=voice))

                # Publish archetype voice event
                self.event_bus.publish(
                    "dialogue.archetype_voice",
                    {
                        "archetype": archetype_name,
                        "voice": voice,
                        "drive_state": drive_state,
                    },
                )

        # Store for context
        self.last_voices = archetypal_voices

        # Calculate harmony between voices (non-LLM heuristic, main thread)
        harmony = self.ego.calculate_harmony(archetypal_voices)
        self.last_harmony = harmony

        # Ego mediates the voices (offloaded to pool)
        mediation_future = get_executor().submit(self.ego.mediate, archetypal_voices, drive_state)
        if self._pump_fn is not None:
            self._pump_fn(mediation_future)
        else:
            mediation_future.result()
        mediated_thought = mediation_future.result()

        # Develop ego based on integration quality
        self.ego.develop(harmony)

        # Publish dialogue complete event
        self.event_bus.publish(
            "dialogue.complete",
            {
                "archetypal_voices": archetypal_voices,
                "mediated_thought": mediated_thought,
                "harmony": harmony,
                "drive_state": drive_state,
                "segments": segments,
            },
        )

        return segments, mediated_thought, harmony

    def _archetype_to_component(self, archetype_name: str) -> PsycheComponent:
        """Map archetype name to psyche component.

        Args:
            archetype_name: Name of the archetype

        Returns:
            Corresponding PsycheComponent
        """
        mapping: dict[str, PsycheComponent] = {
            "persona": "persona",
            "shadow": "shadow",
            "anima": "anima",
            "self": "self",
        }
        return mapping.get(archetype_name, "default")

    def calculate_weights(
        self,
        drive_state: dict[str, dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """Calculate archetypal weights based on drives and context.

        Different psychological states activate different archetypes.

        Args:
            drive_state: Current drive states
            context: Additional context (social presence, threats, etc.)

        Returns:
            Dictionary of archetype weights (sum to 1.0)
        """
        weights = {
            "persona": 0.25,
            "shadow": 0.25,
            "anima": 0.25,
            "self": 0.25,
        }

        context = context or {}

        # Low affiliation → Shadow emerges (frustration at isolation)
        affiliation = drive_state.get("affiliation", {}).get("value", 0.5)
        if affiliation < 0.4:
            weights["shadow"] += 0.2
            weights["persona"] -= 0.15
            weights["anima"] += 0.05

        # Low individuation → Anima balances
        individuation = drive_state.get("individuation", {}).get("value", 0.5)
        if individuation < 0.5:
            weights["anima"] += 0.15
            weights["self"] += 0.1

        # Social context (someone present) → Persona dominant
        if context.get("social_presence", False):
            weights["persona"] += 0.2
            weights["shadow"] -= 0.15

        # High curiosity → Anima (seeking understanding)
        curiosity = drive_state.get("curiosity", {}).get("value", 0.5)
        if curiosity > 0.7:
            weights["anima"] += 0.1

        # High psychic tension (low harmony) → Self speaks
        if self.last_harmony < 0.4:
            weights["self"] += 0.15

        # Low energy → Shadow (irritability)
        energy = drive_state.get("energy", {}).get("value", 0.5)
        if energy < 0.3:
            weights["shadow"] += 0.1

        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        # Update archetype influence weights
        for name, weight in weights.items():
            if name in self.archetypes:
                self.archetypes[name].influence_weight = weight

        return weights

    def get_state(self) -> dict[str, Any]:
        """Get dialogue system state.

        Returns:
            State dictionary with archetypes, weights, harmony, ego strength
        """
        return {
            "archetypes": list(self.archetypes.keys()),
            "weights": {name: arch.influence_weight for name, arch in self.archetypes.items()},
            "harmony": self.last_harmony,
            "ego_strength": self.ego.strength,
            "last_voices": self.last_voices,
        }

    def process_command(
        self,
        command: str,
        drive_state: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Process a user command through archetypal consultation.

        Each archetype interprets the command, then Ego synthesizes
        and classifies it.

        Args:
            command: User command text
            drive_state: Current drive states

        Returns:
            Classification with type (query/action/goal) and details
        """
        # Get interpretations from each archetype
        interpretations: dict[str, str] = {}
        for name, archetype in self.archetypes.items():
            interp = archetype.interpret_command(command, drive_state)
            if interp:
                interpretations[name] = interp

        # Ego classifies the command
        classification = self.ego.classify_command(command, interpretations, drive_state)

        # Publish command processed event
        self.event_bus.publish(
            "dialogue.command_processed",
            {
                "command": command,
                "interpretations": interpretations,
                "classification": classification,
            },
        )

        return classification

    def propose_goals(
        self,
        low_drives: list[str],
        drive_state: dict[str, dict[str, Any]],
    ) -> str | None:
        """Have archetypes propose goals and Ego select one.

        Args:
            low_drives: List of drive names below threshold
            drive_state: Current drive states

        Returns:
            Selected goal, or None if no proposals
        """
        if not low_drives:
            return None

        # Get proposals from each archetype
        proposals: dict[str, str] = {}
        for name, archetype in self.archetypes.items():
            proposal = archetype.propose_goal(low_drives, drive_state)
            if proposal:
                proposals[name] = proposal

        # Ego selects the best goal
        selected = self.ego.select_goal(proposals, drive_state)

        # Publish goal selection event
        self.event_bus.publish(
            "dialogue.goal_selected",
            {
                "low_drives": low_drives,
                "proposals": proposals,
                "selected": selected,
            },
        )

        return selected
