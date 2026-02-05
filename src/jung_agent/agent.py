"""The main agent loop."""

import signal
import sys
import threading
import time
from datetime import datetime
from types import FrameType
from typing import Final, Literal, TypedDict

from jung_agent.actions.executor import ActionExecutor
from jung_agent.config import AgentConfig, load_system_prompt
from jung_agent.drives import DriveSystem
from jung_agent.llm import LLMError, chat_with_retry
from jung_agent.logger import PsycheLogger
from jung_agent.parser import parse_response
from jung_agent.perception import format_perception
from jung_agent.sensors.events import EventCollector
from jung_agent.sensors.somatic import gather_somatic
from jung_agent.terminal import colors
from jung_agent.types import Action, ActionResult, PsycheComponent, SomaticState, StreamSegment
from jung_agent.voice import Voice

# Type for chat message role
MessageRole = Literal["system", "user", "assistant"]


class ChatMessage(TypedDict):
    """A chat message for the LLM."""

    role: MessageRole
    content: str


# Heartbeat mode type
HeartbeatMode = Literal["idle", "active", "stressed", "critical", "dormant", "override"]


class JungAgent:
    """The Jungian psyche agent."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()
        self.executor = ActionExecutor(self.config)
        self.event_collector = EventCollector()
        self.voice = Voice(self.config)
        self.logger = PsycheLogger(self.config)
        self.drive_system = DriveSystem(self.config)

        self._running: bool = False
        self._shutdown_event: threading.Event = threading.Event()
        self._last_action_results: list[ActionResult] = []
        self._current_interval: float = self.config.heartbeat_idle
        self._heartbeat_mode: HeartbeatMode = "idle"
        self._last_update_time: float = time.time()

        # Load system prompt and initialize conversation with few-shot examples
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
        self.voice.start()

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        print(f"Jung Agent starting with model: {self.config.model}")
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
        self.event_collector.stop()
        self.voice.stop()
        print("\nJung Agent stopped.")

    def _handle_shutdown(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        print("\nShutdown signal received...")
        self.stop()
        sys.exit(0)

    def _run_loop(self) -> None:
        """Main agent loop."""
        cycle_count = 0
        while self._running:
            loop_start = time.time()
            cycle_count += 1

            try:
                # Header with cycle number and timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n{'=' * 70}")
                print(f"{colors.BOLD}[CYCLE {cycle_count}] {timestamp}{colors.RESET}")
                print("=" * 70)

                # 1. Gather somatic state
                somatic = gather_somatic()

                # 2. Collect events
                events = self.event_collector.collect_events(somatic)

                # 3. Update drives
                now = time.time()
                dt = now - self._last_update_time
                self._last_update_time = now
                had_actions = len(self._last_action_results) > 0
                self.drive_system.update(somatic, dt, had_actions)

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

                # 7. Print events if any
                if events:
                    print(f"\n{colors.CYAN}[EVENTS]{colors.RESET}")
                    for event in events:
                        ts = event.timestamp.strftime("%H:%M:%S")
                        print(f"  [{ts}] {event.type}: {event.description}")

                # 8. Format full perception (including drives)
                drive_perception = self.drive_system.format_for_perception()
                perception = format_perception(
                    config=self.config,
                    somatic=somatic,
                    events=events,
                    action_results=self._last_action_results,
                    heartbeat_interval=self._current_interval,
                    heartbeat_mode=self._heartbeat_mode,
                    drives=drive_perception,
                )

                # 6. Send to psyche
                response = self._query_psyche(perception)

                # 7. Parse response
                parsed = parse_response(response)

                # 8. Print raw response if no stream parsed
                if not parsed.stream and not parsed.actions:
                    print(f"\n{colors.RED}[RAW RESPONSE - PARSE FAILED]{colors.RESET}")
                    print(response[:500] + ("..." if len(response) > 500 else ""))

                # 9. Log and speak stream
                if self.config.log_stream:
                    self._log_stream(parsed.stream)

                # Speak the internal monologue
                self.voice.speak_stream(parsed.stream)

                # 10. Build final action list
                final_actions: list[Action] = []

                # Add compulsive actions first (survival override)
                if compulsive:
                    final_actions.extend(compulsive)

                # Get primed actions for high-urgency drives
                primed = self.drive_system.get_primed_actions()
                proposed_types = {a.type for a in parsed.actions}
                for action in primed:
                    if action.type not in proposed_types:
                        final_actions.append(action)

                # Add LLM-proposed actions
                final_actions.extend(parsed.actions)

                # Announce and execute actions
                if final_actions:
                    print(f"\n{colors.YELLOW}[ACTIONS]{colors.RESET}")
                    for i, action in enumerate(final_actions, 1):
                        # Mark source of action
                        if action in compulsive:
                            source = f" {colors.RED}(compulsive){colors.RESET}"
                        elif action in primed:
                            source = f" {colors.MAGENTA}(primed){colors.RESET}"
                        else:
                            source = ""
                        params_str = ", ".join(f"{k}={v!r}" for k, v in action.params.items())
                        if params_str:
                            print(f"  {i}. {action.type}({params_str}){source}")
                        else:
                            print(f"  {i}. {action.type}(){source}")
                    self.voice.announce_actions(final_actions)
                else:
                    print(f"\n{colors.YELLOW}[ACTIONS]{colors.RESET} (none)")

                self._last_action_results = self.executor.execute_all(final_actions)

                # Satisfy drives from action results
                self.drive_system.satisfy_from_results(self._last_action_results)

                # Speak what was seen/heard
                self.voice.speak_perceptions(self._last_action_results)

                # Log action results with full details
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

                # 11. Log perception, drives, and state
                self.logger.log_cycle(
                    perception=perception,
                    somatic=somatic,
                    stream=parsed.stream,
                    actions=[a.type for a in final_actions],
                    action_results=self._last_action_results,
                    heartbeat_interval=self._current_interval,
                    heartbeat_mode=self._heartbeat_mode,
                    drives=self.drive_system.get_state(),
                )

                # 9. Check for heartbeat override
                override = self.executor.get_heartbeat_override()
                if override is not None:
                    self._current_interval = override
                    self._heartbeat_mode = "override"
                    print(f"  [HEARTBEAT] Set to {override}s by psyche")
                else:
                    # Adaptive heartbeat
                    self._update_heartbeat(somatic)

            except Exception as e:
                print(f"Error in loop: {e}")
                import traceback

                traceback.print_exc()

            # 9. Wait for next heartbeat (or interrupt)
            elapsed = time.time() - loop_start
            wait_time = max(0, self._current_interval - elapsed)

            if wait_time > 0:
                self._shutdown_event.wait(wait_time)

    def _query_psyche(self, perception: str) -> str:
        """Query the psyche model."""
        # Add perception to messages
        self._messages.append(ChatMessage(role="user", content=perception))

        # Trim history if needed (preserve system message)
        if len(self._messages) > self._max_history * 2 + 1:
            # Keep system message + last N exchanges
            self._messages = [self._messages[0]] + self._messages[-(self._max_history * 2) :]

        # Query model with retry logic
        try:
            response = chat_with_retry(
                model=self.config.model,
                messages=self._messages,
            )
            assistant_message: str = response["message"]["content"]
        except LLMError as e:
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


def run_single(config: AgentConfig | None = None, perception: str | None = None) -> str:
    """Run a single perception-response cycle (for testing)."""
    config = config or AgentConfig()

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
        )
        return response["message"]["content"]
    except LLMError as e:
        return f'{{"stream":[],"actions":[],"error":"{e}"}}'
