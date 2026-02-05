"""The main agent loop."""

import signal
import sys
import threading
import time
from datetime import datetime

import ollama

from jung_agent.actions.executor import ActionExecutor
from jung_agent.config import AgentConfig
from jung_agent.logger import PsycheLogger
from jung_agent.parser import parse_response
from jung_agent.perception import format_perception
from jung_agent.sensors.events import EventCollector
from jung_agent.sensors.somatic import gather_somatic
from jung_agent.types import ActionResult, SomaticState, StreamSegment
from jung_agent.voice import Voice


class JungAgent:
    """The Jungian psyche agent."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()
        self.executor = ActionExecutor(self.config)
        self.event_collector = EventCollector()
        self.voice = Voice(self.config)
        self.logger = PsycheLogger(self.config)

        self._running = False
        self._shutdown_event = threading.Event()
        self._last_action_results: list[ActionResult] = []
        self._current_interval = self.config.heartbeat_idle
        self._heartbeat_mode = "idle"

        # Conversation history for context
        self._messages: list[dict[str, str]] = []
        self._max_history = 20  # Keep last N exchanges

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

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        print("\nShutdown signal received...")
        self.stop()
        sys.exit(0)

    _MAGENTA = "\033[35m"
    _RED = "\033[31m"
    _BLUE = "\033[34m"
    _BOLD = "\033[1m"

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
                print(f"{self._BOLD}[CYCLE {cycle_count}] {timestamp}{self._RESET}")
                print("=" * 70)

                # 1. Gather somatic state
                somatic = gather_somatic()

                # 2. Collect events
                events = self.event_collector.collect_events(somatic)

                # 3. Print somatic state summary
                print(f"\n{self._BLUE}[SOMATIC]{self._RESET} {somatic.to_tag()}")
                print(f"  Battery: {somatic.battery_percent}% ({somatic.power_state.value})")
                print(f"  CPU: {somatic.cpu_percent:.1f}% | RAM: {somatic.ram_percent:.1f}%")
                print(f"  Thermal: {somatic.thermal_state.value} | Fan: {somatic.fan_rpm} RPM")
                print(f"  Network: {somatic.network_state.value} | Lid: {somatic.lid_state.value}")

                # 4. Print events if any
                if events:
                    print(f"\n{self._MAGENTA}[EVENTS]{self._RESET}")
                    for event in events:
                        ts = event.timestamp.strftime("%H:%M:%S")
                        print(f"  [{ts}] {event.type}: {event.description}")

                # 5. Format full perception
                perception = format_perception(
                    config=self.config,
                    somatic=somatic,
                    events=events,
                    action_results=self._last_action_results,
                    heartbeat_interval=self._current_interval,
                    heartbeat_mode=self._heartbeat_mode,
                )

                # Print perception (full)
                print(f"\n{self._CYAN}[PERCEPTION → LLM]{self._RESET}")
                print("-" * 50)
                for line in perception.split("\n"):
                    print(f"  {self._DIM}{line}{self._RESET}")
                print("-" * 50)

                # 6. Send to psyche
                response = self._query_psyche(perception)

                # 7. Parse response
                parsed = parse_response(response)

                # 8. Print raw response if no stream parsed
                if not parsed.stream and not parsed.actions:
                    print(f"\n{self._RED}[RAW RESPONSE - PARSE FAILED]{self._RESET}")
                    print(response[:500] + ("..." if len(response) > 500 else ""))

                # 9. Log and speak stream
                if self.config.log_stream:
                    self._log_stream(parsed.stream)

                # Speak the internal monologue
                self.voice.speak_stream(parsed.stream)

                # 10. Announce and execute actions
                if parsed.actions:
                    print(f"\n{self._YELLOW}[ACTIONS]{self._RESET}")
                    for i, action in enumerate(parsed.actions, 1):
                        params_str = ", ".join(f"{k}={v!r}" for k, v in action.params.items())
                        if params_str:
                            print(f"  {i}. {action.type}({params_str})")
                        else:
                            print(f"  {i}. {action.type}()")
                    self.voice.announce_actions(parsed.actions)
                else:
                    print(f"\n{self._YELLOW}[ACTIONS]{self._RESET} (none)")

                self._last_action_results = self.executor.execute_all(parsed.actions)

                # Speak what was seen/heard
                self.voice.speak_perceptions(self._last_action_results)

                # Log action results with full details
                if self._last_action_results:
                    print(f"\n{self._GREEN}[RESULTS]{self._RESET}")
                    for result in self._last_action_results:
                        status_color = self._GREEN if result.success else self._RED
                        status = "✓" if result.success else "✗"
                        print(f"  {status_color}{status} {result.action_type}{self._RESET}")
                        if result.success and isinstance(result.result, dict):
                            # Print all result fields
                            for key, value in result.result.items():
                                if key != "full_data":  # Skip raw image data
                                    if isinstance(value, str) and len(value) > 100:
                                        value = value[:100] + "..."
                                    print(f"      {self._DIM}{key}: {value}{self._RESET}")
                        elif not result.success and result.error:
                            print(f"      {self._DIM}Error: {result.error}{self._RESET}")

                # 8. Log perception, drives, and state
                self.logger.log_cycle(
                    perception=perception,
                    somatic=somatic,
                    stream=parsed.stream,
                    actions=[a.type for a in parsed.actions],
                    action_results=self._last_action_results,
                    heartbeat_interval=self._current_interval,
                    heartbeat_mode=self._heartbeat_mode,
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
        self._messages.append({"role": "user", "content": perception})

        # Trim history if needed
        if len(self._messages) > self._max_history * 2:
            self._messages = self._messages[-self._max_history * 2:]

        # Query model
        response = ollama.chat(
            model=self.config.model,
            messages=self._messages,
        )

        assistant_message = response["message"]["content"]

        # Add response to history
        self._messages.append({"role": "assistant", "content": assistant_message})

        return assistant_message

    # ANSI color codes and emojis for psyche components
    _COMPONENT_STYLE = {
        "shadow": ("\033[31m", "🌑"),    # Red
        "anima": ("\033[36m", "✨"),      # Cyan
        "persona": ("\033[33m", "🎭"),   # Yellow
        "self": ("\033[35m", "☀️"),       # Magenta
        "default": ("\033[37m", "💭"),   # White
    }
    _RESET = "\033[0m"
    _DIM = "\033[2m"
    _CYAN = "\033[36m"
    _GREEN = "\033[32m"
    _YELLOW = "\033[33m"

    def _log_stream(self, segments: list[StreamSegment]) -> None:
        """Log the psyche's stream to console with timestamped, colored component labels."""
        print()  # Blank line before stream

        for segment in segments:
            timestamp = datetime.now().strftime("%H:%M:%S")
            color, emoji = self._COMPONENT_STYLE.get(segment.component, self._COMPONENT_STYLE["default"])
            label = segment.component.upper()

            print(f"[{timestamp}] {color}{emoji} {label}{self._RESET}: {segment.text}")

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

    response = ollama.chat(
        model=config.model,
        messages=[{"role": "user", "content": perception}],
    )

    return response["message"]["content"]
