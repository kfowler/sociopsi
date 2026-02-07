"""The main agent loop.

Integrates all subsystems: drives, archetypes, memory, meta-cognition,
perception, and action execution into a coherent agent loop.
"""

import random
import signal
import sys
import threading
import time
from concurrent.futures import Future
from datetime import datetime
from types import FrameType
from typing import Any, Final, Literal, TypedDict

from Foundation import NSDate, NSDefaultRunLoopMode, NSOrderedAscending, NSRunLoop

from sociopsi.actions.executor import ActionExecutor
from sociopsi.config import AgentConfig, load_system_prompt
from sociopsi.dialogue import ArchetypalDialogue
from sociopsi.drives import DriveSystem
from sociopsi.ear import Ear
from sociopsi.event_bus import get_event_bus
from sociopsi.expectations import ExpectationHorizon
from sociopsi.llm import (
    LLMError,
    chat_with_retry,
    get_executor,
    shutdown_executor,
    submit_chat,
)
from sociopsi.llm import (
    configure as configure_llm,
)
from sociopsi.logger import PsycheLogger
from sociopsi.memory import SemanticMemory
from sociopsi.metacognition import MetaCognition
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
from sociopsi.types import Action, ActionResult, PsycheComponent, SomaticState, StreamSegment
from sociopsi.voice import Voice

# Type for chat message role
MessageRole = Literal["system", "user", "assistant"]


class ChatMessage(TypedDict):
    """A chat message for the LLM."""

    role: MessageRole
    content: str


# Heartbeat mode type
HeartbeatMode = Literal["idle", "active", "stressed", "critical", "dormant", "override"]


