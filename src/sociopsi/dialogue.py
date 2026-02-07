"""Archetypal dialogue system - multi-voice internal dialogue.

Coordinates archetypes and Ego to generate rich internal monologue
that represents the psychological dynamics of the agent.
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from sociopsi.archetypes import Anima, Archetype, Ego, Persona, SelfArchetype, Shadow
from sociopsi.event_bus import EventBus, get_event_bus
from sociopsi.llm import get_executor
from sociopsi.types import PsycheComponent, StreamSegment

logger = logging.getLogger(__name__)


class ArchetypalDialogue:
    """Manages multi-voice internal dialogue between archetypes.

    The dialogue system generates voices from each archetype, then has
    the Ego mediate them into a coherent integrated thought.
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


@dataclass
class DialogueResult:
    """Cached result from event-driven dialogue generation."""

    segments: list[StreamSegment]
    mediated_thought: str
    harmony: float
    timestamp: float
    trigger: str


class DialogueManager:
    """Event-driven dialogue manager with cached output.

    Runs dialogue generation in a dedicated thread, triggered by events
    on the bus. The agent reads cached results without blocking.

    Triggers:
        - Drive urgency crosses 0.7
        - External stimulus (speech, person detected)
        - Somatic alarm (thermal/battery critical)
        - Timer fallback (every 30s if no trigger)
    """

    STALE_THRESHOLD: float = 60.0
    FALLBACK_INTERVAL: float = 30.0
    HARMONY_WINDOW: int = 10

    def __init__(
        self,
        model: str = "sociopsi-mid",
        event_bus: EventBus | None = None,
    ) -> None:
        self._event_bus = event_bus or get_event_bus()
        self._dialogue = ArchetypalDialogue(
            model=model,
            event_bus=self._event_bus,
            pump_fn=None,  # Background thread uses blocking waits
        )

        # Thread-safe cached result
        self._cached: DialogueResult | None = None
        self._lock = threading.Lock()

        # Trigger mechanism
        self._trigger_event = threading.Event()
        self._pending_trigger: str = "init"

        # Latest state for generation (updated by agent each cycle)
        self._drive_state: dict[str, dict[str, Any]] | None = None
        self._context: str = ""
        self._modulator_context: dict[str, Any] | None = None

        # Rolling harmony
        self._harmony_history: list[float] = []

        # Thread
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def dialogue(self) -> ArchetypalDialogue:
        """Access underlying dialogue system for ego/weights."""
        return self._dialogue

    def start(self) -> None:
        """Start the dialogue manager thread and subscribe to triggers."""
        if self._running:
            return
        self._event_bus.subscribe("dialogue.trigger", self._on_trigger)
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="dialogue-manager",
        )
        self._thread.start()
        logger.info("DialogueManager started")

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the dialogue manager thread."""
        if not self._running:
            return
        self._running = False
        self._trigger_event.set()
        self._event_bus.unsubscribe("dialogue.trigger", self._on_trigger)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("DialogueManager stopped")

    def update_state(
        self,
        drive_state: dict[str, dict[str, Any]],
        context: str,
        modulator_context: dict[str, Any] | None = None,
    ) -> None:
        """Update state for next dialogue generation.

        Called by the agent each cycle to provide fresh state.
        """
        with self._lock:
            self._drive_state = drive_state
            self._context = context
            self._modulator_context = modulator_context

    def get_cached(self) -> DialogueResult | None:
        """Get the latest cached dialogue result (thread-safe, non-blocking)."""
        with self._lock:
            return self._cached

    def is_stale(self) -> bool:
        """Check if cached dialogue is too old to use."""
        with self._lock:
            if self._cached is None:
                return True
            return (time.time() - self._cached.timestamp) > self.STALE_THRESHOLD

    def get_rolling_harmony(self) -> float:
        """Get rolling average harmony score."""
        with self._lock:
            return self._rolling_harmony_unlocked()

    def get_state(self) -> dict[str, Any]:
        """Get dialogue manager state for logging/inspection."""
        with self._lock:
            cached_age = time.time() - self._cached.timestamp if self._cached else None
            cached_trigger = self._cached.trigger if self._cached else None
            rolling = self._rolling_harmony_unlocked()
            stale = (
                self._cached is None
                or (time.time() - self._cached.timestamp) > self.STALE_THRESHOLD
            )
        dialogue_state = self._dialogue.get_state()
        return {
            "cached_age": cached_age,
            "cached_trigger": cached_trigger,
            "rolling_harmony": rolling,
            "stale": stale,
            **dialogue_state,
        }

    def _rolling_harmony_unlocked(self) -> float:
        """Compute rolling harmony (caller must hold self._lock)."""
        if not self._harmony_history:
            return 0.5
        return sum(self._harmony_history) / len(self._harmony_history)

    def _on_trigger(self, data: dict[str, Any]) -> None:
        """Event bus callback for dialogue triggers."""
        with self._lock:
            self._pending_trigger = data.get("reason", "event")
        self._trigger_event.set()

    def _run(self) -> None:
        """Background thread: wait for triggers, generate dialogue."""
        while self._running:
            triggered = self._trigger_event.wait(timeout=self.FALLBACK_INTERVAL)
            if not self._running:
                break
            self._trigger_event.clear()

            with self._lock:
                trigger = self._pending_trigger if triggered else "timer_fallback"
                drive_state = self._drive_state
                context = self._context
                modulator_context = self._modulator_context

            if drive_state is None:
                continue

            try:
                segments, thought, harmony = self._dialogue.generate_dialogue(
                    drive_state=drive_state,
                    context=context,
                    modulator_context=modulator_context,
                )

                result = DialogueResult(
                    segments=segments,
                    mediated_thought=thought,
                    harmony=harmony,
                    timestamp=time.time(),
                    trigger=trigger,
                )

                with self._lock:
                    self._cached = result
                    self._harmony_history.append(harmony)
                    if len(self._harmony_history) > self.HARMONY_WINDOW:
                        self._harmony_history = self._harmony_history[-self.HARMONY_WINDOW :]

                logger.debug(
                    "Dialogue generated (trigger=%s, harmony=%.2f)",
                    trigger,
                    harmony,
                )

            except Exception:
                logger.exception("Dialogue generation failed")
