"""The main agent loop — thin coordinator over layered subsystems.

All heavy processing (LLM dialogue, metacognition, drive updates, sensor
polling) runs independently in background threads. The agent loop reads
snapshots and cached output, builds an action list, executes, and logs.
Target cycle time: <500ms (no LLM calls in the main loop).
"""

import random
import signal
import sys
import threading
import time
from concurrent.futures import Future
from datetime import datetime
from types import FrameType
from typing import Any, Literal

from Foundation import NSDate, NSDefaultRunLoopMode, NSOrderedAscending, NSRunLoop

from sociopsi.actions.executor import ActionExecutor
from sociopsi.config import AgentConfig, load_system_prompt
from sociopsi.dialogue import DialogueManager
from sociopsi.drives import DriveSystem
from sociopsi.ear import Ear
from sociopsi.emotions import EmotionSystem
from sociopsi.event_bus import get_event_bus
from sociopsi.expectations import ExpectationHorizon
from sociopsi.llm import (
    LLMError,
    chat_with_retry,
    shutdown_executor,
    submit_chat,
)
from sociopsi.llm import (
    configure as configure_llm,
)
from sociopsi.logger import PsycheLogger
from sociopsi.memory import SemanticMemory
from sociopsi.metacognition import MetaCognition, MetacognitionManager
from sociopsi.nodenet import NodeNet
from sociopsi.parser import parse_response
from sociopsi.perception import format_perception
from sociopsi.planning import (
    DRIVE_ACTION_VOCABULARY,
    GoalStack,
    build_plan_prompt,
    parse_plan_response,
)
from sociopsi.sensors.events import EventCollector
from sociopsi.sensors.somatic import SomaticPoller, gather_somatic
from sociopsi.terminal import colors
from sociopsi.types import Action, ActionResult, SomaticState
from sociopsi.ux import ConsoleRenderer, UXRenderer
from sociopsi.voice import Voice

# Heartbeat mode type
HeartbeatMode = Literal["idle", "active", "stressed", "critical", "dormant", "override"]