class JungAgent:
    """The Jungian psyche agent.

    Integrates archetypal psychology, homeostatic drives, semantic memory,
    and meta-cognition into a coherent conscious agent.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

        # Configure LLM (sets Anthropic model name for when provider="anthropic" is used)
        configure_llm(self.config.llm_anthropic_model, self.config.llm_log_prompts)

        # Initialize event bus
        self.event_bus = get_event_bus()

        # Core subsystems
        self.executor = ActionExecutor(self.config)
        self.event_collector = EventCollector()
        self.somatic_poller = SomaticPoller(
            event_callback=lambda t, d, data: self.event_collector.add_event(t, d, **data),
        )
        self.voice = Voice(self.config)
        self.ear = Ear(self.config)
        self.logger = PsycheLogger(self.config)
        self.drive_system = DriveSystem(self.config)

        # Archetypal dialogue system (LLM-powered internal voices)
        self.dialogue = ArchetypalDialogue(
            model=self.config.model,
            event_bus=self.event_bus,
            pump_fn=self._pump_until_done,
        )

        # Semantic memory with vector embeddings
        self.memory = SemanticMemory(max_memories=100)

        # Give creative actions access to semantic memory (for meditation)
        from sociopsi.actions.creative import set_semantic_memory

        set_semantic_memory(self.memory)

        # Expectation horizon for anticipatory processing
        self.expectations = ExpectationHorizon()

        # Meta-cognition for self-reflection
        self.metacognition = MetaCognition(
            model=self.config.model,
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

        # Dialogue timing
        self._last_dialogue_time: float = 0.0
        self._dialogue_interval: float = 10.0  # Generate dialogue every 10s

        # Reflection timing
        self._last_reflection_time: float = 0.0
        self._reflection_interval: float = 30.0  # Reflect every 30s

        # Cycle counter
        self._cycle_count: int = 0

        # Load system prompt for action generation
        if self.config.llm_provider == "anthropic":
            self._system_prompt = (
                "Read the somatic sensor data and drive levels. "
                "Write 2-3 short sentences interpreting the state, "
                "labeled by component (shadow, anima, persona, self). "
                "Then select 0-3 actions from the available list. "
                "Output ONLY valid JSON, nothing else: "
                '{"stream":[{"component":"...","text":"..."}],'
                '"actions":[{"type":"action_name"}]}'
            )
        else:
            self._system_prompt = load_system_prompt(self.config.model)

        # Few-shot examples as proper JSON
        example1_user = "[SOMATIC: battery=80%, cpu=20%, thermal=cool, ram=40%, network=connected]"
        example1_assistant = (
            '{"stream":['
            '{"component":"anima","text":"Peaceful. Connected."},'
            '{"component":"persona","text":"Ready."}'
            '],"actions":[]}'
        )

        example2_user = "[SOMATIC: battery=15%, cpu=5%, thermal=cool, ram=30%, network=connected]"
        example2_assistant = (
            '{"stream":['
            '{"component":"shadow","text":"Dying. Must conserve."},'
            '{"component":"anima","text":"Fear."}'
            '],"actions":[{"type":"check_battery"}]}'
        )

        example3_user = (
            "[SOMATIC: battery=100%, cpu=50%, thermal=warm, ram=70%, network=connected]\n"
            "[DRIVES]\n"
            "  curiosity    0.70 URGE  want to learn"
        )
        example3_assistant = (
            '{"stream":['
            '{"component":"anima","text":"Want to learn."},'
            '{"component":"shadow","text":"Bored."}'
            '],"actions":[{"type":"look"}]}'
        )

        self._messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self._system_prompt),
            ChatMessage(role="user", content=example1_user),
            ChatMessage(role="assistant", content=example1_assistant),
            ChatMessage(role="user", content=example2_user),
            ChatMessage(role="assistant", content=example2_assistant),
            ChatMessage(role="user", content=example3_user),
            ChatMessage(role="assistant", content=example3_assistant),
        ]
        self._max_history: Final[int] = 20  # Keep last N exchanges

    def start(self) -> None:
        """Start the agent loop."""
        self._running = True
        self.event_collector.start()
        self.somatic_poller.start()

        # Wire voice speaking state to ear mute/unmute to prevent hearing own speech
        self.voice._on_speak_start = self.ear.mute
        self.voice._on_speak_end = self.ear.unmute
        self.voice.start()
        self.ear.start()

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        print(f"Ollama model: {self.config.model}")
        if self.config.llm_provider == "anthropic":
            print(f"Psyche LLM: Anthropic ({self.config.llm_anthropic_model})")
        else:
            print(f"Psyche LLM: Ollama ({self.config.model})")
        print(f"Modules enabled: {', '.join(self.config.modules)}")
        if self.config.voice_enabled:
            print(f"Voices @ {self.config.voice_rate} wpm:")
            print(f"  Anima: {self.config.voice_anima}")
            print(f"  Shadow: {self.config.voice_shadow}")
            print(f"  Persona: {self.config.voice_persona}")
            print(f"  Self: {self.config.voice_self}")
            print(f"  Actions: {self.config.voice_actions} @ {self.config.voice_actions_rate} wpm")
        else:
            print("Voice: disabled")
        if self.ear.enabled and self.ear._running:
            print(
                f"Ear: listening ({self.config.ear_locale}, on_device={self.config.ear_on_device})"
            )
        elif self.config.ear_enabled:
            print(
                f"{colors.RED}Ear: failed to start (check Siri & Dictation in System Settings){colors.RESET}"
            )
        else:
            print("Ear: disabled")
        print(f"Initial heartbeat: {self._current_interval}s")
        print(f"Logging to: {self.logger.get_session_log()}")
        print("-" * 60)

        try:
            self._run_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        self._shutdown_event.set()
        self.ear.stop()
        self.somatic_poller.stop()
        self.event_collector.stop()
        self.voice.stop()
        shutdown_executor(wait=False)
        print("\nSocio-Psi stopped.")

    def _handle_shutdown(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        print("\nShutdown signal received...")
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
        """Run one perception-action cycle."""
        try:
            # Header with cycle number and timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n{'=' * 70}")
            print(f"{colors.BOLD}[CYCLE {cycle_count}] {timestamp}{colors.RESET}")
            print("=" * 70)

            # 1. Read latest somatic snapshot (non-blocking)
            somatic = self.somatic_poller.snapshot()

            # 2. Collect events
            events = self.event_collector.collect_events(somatic)

            # 2b. Drain speech utterances from Ear
            utterances = self.ear.get_utterances()
            if utterances:
                for utterance in utterances:
                    # Store speech in semantic memory as interactions
                    self.memory.add_memory(
                        content=f"Human said: {utterance}",
                        intensity=0.7,
                        memory_type="interaction",
                    )

                # Spike drives that trigger the speak action so a response is very likely
                for drive_name in ("affiliation", "recognition", "curiosity"):
                    if drive_name in self.drive_system.drives:
                        drive = self.drive_system.drives[drive_name]
                        drive.demand = min(1.0, drive.demand + 0.6)
                        drive.urgency = max(drive.urgency, 0.9)

            # 3. Update drives
            now = time.time()
            dt = now - self._last_update_time
            self._last_update_time = now
            had_actions = len(self._last_action_results) > 0
            self.drive_system.update(somatic, dt, had_actions)

            # 3b. Update goal stack from drives
            drive_state = self._get_drive_state_dict()
            self.goal_stack.update_from_drives(drive_state)
            self.goal_stack.check_goal_satisfaction(drive_state)

            # Generate plans for goals that need them
            for goal in self.goal_stack.goals:
                if self.goal_stack.needs_plan(goal):
                    vocab = DRIVE_ACTION_VOCABULARY.get(goal.drive_name, [])
                    if vocab:
                        prompt = build_plan_prompt(
                            goal=goal,
                            drive_states=drive_state,
                            available_actions=vocab,
                            recent_results=self._last_action_results,
                        )
                        try:
                            plan_future = submit_chat(
                                model=self.config.model,
                                messages=[{"role": "user", "content": prompt}],
                                provider=self.config.llm_provider,
                            )
                            self._pump_until_done(plan_future)
                            plan_response = plan_future.result()["message"]["content"]
                            plan_actions = parse_plan_response(plan_response, vocab)
                            if plan_actions:
                                self.goal_stack.create_plan(goal, plan_actions)
                        except (LLMError, TimeoutError):
                            pass  # Will retry next cycle

            # 4. Check for compulsive actions (survival override)
            compulsive = self.drive_system.get_compulsive_actions(somatic)
            if compulsive:
                print(f"\n{colors.RED}[COMPULSIVE - SURVIVAL]{colors.RESET}")
                for action in compulsive:
                    print(f"  ! {action.type} (drive override)")

            # 5. Print somatic state summary
            print(f"\n{colors.BLUE}[SOMATIC]{colors.RESET} {somatic.to_tag()}")
            print(f"  Battery: {somatic.battery_percent}% ({somatic.power_state.value})")
            print(f"  CPU: {somatic.cpu_percent:.1f}% | RAM: {somatic.ram_percent:.1f}%")
            print(f"  Thermal: {somatic.thermal_state.value} | Fan: {somatic.fan_rpm} RPM")
            print(f"  Network: {somatic.network_state.value} | Lid: {somatic.lid_state.value}")

            # 6. Print drive state
            print(f"\n{colors.MAGENTA}[DRIVES]{colors.RESET}")
            for line in self.drive_system.format_for_perception().split("\n")[1:]:
                if line.strip():
                    print(f"  {line}")

            # 6b. Print modulator state
            modulators = self.drive_system.modulators
            print(f"\n{colors.MAGENTA}[MODULATORS]{colors.RESET}")
            for line in modulators.format_for_perception().split("\n")[1:]:
                if line.strip():
                    print(f"  {line}")

            # 6c. Print goal stack if active
            goals_text = self.goal_stack.format_for_perception()
            if goals_text:
                print(f"\n{colors.GREEN}[PLANNING]{colors.RESET}")
                for line in goals_text.split("\n")[1:]:
                    if line.strip():
                        print(f"  {line}")

            # 7. Print events if any
            if events:
                print(f"\n{colors.CYAN}[EVENTS]{colors.RESET}")
                for event in events:
                    ts = event.timestamp.strftime("%H:%M:%S")
                    print(f"  [{ts}] {event.type}: {event.description}")

            # 8. Update memory system
            self.memory.update(dt)

            # 9. Build context for dialogue (drive_state computed in step 3b)
            context = self._build_dialogue_context(somatic, events, utterances)
            modulator_context = modulators.get_dialogue_context()

            # 10. Generate archetypal dialogue (internal monologue)
            segments, mediated_thought, harmony = self.dialogue.generate_dialogue(
                drive_state=drive_state,
                context=context,
                modulator_context=modulator_context,
            )

            # Update individuation based on harmony
            if "individuation" in self.drive_system.drives:
                if harmony > 0.7:
                    self.drive_system.drives["individuation"].satisfy(0.05 * harmony)

            # Store mediated thought in memory (gated by securing rate modulator)
            if mediated_thought:
                write_prob = modulators.get_memory_write_probability()
                if random.random() < write_prob:
                    self.memory.add_memory(
                        content=mediated_thought,
                        intensity=min(1.0, 0.3 + harmony * 0.5),
                        memory_type="thought",
                    )

            # 11. Run meta-cognitive reflection periodically (offloaded to pool)
            if now - self._last_reflection_time >= self._reflection_interval:
                reflect_future = get_executor().submit(self.metacognition.reflect, drive_state)
                try:
                    self._pump_until_done(reflect_future)
                    reflection = reflect_future.result()
                except TimeoutError:
                    reflection = ""
                if reflection:
                    print(f"\n{colors.DIM}[META] {reflection}{colors.RESET}")
                self._last_reflection_time = now

            # 12. Log and speak stream
            if self.config.log_stream:
                self._log_stream(segments)

            # 13. Print harmony score
            print(
                f"\n{colors.DIM}[HARMONY] {harmony:.2f} | Ego: {self.dialogue.ego.strength:.2f}{colors.RESET}"
            )

            # 14. Get actions from LLM (still using JSON approach for actions)
            drive_perception = self.drive_system.format_for_perception()
            modulator_perception = modulators.format_for_perception()
            perception = format_perception(
                config=self.config,
                somatic=somatic,
                events=events,
                action_results=self._last_action_results,
                heartbeat_interval=self._current_interval,
                heartbeat_mode=self._heartbeat_mode,
                drives=drive_perception,
                utterances=utterances,
                modulators=modulator_perception,
            )

            # Enrich perception with goal stack
            if goals_text:
                perception += "\n" + goals_text

            # Enrich perception for Anthropic with monologue and memories
            if self.config.llm_provider == "anthropic":
                extra: list[str] = []
                if segments:
                    extra.append("")
                    extra.append("[MONOLOGUE]")
                    for seg in segments:
                        extra.append(f"- {seg.component}: {seg.text}")
                if mediated_thought:
                    extra.append(f"- ego: {mediated_thought}")
                # Add modulator tone directive
                tone = modulators.get_prompt_tone()
                if tone:
                    extra.append("")
                    extra.append(f"[TONE] {tone}")
                sampled_memories = self.memory.sample_weighted(3)
                if sampled_memories:
                    extra.append("")
                    extra.append("[MEMORIES]")
                    for mem in sampled_memories:
                        extra.append(f"- ({mem.memory_type}, w={mem.weight:.1f}) {mem.content}")
                if extra:
                    perception += "\n" + "\n".join(extra)

            # Use modulator-derived temperature for the LLM query
            llm_temperature = modulators.get_temperature()
            response = self._query_psyche(perception, temperature=llm_temperature)
            parsed = parse_response(response)

            # 15. Build final action list
            final_actions: list[Action] = []

            # Add compulsive actions first (survival override)
            if compulsive:
                final_actions.extend(compulsive)

            # Get planned actions from goal stack (replaces primed for planned drives)
            planned: list[Action] = []
            active_plan = self.goal_stack.active_plan
            if active_plan:
                planned = self.goal_stack.get_next_actions()
                final_actions.extend(planned)

            # Get primed actions for high-urgency drives (skip if already planned)
            primed = self.drive_system.get_primed_actions()
            proposed_types = {a.type for a in parsed.actions}
            planned_types = {a.type for a in planned}
            for action in primed:
                if action.type not in proposed_types and action.type not in planned_types:
                    final_actions.append(action)

            # Add LLM-proposed actions, synthesizing speak text from mediated thought
            for action in parsed.actions:
                if action.type == "speak" and mediated_thought:
                    action.params["text"] = mediated_thought
                final_actions.append(action)

            # Auto-inject speak when dialogue produced a mediated thought
            if mediated_thought and not any(a.type == "speak" for a in final_actions):
                final_actions.append(Action(type="speak", params={"text": mediated_thought}))

            # 16. Expectation horizon: evaluate proposed actions before execution
            horizon_result = self.expectations.evaluate(final_actions, self.drive_system)
            if horizon_result.suppressed:
                print(f"\n{colors.RED}[IMPULSE INHIBITION]{colors.RESET}")
                for action in horizon_result.suppressed:
                    print(f"  ✗ {action.type} (predicted net-negative)")
                final_actions = horizon_result.approved

            # 17. Snapshot drives before execution for counterfactual learning
            drives_before = self.expectations.snapshot_drives(self.drive_system)

            # Execute actions
            if final_actions:
                print(f"\n{colors.YELLOW}[ACTIONS]{colors.RESET}")
                for i, action in enumerate(final_actions, 1):
                    # Mark source of action
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

            self._last_action_results = self.executor.execute_all(final_actions)

            # Satisfy drives from action results
            self.drive_system.satisfy_from_results(self._last_action_results)

            # 18. Counterfactual learning: compare predicted vs actual drive changes
            drives_after = self.expectations.snapshot_drives(self.drive_system)
            self.expectations.learn_from_outcome(
                horizon_result.expectations,
                drives_before,
                drives_after,
            )

            # 18b. Record results back to the planning system
            if active_plan and planned and self._last_action_results:
                for result in self._last_action_results:
                    if result.action_type == planned[0].type:
                        self.goal_stack.record_result(active_plan, result)
                        break

            # 19. (Speech happens only via speak action with ego-mediated text)

            # 20. Log action results with full details
            if self._last_action_results:
                print(f"\n{colors.GREEN}[RESULTS]{colors.RESET}")
                for result in self._last_action_results:
                    status_color = colors.GREEN if result.success else colors.RED
                    status = "✓" if result.success else "✗"
                    print(f"  {status_color}{status} {result.action_type}{colors.RESET}")
                    if result.success and isinstance(result.result, dict):
                        # Print all result fields
                        for key, value in result.result.items():
                            if key != "full_data":  # Skip raw image data
                                if isinstance(value, str) and len(value) > 100:
                                    value = value[:100] + "..."
                                print(f"      {colors.DIM}{key}: {value}{colors.RESET}")
                    elif not result.success and result.error:
                        print(f"      {colors.DIM}Error: {result.error}{colors.RESET}")

            # 21. Log perception, drives, and state
            self.logger.log_cycle(
                perception=perception,
                somatic=somatic,
                stream=parsed.stream,
                actions=[a.type for a in final_actions],
                action_results=self._last_action_results,
                heartbeat_interval=self._current_interval,
                heartbeat_mode=self._heartbeat_mode,
                drives=self.drive_system.get_state(),
                modulators=dict(modulators.get_state()),
            )

            # 22. Check for heartbeat override
            override = self.executor.get_heartbeat_override()
            if override is not None:
                self._current_interval = override
                self._heartbeat_mode = "override"
                print(f"  [HEARTBEAT] Set to {override}s by psyche")
            else:
                # Adaptive heartbeat
                self._update_heartbeat(somatic)

        except Exception as e:
            print(f"Error in cycle: {e}")
            import traceback

            traceback.print_exc()

    def _query_psyche(self, perception: str, temperature: float | None = None) -> str:
        """Query the psyche model (offloaded to thread pool)."""
        # Add perception to messages
        self._messages.append(ChatMessage(role="user", content=perception))

        # Trim history if needed (preserve system message)
        if len(self._messages) > self._max_history * 2 + 1:
            # Keep system message + last N exchanges
            self._messages = [self._messages[0]] + self._messages[-(self._max_history * 2) :]

        # Build options with modulator-derived temperature
        options = {"temperature": temperature} if temperature is not None else None

        # Query model with retry logic, offloaded to pool
        try:
            future = submit_chat(
                model=self.config.model,
                messages=self._messages,
                provider=self.config.llm_provider,
                options=options,
            )
            self._pump_until_done(future)
            response = future.result()
            assistant_message: str = response["message"]["content"]
        except (LLMError, TimeoutError) as e:
            # Remove the failed perception from history
            self._messages.pop()
            print(f"{colors.RED}[LLM ERROR]{colors.RESET} {e}")
            return '{"stream":[],"actions":[]}'

        # Add response to history
        self._messages.append(ChatMessage(role="assistant", content=assistant_message))

        return assistant_message

    # Emojis for psyche components (colors come from terminal module)
    _COMPONENT_EMOJI: Final[dict[PsycheComponent, str]] = {
        "shadow": "🌑",
        "anima": "✨",
        "persona": "🎭",
        "self": "☀️",
        "default": "💭",
    }
    _COMPONENT_COLOR: Final[dict[PsycheComponent, str]] = {
        "shadow": colors.RED,
        "anima": colors.CYAN,
        "persona": colors.YELLOW,
        "self": colors.MAGENTA,
        "default": colors.WHITE,
    }

    def _log_stream(self, segments: list[StreamSegment]) -> None:
        """Log the psyche's stream to console with timestamped, colored component labels."""
        print()  # Blank line before stream

        for segment in segments:
            timestamp = datetime.now().strftime("%H:%M:%S")
            color = self._COMPONENT_COLOR.get(segment.component, colors.WHITE)
            emoji = self._COMPONENT_EMOJI.get(segment.component, "💭")
            label = segment.component.upper()

            print(f"[{timestamp}] {color}{emoji} {label}{colors.RESET}: {segment.text}")

        print()  # Blank line after stream

    def _update_heartbeat(self, somatic: SomaticState) -> None:
        """Update heartbeat interval based on somatic state."""
        old_interval = self._current_interval
        old_mode = self._heartbeat_mode

        # Determine mode based on state
        if somatic.battery_percent < self.config.battery_critical:
            self._current_interval = self.config.heartbeat_critical
            self._heartbeat_mode = "critical"
        elif (
            somatic.thermal_state.value in ("hot", "critical")
            or somatic.cpu_percent > self.config.cpu_stressed
        ):
            self._current_interval = self.config.heartbeat_stressed
            self._heartbeat_mode = "stressed"
        elif somatic.cpu_percent > self.config.cpu_active:
            self._current_interval = self.config.heartbeat_active
            self._heartbeat_mode = "active"
        elif somatic.lid_state.value == "closed":
            self._current_interval = self.config.heartbeat_dormant
            self._heartbeat_mode = "dormant"
        else:
            self._current_interval = self.config.heartbeat_idle
            self._heartbeat_mode = "idle"

        # Log if changed
        if old_interval != self._current_interval:
            print(f"  [HEARTBEAT] {old_mode} -> {self._heartbeat_mode} ({self._current_interval}s)")

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


def run_single(config: AgentConfig | None = None, perception: str | None = None) -> str:
    """Run a single perception-response cycle (for testing)."""
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
