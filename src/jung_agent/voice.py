"""Voice output for the psyche."""

import re
import subprocess
import threading
from dataclasses import dataclass
from queue import Queue

from jung_agent.config import AgentConfig
from jung_agent.types import Action


@dataclass
class VoiceSegment:
    """A segment of text attributed to a psyche component."""

    text: str
    component: str  # "anima", "shadow", "persona", "self", or "default"


class Voice:
    """Text-to-speech voice for the psyche."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._queue: Queue[tuple[str, str, int] | None] = Queue()
        self._thread: threading.Thread | None = None
        self._running = False

        # Map component names to voice config
        self._component_voices = {
            "anima": config.voice_anima,
            "shadow": config.voice_shadow,
            "persona": config.voice_persona,
            "self": config.voice_self,
            "default": config.voice_default,
        }

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
        self._queue.put(None)  # Unblock the worker
        if self._thread:
            self._thread.join(timeout=1.0)

    def speak_stream(self, stream: str) -> None:
        """Speak the internal monologue stream with component-specific voices."""
        if not self.config.voice_enabled:
            return

        # Parse stream into component segments
        segments = self._parse_components(stream)

        if self.config.voice_sequential:
            # Speak one at a time (queued)
            for segment in segments:
                text = self._clean_for_speech(segment.text)
                if text:
                    voice = self._component_voices.get(segment.component, self.config.voice_default)
                    self._queue.put((text, voice, self.config.voice_rate))
        else:
            # Speak all together (concurrent) - use separate processes
            self._speak_concurrent(segments)

    def announce_actions(self, actions: list[Action]) -> None:
        """Announce intended actions (actions voice, deliberate)."""
        if not self.config.voice_enabled or not actions:
            return

        announcements = []
        for action in actions:
            announcement = self._action_to_speech(action)
            if announcement:
                announcements.append(announcement)

        if announcements:
            text = "I will " + ", and ".join(announcements) + "."
            self._queue.put((
                text,
                self.config.voice_actions,
                self.config.voice_actions_rate,
            ))

    def _parse_components(self, stream: str) -> list[VoiceSegment]:
        """Parse stream into segments by psyche component."""
        segments: list[VoiceSegment] = []

        # Pattern to find component labels: [SHADOW], [ANIMA], [PERSONA], [SELF]
        pattern = r"\[(SHADOW|ANIMA|ANIMUS|PERSONA|SELF)\]"

        # Split by component labels, keeping the labels
        parts = re.split(f"({pattern})", stream, flags=re.IGNORECASE)

        current_component = "default"
        current_text = ""

        for part in parts:
            if not part:
                continue

            # Check if this part is a component label
            match = re.match(pattern, part, re.IGNORECASE)
            if match:
                # Save previous segment if any
                if current_text.strip():
                    segments.append(VoiceSegment(text=current_text.strip(), component=current_component))
                    current_text = ""

                # Set new component
                label = match.group(1).lower()
                if label in ("anima", "animus"):
                    current_component = "anima"
                else:
                    current_component = label
            else:
                current_text += part

        # Don't forget the last segment
        if current_text.strip():
            segments.append(VoiceSegment(text=current_text.strip(), component=current_component))

        return segments

    def _speak_concurrent(self, segments: list[VoiceSegment]) -> None:
        """Speak all segments concurrently (overlapping voices)."""
        processes: list[subprocess.Popen[bytes]] = []

        for segment in segments:
            text = self._clean_for_speech(segment.text)
            if not text:
                continue

            voice = self._component_voices.get(segment.component, self.config.voice_default)

            try:
                # Start speech process without waiting
                proc = subprocess.Popen(
                    ["say", "-v", voice, "-r", str(self.config.voice_rate), text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                processes.append(proc)
            except FileNotFoundError:
                pass

        # Wait for all to finish
        for proc in processes:
            try:
                proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _clean_for_speech(self, text: str) -> str:
        """Clean text for natural speech."""
        # Remove markdown-style formatting
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)  # *emphasis*
        text = re.sub(r"_+([^_]+)_+", r"\1", text)  # _emphasis_

        # Convert dashes/ellipses to pauses
        text = re.sub(r"—+", ", ", text)  # em-dash
        text = re.sub(r"\.\.\.+", "...", text)  # normalize ellipses

        # Remove component labels (they're not meant to be spoken)
        text = re.sub(r"\[(SHADOW|ANIMA|ANIMUS|PERSONA|SELF)\]", "", text, flags=re.IGNORECASE)

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
            # Learning
            "web_search": lambda p: f"search the web for {p.get('query', 'something')}",
            "web_read": lambda p: "read a webpage",
            "describe_image": lambda p: "describe what I see",
            "transcribe_audio": lambda p: "transcribe what I hear",
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
            item = self._queue.get()
            if item is None or not self._running:
                continue

            text, voice, rate = item
            if not text:
                continue

            try:
                # Use macOS say command with the specified voice and rate
                cmd = [
                    "say",
                    "-v", voice,
                    "-r", str(rate),
                    text,
                ]
                subprocess.run(cmd, capture_output=True, timeout=120)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