class JungAgent:
    """The Jungian psyche agent — thin coordinator over layered subsystems.

    Background threads handle:
    - SomaticPoller: tiered sensor polling (1s/10s/30s)
    - DriveSystem: continuous 100ms drive economy
    - ArchetypalDialogue: periodic LLM dialogue generation
    - MetaCognition: periodic LLM reflection
    - EventBus: async event dispatch

    The agent loop reads snapshots, builds actions, executes, and logs.
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        renderer: UXRenderer | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.renderer: UXRenderer = renderer or ConsoleRenderer()

        # Configure LLM (sets Anthropic model name for when provider="anthropic" is used)
        configure_llm(self.config.llm_anthropic_model, self.config.llm_log_prompts)

        # Initialize event bus with async dispatch configuration
        self.event_bus = get_event_bus()
        # Survival/compulsive events skip queue — dispatch immediately inline
        self.event_bus.set_priority("survival.battery_critical", "survival.thermal_critical")
        # Somatic updates coalesce — only latest value dispatched
        self.event_bus.set_coalesce("somatic.update")

        # Core subsystems
        self.executor = ActionExecutor(self.config)
        self.event_collector = EventCollector()
        self.somatic_poller = SomaticPoller(
            event_callback=lambda t, d, data: self.event_collector.add_event(t, d, **data),
        )
        self.voice = Voice(self.config)
        self.ear = Ear(self.config, renderer=self.renderer)
        self.logger = PsycheLogger(self.config)
        self.drive_system = DriveSystem(self.config, event_bus=self.event_bus)

        # Emergent emotion system (computed from modulators + drives)
        self.emotions = EmotionSystem()

        # Event-driven dialogue manager (LLM-powered internal voices)
        self.dialogue_manager = DialogueManager(
            model=self.config.model,
            event_bus=self.event_bus,
        )
        self.dialogue = self.dialogue_manager.dialogue  # Alias for ego/weights access

        # Semantic memory with vector embeddings
        self.memory = SemanticMemory(max_memories=100)

        # Give creative actions access to semantic memory (for meditation)
        from sociopsi.actions.creative import set_semantic_memory

        set_semantic_memory(self.memory)

        # Spreading activation node net for implicit associations
        self.nodenet = NodeNet()

        # Expectation horizon for anticipatory processing
        self.expectations = ExpectationHorizon()

        # Meta-cognition for self-reflection (background thread)
        self.metacognition = MetaCognition(
            model=self.config.model,
            event_bus=self.event_bus,
        )

        # Independent metacognition timer (Layer 3 — runs in its own thread)
        self.metacognition_manager = MetacognitionManager(
            metacognition=self.metacognition,
            drive_state_fn=self._get_drive_state_dict,
            arousal_fn=lambda: self.drive_system.modulators.arousal_level,
            event_bus=self.event_bus,
        )

        # Hierarchical planning (ReCoN-inspired goal stack)
        self.goal_stack = GoalStack()

        # State
        self._running: bool = False
        self._shutdown_event: threading.Event = threading.Event()
        self._last_action_results: list[ActionResult] = []
        self._current_interval: float = self.config.heartbeat_idle
        self._heartbeat_mode: HeartbeatMode = "idle"
        self._last_update_time: float = time.time()

        # Dialogue tracking
        self._last_consumed_dialogue_time: float = 0.0
        self._prev_drive_urgency: dict[str, float] = {}

        # Reflection is now handled by MetacognitionManager (independent timer)

        # Cycle counter
        self._cycle_count: int = 0

    def _build_startup_summary(self) -> dict[str, Any]:
        """Build a config summary dict for the renderer."""
        lines: dict[str, Any] = {}
        lines["model"] = f"Ollama model: {self.config.model}"
        if self.config.llm_provider == "anthropic":
            lines["llm"] = f"Psyche LLM: Anthropic ({self.config.llm_anthropic_model})"
        else:
            lines["llm"] = f"Psyche LLM: Ollama ({self.config.model})"
        lines["modules"] = f"Modules enabled: {', '.join(self.config.modules)}"
        if self.config.voice_enabled:
            lines["voice"] = [
                f"Voices @ {self.config.voice_rate} wpm:",
                f"  Anima: {self.config.voice_anima}",
                f"  Shadow: {self.config.voice_shadow}",
                f"  Persona: {self.config.voice_persona}",
                f"  Self: {self.config.voice_self}",
                f"  Actions: {self.config.voice_actions} @ {self.config.voice_actions_rate} wpm",
            ]
        else:
            lines["voice"] = "Voice: disabled"
        if self.ear.enabled and self.ear._running:
            lines["ear"] = (
                f"Ear: listening ({self.config.ear_locale}, on_device={self.config.ear_on_device})"
            )
        elif self.config.ear_enabled:
            lines["ear"] = (
                f"{colors.RED}Ear: failed to start "
                f"(check Siri & Dictation in System Settings){colors.RESET}"
            )
        else:
            lines["ear"] = "Ear: disabled"
        lines["heartbeat"] = f"Initial heartbeat: {self._current_interval}s"
        lines["logging"] = f"Logging to: {self.logger.get_session_log()}"
        return lines

    def start(self) -> None:
        """Start the agent and all subsystems."""
        self._running = True
        self.event_bus.start()
        self.dialogue_manager.start()
        self.event_collector.start()
        self.somatic_poller.start()
        self.drive_system.start()

        # Wire voice speaking state to ear mute/unmute to prevent hearing own speech
        self.voice._on_speak_start = self.ear.mute
        self.voice._on_speak_end = self.ear.unmute
        self.voice.start()
        self.ear.start()
        self.metacognition_manager.start()

        # Start background LLM subsystems
        self.dialogue.start(interval=10.0)
        self.metacognition.start(interval=30.0)

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.renderer.render_startup(self._build_startup_summary())

        try:
            self._run_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the agent and all subsystems."""
        self._running = False
        self._shutdown_event.set()
        self.metacognition_manager.stop()
        self.drive_system.stop()
        self.ear.stop()
        self.somatic_poller.stop()
        self.event_collector.stop()
        self.voice.stop()
        self.dialogue_manager.stop()
        self.event_bus.stop()
        shutdown_executor(wait=False)
        self.renderer.render_shutdown("\nSocio-Psi stopped.")

    def _handle_shutdown(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        self.renderer.render_shutdown("\nShutdown signal received...")
        self.stop()
        sys.exit(0)

    def _run_loop(self) -> None:
        """Main agent loop driven by NSRunLoop.

        Uses NSRunLoop as the main driver, which allows voice delegate
        callbacks to fire naturally without manual pumping.
        """
        run_loop = NSRunLoop.currentRunLoop()
        cycle_count = 0

        while self._running:
            cycle_start = time.time()
            cycle_count += 1

            # Run one cycle
            self._run_cycle(cycle_count)

            # Calculate wait time until next cycle
            elapsed = time.time() - cycle_start
            wait_time = max(0.1, self._current_interval - elapsed)

            # Wait until deadline while servicing the run loop
            # This allows voice callbacks to fire naturally
            deadline = NSDate.dateWithTimeIntervalSinceNow_(wait_time)
            while self._running and NSDate.date().compare_(deadline) == NSOrderedAscending:
                # Run loop returns when: input processed, deadline reached, or no sources
                run_loop.runMode_beforeDate_(NSDefaultRunLoopMode, deadline)

    def _pump_until_done(self, *futures: Future[Any], timeout: float = 120.0) -> None:
        """Wait for futures to complete while pumping NSRunLoop.

        Polls futures in a loop, running NSRunLoop in 50ms intervals so
        that voice synthesis delegates and speech recognition callbacks
        can fire while LLM calls execute on worker threads.

        Args:
            *futures: Futures to wait on.
            timeout: Maximum seconds to wait before raising TimeoutError.

        Raises:
            TimeoutError: If futures don't complete within timeout.
        """
        run_loop = NSRunLoop.currentRunLoop()
        deadline = time.time() + timeout

        while not all(f.done() for f in futures):
            if time.time() > deadline:
                for f in futures:
                    f.cancel()
                raise TimeoutError(f"LLM futures did not complete within {timeout}s")
            run_loop.runMode_beforeDate_(
                NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.05)
            )

    def _run_cycle(self, cycle_count: int) -> None:
        """Run one perception-action cycle.

        Thin coordinator — reads snapshots from independent subsystems,
        builds an action list, executes, and logs. No LLM calls here.
        Target: <500ms per cycle.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.renderer.render_cycle_header(cycle_count, timestamp)

            # ── 1. Read somatic snapshot (non-blocking, from tiered sensors) ──
            somatic = self.somatic_poller.snapshot()

            # Collect events and speech
            events = self.event_collector.collect_events(somatic)
            utterances = self.ear.get_utterances()
            if utterances:
                for utterance in utterances:
                    self.memory.add_memory(
                        content=f"Human said: {utterance}",
                        intensity=0.7,
                        memory_type="interaction",
                    )
                # Spike social drives so a response is very likely
                for drive_name in ("affiliation", "recognition", "curiosity"):
                    if drive_name in self.drive_system.drives:
                        drive = self.drive_system.drives[drive_name]
                        drive.demand = min(1.0, drive.demand + 0.6)
                        drive.urgency = max(drive.urgency, 0.9)

            # ── 2. Read drive snapshot (non-blocking, from continuous drives) ──
            now = time.time()
            dt = now - self._last_update_time
            self._last_update_time = now
            had_actions = len(self._last_action_results) > 0
            self.drive_system.push_somatic(somatic, had_actions)

            drive_state = self._get_drive_state_dict()
            modulators = self.drive_system.modulators

            # Update lightweight subsystems (fast, no LLM)
            self.goal_stack.update_from_drives(drive_state)
            self.goal_stack.check_goal_satisfaction(drive_state)
            self.emotions.update(modulators, self.drive_system)
            self.memory.update(dt)

            # Feed concepts into node net and run spreading activation
            if events:
                self.nodenet.activate_concepts([e.type for e in events], amount=0.3)
            if utterances:
                for utterance in utterances:
                    words = [w for w in utterance.lower().split() if len(w) > 3]
                    if words:
                        self.nodenet.activate_concepts(words, amount=0.4)
            self.nodenet.update()

            # ── 3. Check compulsive actions (survival override, ~1ms) ──
            compulsive = self.drive_system.get_compulsive_actions(somatic)
            if compulsive:
                self.renderer.render_compulsive(compulsive)

            # ── 4. Read cached dialogue (non-blocking, from background thread) ──
            # Push fresh context for the next background dialogue generation
            dialogue_context = self._build_dialogue_context(somatic, events, utterances)
            modulator_context = modulators.get_dialogue_context()
            modulator_context.update(self.emotions.get_dialogue_context())
            self.dialogue.update_context(drive_state, dialogue_context, modulator_context)

            # Read whatever the background thread last produced
            dialogue_snap = self.dialogue.cached_output()
            segments = dialogue_snap.segments
            mediated_thought = dialogue_snap.mediated_thought
            harmony = dialogue_snap.harmony

            # Integrate dialogue output into other subsystems
            if dialogue_snap.fresh:
                # Update individuation from harmony
                if "individuation" in self.drive_system.drives and harmony > 0.7:
                    self.drive_system.drives["individuation"].satisfy(0.05 * harmony)

                # Feed dialogue concepts into node net
                if mediated_thought:
                    thought_words = [w for w in mediated_thought.lower().split() if len(w) > 3]
                    if thought_words:
                        self.nodenet.activate_concepts(thought_words[:8], amount=0.3)

                # Store mediated thought in memory (gated by securing rate modulator)
                if mediated_thought:
                    write_prob = modulators.get_memory_write_probability()
                    if random.random() < write_prob:
                        self.memory.add_memory(
                            content=mediated_thought,
                            intensity=min(1.0, 0.3 + harmony * 0.5),
                            emotional_valence=self.emotions.get_valence(),
                            memory_type="thought",
                        )

            # ── 5. Read cached reflection (non-blocking, from background thread) ──
            self.metacognition.update_context(drive_state)
            reflection = self.metacognition.cached_reflection()
            if reflection:
                self.renderer.render_reflection(reflection)

            # ── 6. Render state ──
            self.renderer.render_somatic(somatic)
            self.renderer.render_drives(self.drive_system.format_for_perception())
            self.renderer.render_modulators(modulators.format_for_perception())

            emotion_text = self.emotions.format_for_perception()
            if emotion_text:
                print(f"\n{colors.MAGENTA}[EMOTIONS]{colors.RESET}")
                for line in emotion_text.split("\n")[1:]:
                    if line.strip():
                        print(f"  {line}")

            goals_text = self.goal_stack.format_for_perception()
            if goals_text:
                self.renderer.render_planning(goals_text)

            if events:
                self.renderer.render_events(events)

            # 8. Update memory system
            self.memory.update(dt)

            # 8b. Feed concepts into node net from events and speech
            if events:
                event_concepts = [e.type for e in events]
                self.nodenet.activate_concepts(event_concepts, amount=0.3)
            if utterances:
                for utterance in utterances:
                    words = [w for w in utterance.lower().split() if len(w) > 3]
                    if words:
                        self.nodenet.activate_concepts(words, amount=0.4)

            # 8c. Run node net spreading activation cycle
            self.nodenet.update()

            # 9. Update dialogue manager state (non-blocking)
            context = self._build_dialogue_context(somatic, events, utterances)
            modulator_context = modulators.get_dialogue_context()
            # Enrich modulator context with emotional state
            modulator_context.update(self.emotions.get_dialogue_context())
            self.dialogue_manager.update_state(drive_state, context, modulator_context)

            # 9b. Publish dialogue triggers
            self._publish_dialogue_triggers(utterances, somatic)

            # 10. Read cached dialogue (non-blocking — never waits for generation)
            cached_dialogue = self.dialogue_manager.get_cached()
            is_new_dialogue = False

            if cached_dialogue is not None and not self.dialogue_manager.is_stale():
                segments = cached_dialogue.segments
                mediated_thought = cached_dialogue.mediated_thought
                harmony = cached_dialogue.harmony
                if cached_dialogue.timestamp > self._last_consumed_dialogue_time:
                    is_new_dialogue = True
                    self._last_consumed_dialogue_time = cached_dialogue.timestamp
            else:
                # Stale or no dialogue — use drive state directly
                segments = []
                mediated_thought = ""
                harmony = self.dialogue_manager.get_rolling_harmony()

            # Update individuation based on rolling harmony
            rolling_harmony = self.dialogue_manager.get_rolling_harmony()
            if "individuation" in self.drive_system.drives:
                if rolling_harmony > 0.7:
                    self.drive_system.drives["individuation"].satisfy(
                        0.05 * rolling_harmony
                    )

            # Feed dialogue concepts into node net (only for new dialogue)
            if is_new_dialogue and mediated_thought:
                thought_words = [w for w in mediated_thought.lower().split() if len(w) > 3]
                if thought_words:
                    self.nodenet.activate_concepts(thought_words[:8], amount=0.3)

            # Store mediated thought in memory (only for new dialogue)
            if is_new_dialogue and mediated_thought:
                write_prob = modulators.get_memory_write_probability()
                if random.random() < write_prob:
                    self.memory.add_memory(
                        content=mediated_thought,
                        intensity=min(1.0, 0.3 + harmony * 0.5),
                        emotional_valence=self.emotions.get_valence(),
                        memory_type="thought",
                    )

            # 11. Read latest reflection from independent timer (never waits)
            reflection = self.metacognition_manager.get_latest_reflection()
            if reflection:
                self.renderer.render_reflection(reflection)

            # 12. Log and speak stream
            if self.config.log_stream:
                self.renderer.render_stream(segments)

            self.renderer.render_ego(mediated_thought, harmony, self.dialogue.ego.strength)

            primed_nodes = self.nodenet.get_primed(3)
            if primed_nodes:
                primed_str = ", ".join(f"{c}({a:.2f})" for c, a in primed_nodes)
                print(f"{colors.DIM}[PRIMING] {primed_str}{colors.RESET}")

            # ── 7. Build action list from dialogue + compulsive + primed ──
            final_actions: list[Action] = []

            # Compulsive actions first (survival override)
            if compulsive:
                final_actions.extend(compulsive)

            # Planned actions from goal stack
            planned: list[Action] = []
            active_plan = self.goal_stack.active_plan
            if active_plan:
                planned = self.goal_stack.get_next_actions()
                final_actions.extend(planned)

            # Primed actions for high-urgency drives
            primed = self.drive_system.get_primed_actions()
            planned_types = {a.type for a in planned}
            for action in primed:
                if action.type not in planned_types:
                    final_actions.append(action)

            # Auto-inject speak when new dialogue produced a mediated thought
            if is_new_dialogue and mediated_thought and not any(
                a.type == "speak" for a in final_actions
            ):
                final_actions.append(Action(type="speak", params={"text": mediated_thought}))

            # ── 8. Expectation horizon: evaluate and execute ──
            horizon_result = self.expectations.evaluate(final_actions, self.drive_system)
            if horizon_result.suppressed:
                self.renderer.render_impulse_inhibition(horizon_result.suppressed)
                final_actions = horizon_result.approved

            drives_before = self.expectations.snapshot_drives(self.drive_system)

            self.renderer.render_actions(final_actions, compulsive, planned, primed)
            self._last_action_results = self.executor.execute_all(final_actions)

            # ── 9. Push satisfaction signals to drive queue ──
            self.drive_system.queue_satisfaction(self._last_action_results)

            # Counterfactual learning
            drives_after = self.expectations.snapshot_drives(self.drive_system)
            self.expectations.learn_from_outcome(
                horizon_result.expectations, drives_before, drives_after
            )

            # Record results back to planning system
            if active_plan and planned and self._last_action_results:
                for result in self._last_action_results:
                    if result.action_type == planned[0].type:
                        self.goal_stack.record_result(active_plan, result)
                        break

            if self._last_action_results:
                self.renderer.render_results(self._last_action_results)

            # ── 10. Log cycle state ──
            self.logger.log_cycle(
                perception=dialogue_context,
                somatic=somatic,
                stream=segments,
                actions=[a.type for a in final_actions],
                action_results=self._last_action_results,
                heartbeat_interval=self._current_interval,
                heartbeat_mode=self._heartbeat_mode,
                drives=self.drive_system.get_state(),
                modulators=dict(modulators.get_state()),
                emotions=self.emotions.get_state(),
            )

            # Reactive heartbeat
            override = self.executor.get_heartbeat_override()
            if override is not None:
                old_mode = self._heartbeat_mode
                self._current_interval = override
                self._heartbeat_mode = "override"
                self.renderer.render_heartbeat_change(old_mode, "override", override)
            else:
                self._update_heartbeat(somatic, drive_state)

        except Exception as e:
            self.renderer.render_error(f"Error in cycle: {e}")
            import traceback

            traceback.print_exc()

    def _update_heartbeat(
        self, somatic: SomaticState, drive_state: dict[str, dict[str, Any]]
    ) -> None:
        """Update heartbeat interval reactively from somatic + drive urgency.

        Priority order: critical > stressed > drive-urgent > active > dormant > idle.
        Drive urgency makes the heartbeat responsive to psychological state,
        not just hardware state.
        """
        old_interval = self._current_interval
        old_mode = self._heartbeat_mode

        # Critical: battery emergency
        if somatic.battery_percent < self.config.battery_critical:
            self._current_interval = self.config.heartbeat_critical
            self._heartbeat_mode = "critical"
        # Stressed: thermal or CPU overload
        elif (
            somatic.thermal_state.value in ("hot", "critical")
            or somatic.cpu_percent > self.config.cpu_stressed
        ):
            self._current_interval = self.config.heartbeat_stressed
            self._heartbeat_mode = "stressed"
        # Drive-urgent: any drive above urgency threshold → fast heartbeat
        elif self._max_drive_urgency(drive_state) > 0.7:
            self._current_interval = self.config.heartbeat_active
            self._heartbeat_mode = "active"
        # Active: moderate CPU
        elif somatic.cpu_percent > self.config.cpu_active:
            self._current_interval = self.config.heartbeat_active
            self._heartbeat_mode = "active"
        # Dormant: lid closed
        elif somatic.lid_state.value == "closed":
            self._current_interval = self.config.heartbeat_dormant
            self._heartbeat_mode = "dormant"
        # Idle: all calm
        else:
            self._current_interval = self.config.heartbeat_idle
            self._heartbeat_mode = "idle"

        if old_interval != self._current_interval:
            self.renderer.render_heartbeat_change(
                old_mode, self._heartbeat_mode, self._current_interval
            )

    @staticmethod
    def _max_drive_urgency(drive_state: dict[str, dict[str, Any]]) -> float:
        """Return the highest drive urgency value."""
        if not drive_state:
            return 0.0
        return max(s.get("value", 0.0) for s in drive_state.values())

    def _get_drive_state_dict(self) -> dict[str, dict[str, Any]]:
        """Get drive states in format expected by dialogue system.

        Returns:
            Dictionary mapping drive names to their state dicts
        """
        result: dict[str, dict[str, Any]] = {}
        for name, drive in self.drive_system.drives.items():
            result[name] = {
                "value": drive.demand,
                "threshold": 0.5,  # Default threshold
                "below_threshold": drive.demand > 0.5,  # High demand = needs attention
            }
        return result

    def _build_dialogue_context(
        self,
        somatic: SomaticState,
        events: list[Any],
        utterances: list[str] | None = None,
    ) -> str:
        """Build context string for dialogue generation.

        Args:
            somatic: Current somatic state
            events: Recent events
            utterances: Speech heard from humans

        Returns:
            Context string
        """
        context_parts = []

        # Add speech context first (most salient input)
        if utterances:
            speech_text = "; ".join(f'"{u}"' for u in utterances)
            context_parts.append(f"Human said: {speech_text}")

        # Add somatic context
        context_parts.append(f"Battery: {somatic.battery_percent}%")
        if somatic.battery_percent < 20:
            context_parts.append("(battery critically low)")
        if somatic.thermal_state.value in ("hot", "critical"):
            context_parts.append(f"Thermal: {somatic.thermal_state.value}")
        if somatic.cpu_percent > 70:
            context_parts.append(f"CPU: {somatic.cpu_percent:.0f}% (busy)")

        # Add recent events
        if events:
            event_descs = [e.description for e in events[:3]]
            context_parts.append(f"Recent: {'; '.join(event_descs)}")

        # Add memory context
        memory_context = self.memory.get_context(count=2)
        if memory_context and "No" not in memory_context:
            context_parts.append(memory_context)

        return ". ".join(context_parts) if context_parts else "All systems normal"

    def _publish_dialogue_triggers(
        self,
        utterances: list[str] | None,
        somatic: SomaticState,
    ) -> None:
        """Publish events that trigger dialogue generation.

        Detects threshold crossings and salient stimuli, publishing
        dialogue.trigger events that the DialogueManager subscribes to.
        """
        # Drive urgency crossing 0.7
        for name, drive in self.drive_system.drives.items():
            prev = self._prev_drive_urgency.get(name, 0.0)
            if drive.urgency >= 0.7 and prev < 0.7:
                self.event_bus.publish(
                    "dialogue.trigger",
                    {"reason": f"drive:{name}", "drive": name, "urgency": drive.urgency},
                )
            self._prev_drive_urgency[name] = drive.urgency

        # Speech utterance
        if utterances:
            self.event_bus.publish(
                "dialogue.trigger",
                {"reason": "speech", "utterances": utterances},
            )

        # Somatic alarm
        if somatic.battery_percent < 10 or somatic.thermal_state.value == "critical":
            self.event_bus.publish(
                "dialogue.trigger",
                {"reason": "somatic_alarm"},
            )


def run_single(config: AgentConfig | None = None, perception: str | None = None) -> str:
    """Run a single perception-response cycle (for testing)."""
    from sociopsi.llm import LLMError, chat_with_retry
    from sociopsi.parser import parse_response
    from sociopsi.perception import format_perception

    config = config or AgentConfig()

    # Start voice if enabled
    voice: Voice | None = None
    if config.voice_enabled:
        voice = Voice(config)
        voice.start()

    if perception is None:
        somatic = gather_somatic()
        perception = format_perception(
            config=config,
            somatic=somatic,
            events=[],
            action_results=[],
            heartbeat_interval=60,
            heartbeat_mode="idle",
        )

    try:
        response = chat_with_retry(
            model=config.model,
            messages=[{"role": "user", "content": perception}],
            provider=config.llm_provider,
        )
        content = response["message"]["content"]

        # Parse and speak the stream if voice enabled
        if voice:
            parsed = parse_response(content)
            if parsed and parsed.stream:
                voice.speak_stream(parsed.stream)
            # Wait for all speech to complete before exiting
            voice.stop(wait_for_completion=True)

        return content
    except LLMError as e:
        if voice:
            voice.stop()
        return f'{{"stream":[],"actions":[],"error":"{e}"}}'
