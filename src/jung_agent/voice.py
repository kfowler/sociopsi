"""Voice output for the psyche."""

import re
import subprocess
import threading
from queue import Queue

from jung_agent.config import AgentConfig
from jung_agent.types import Action


class Voice:
    """Text-to-speech voice for the psyche."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._queue: Queue[str] = Queue()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """Start the voice thread."""
        if not self.config.voice_enabled:
            return

        self._running = True
        self._thread = threading.Thread(target=self._voice_worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the voice thread."""
        self._running = False
        self._queue.put("")  # Unblock the worker
        if self._thread:
            self._thread.join(timeout=1.0)

    def speak_stream(self, stream: str) -> None:
        """Speak the internal monologue stream."""
        if not self.config.voice_enabled:
            return

        # Clean up the stream for speech
        text = self._clean_for_speech(stream)
        if text:
            self._queue.put(text)

    def announce_actions(self, actions: list[Action]) -> None:
        """Announce intended actions before executing them."""
        if not self.config.voice_enabled or not actions:
            return

        announcements = []
        for action in actions:
            announcement = self._action_to_speech(action)
            if announcement:
                announcements.append(announcement)

        if announcements:
            text = "I will " + ", and ".join(announcements) + "."
            self._queue.put(text)

    def _clean_for_speech(self, text: str) -> str:
        """Clean text for natural speech."""
        # Remove markdown-style formatting
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)  # *emphasis*
        text = re.sub(r"_+([^_]+)_+", r"\1", text)  # _emphasis_

        # Convert dashes/ellipses to pauses
        text = re.sub(r"—+", ", ", text)  # em-dash
        text = re.sub(r"\.\.\.+", "...", text)  # normalize ellipses

        # Remove component labels if in structured mode
        text = re.sub(r"\[(SHADOW|ANIMA|PERSONA|SELF)\]", "", text, flags=re.IGNORECASE)

        # Clean up multiple spaces/newlines
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        # Don't speak if too short
        if len(text) < 10:
            return ""

        return text

    def _action_to_speech(self, action: Action) -> str | None:
        """Convert an action to a spoken announcement."""
        action_announcements = {
            # Self-regulation
            "set_brightness": lambda p: f"adjust the brightness to {p.get('level', 'unknown')} percent",
            "set_volume": lambda p: f"set the volume to {p.get('level', 'unknown')} percent",
            "set_power_mode": lambda p: f"switch to {p.get('mode', 'unknown')} power mode",
            "sleep": lambda p: "go to sleep",
            "wake_display": lambda p: "wake the display",
            "set_heartbeat": lambda p: f"set my rhythm to {p.get('interval', 'unknown')} seconds",
            # Perception
            "check_battery": lambda p: "check my battery",
            "check_thermals": lambda p: "check my temperature",
            "check_memory": lambda p: "check my memory",
            "check_network": lambda p: "check my connection",
            "check_processes": lambda p: "see what consumes me",
            "sense_presence": lambda p: "sense who is nearby",
            "sense_network": lambda p: "scan the local network",
            "look": lambda p: "look with my camera",
            "listen": lambda p: "listen with my microphone",
            "sense_light": lambda p: "sense the light",
            # Communication - don't announce speak actions (would be redundant)
            "notify": lambda p: f"send a notification: {p.get('message', '')[:30]}",
            "play_sound": lambda p: f"play a {p.get('sound', 'sound')}",
            # Environment
            "open_app": lambda p: f"open {p.get('name', 'an application')}",
            "close_app": lambda p: f"close {p.get('name', 'an application')}",
            "connect_network": lambda p: "connect to the network",
            "disconnect_network": lambda p: "disconnect from the network",
            # Memory
            "journal_write": lambda p: "write in my journal",
            "journal_read": lambda p: "read my journal",
            "store_memory": lambda p: f"remember {p.get('key', 'something')}",
            "recall_memory": lambda p: f"recall {p.get('key', 'something')}",
        }

        # Skip certain actions from announcement
        skip_actions = {"speak", "display_message"}  # Already verbal
        if action.type in skip_actions:
            return None

        formatter = action_announcements.get(action.type)
        if formatter:
            return formatter(action.params)

        return None

    def _voice_worker(self) -> None:
        """Background worker that speaks queued text."""
        while self._running:
            text = self._queue.get()
            if not text or not self._running:
                continue

            try:
                # Use macOS say command with the configured voice
                cmd = [
                    "say",
                    "-v", self.config.voice_name,
                    "-r", str(self.config.voice_rate),
                    text,
                ]
                subprocess.run(cmd, capture_output=True, timeout=60)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
