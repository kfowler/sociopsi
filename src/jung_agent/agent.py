"""The main agent loop."""

import signal
import sys
import threading
import time
from datetime import datetime

import ollama

from jung_agent.actions.executor import ActionExecutor
from jung_agent.config import AgentConfig
from jung_agent.parser import parse_response
from jung_agent.perception import format_perception
from jung_agent.sensors.events import EventCollector
from jung_agent.sensors.somatic import gather_somatic
from jung_agent.types import ActionResult, SomaticState
from jung_agent.voice import Voice


class JungAgent:
    """The Jungian psyche agent."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()
        self.executor = ActionExecutor(self.config)
        self.event_collector = EventCollector()
        self.voice = Voice(self.config)

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
            mode = "sequential" if self.config.voice_sequential else "concurrent"
            print(f"Voice mode: {mode} @ {self.config.voice_rate} wpm")
            print(f"  Anima: {self.config.voice_anima}")
            print(f"  Shadow: {self.config.voice_shadow}")
            print(f"  Persona: {self.config.voice_persona}")
            print(f"  Actions: {self.config.voice_actions} @ {self.config.voice_actions_rate} wpm")
        else:
            print("Voice: disabled")
        print(f"Initial heartbeat: {self._current_interval}s")
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

    def _run_loop(self) -> None:
        """Main agent loop."""
        while self._running:
            loop_start = time.time()

            try:
                # 1. Gather somatic state
                somatic = gather_somatic()

                # 2. Collect events
                events = self.event_collector.collect_events(somatic)

                # 3. Format perception
                perception = format_perception(
                    config=self.config,
                    somatic=somatic,
                    events=events,
                    action_results=self._last_action_results,
                    heartbeat_interval=self._current_interval,
                    heartbeat_mode=self._heartbeat_mode,
                )

                # 4. Send to psyche
                response = self._query_psyche(perception)

                # 5. Parse response
                parsed = parse_response(response)

                # 6. Log and speak stream
                if self.config.log_stream:
                    self._log_stream(parsed.stream)

                # Speak the internal monologue
                self.voice.speak_stream(parsed.stream)

                # 7. Announce and execute actions
                if parsed.actions:
                    self.voice.announce_actions(parsed.actions)

                self._last_action_results = self.executor.execute_all(parsed.actions)

                # Log action results
                for result in self._last_action_results:
                    status = "OK" if result.success else "FAILED"
                    print(f"  [{status}] {result.action_type}")

                # 8. Check for heartbeat override
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

    def _log_stream(self, stream: str) -> None:
        """Log the psyche's stream to console."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] STREAM:")
        print("-" * 40)

        # Wrap and indent stream text
        for line in stream.split("\n"):
            if line.strip():
                print(f"  {line}")

        print("-" * 40)

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
