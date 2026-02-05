"""Voice output for the psyche."""

import logging
import re
import threading
from queue import Queue
from typing import TypeAlias

from jung_agent.config import AgentConfig
from jung_agent.types import Action, ActionResult, PsycheComponent, StreamSegment

logger = logging.getLogger(__name__)

# Type alias for voice queue items: (text, voice, rate) or None for shutdown
VoiceQueueItem: TypeAlias = tuple[str, str, int] | None

# Module-level voice instance for global access
_voice_instance: "Voice | None" = None


def get_voice() -> "Voice | None":
    """Get the global voice instance if available."""
    return _voice_instance


def queue_speech(text: str, voice: str | None = None, rate: int = 200) -> bool:
    """Queue text for speech via the global voice instance.

    Args:
        text: Text to speak
        voice: Voice name (uses default if None)
        rate: Words per minute

    Returns:
        True if queued, False if no voice instance available.
    """
    if _voice_instance and _voice_instance.config.voice_enabled:
        voice_name = voice or _voice_instance.config.voice_default
        _voice_instance._queue.put((text, voice_name, rate))
        return True
    return False


class _SpeechDelegate:
    """Delegate for AVSpeechSynthesizer completion callbacks."""

    def __init__(self) -> None:
        self.done_event = threading.Event()

    def speechSynthesizer_didFinishSpeechUtterance_(self, synth: object, utt: object) -> None:
        self.done_event.set()

    def speechSynthesizer_didCancelSpeechUtterance_(self, synth: object, utt: object) -> None:
        self.done_event.set()


class Voice:
    """Text-to-speech voice for the psyche."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._queue: Queue[VoiceQueueItem] = Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._running_lock = threading.Lock()
        self._current_synthesizer: object | None = None
        self._synth_lock = threading.Lock()

        # Map component names to voice config
        self._component_voices: dict[PsycheComponent, str] = {
            "anima": config.voice_anima,
            "shadow": config.voice_shadow,
            "persona": config.voice_persona,
            "self": config.voice_self,
            "default": config.voice_default,
        }

    def start(self) -> None:
        """Start the voice thread."""
        global _voice_instance

        if not self.config.voice_enabled:
            return

        with self._running_lock:
            if self._running:
                return  # Already running
            self._running = True

        _voice_instance = self
        self._thread = threading.Thread(target=self._voice_worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the voice thread."""
        global _voice_instance

        with self._running_lock:
            if not self._running:
                return  # Already stopped
            self._running = False

        _voice_instance = None

        # Stop any current speech
        with self._synth_lock:
            if self._current_synthesizer:
                try:
                    self._current_synthesizer.stopSpeakingAtBoundary_(0)  # type: ignore[attr-defined]
                except Exception:
                    pass

        self._queue.put(None)  # Unblock the worker

        if self._thread:
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                logger.warning("Voice thread did not stop within timeout")

    def _is_running(self) -> bool:
        """Thread-safe check of running state."""
        with self._running_lock:
            return self._running

    def speak_stream(self, segments: list[StreamSegment]) -> None:
        """Speak the internal monologue with component-specific voices."""
        if not self.config.voice_enabled:
            return

        for segment in segments:
            text = self._clean_for_speech(segment.text)
            if text:
                voice = self._component_voices.get(segment.component, self.config.voice_default)
                self._queue.put((text, voice, self.config.voice_rate))

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
            self._queue.put(
                (
                    text,
                    self.config.voice_actions,
                    self.config.voice_actions_rate,
                )
            )

    def speak_perceptions(self, results: list[ActionResult]) -> None:
        """Speak what was seen, heard, or learned from perception/learning actions."""
        if not self.config.voice_enabled:
            return

        for result in results:
            if not result.success:
                continue

            text = None
            voice = self.config.voice_anima  # Default for perceptions
            rate = self.config.voice_rate

            # Vision actions - say what was seen
            if result.action_type in ("look", "look_for", "describe_image"):
                if isinstance(result.result, dict):
                    desc = result.result.get("description", "")
                    if desc and "no vision model" not in desc.lower():
                        text = f"I see: {desc}"

            # Auditory actions - say what was heard
            elif result.action_type in ("listen", "listen_for", "transcribe"):
                if isinstance(result.result, dict):
                    transcription = result.result.get("transcription")
                    if transcription:
                        text = f"I hear: {transcription}"
                    else:
                        audio_desc = result.result.get("description", "")
                        if audio_desc and "install" not in audio_desc.lower():
                            text = f"I hear: {audio_desc}"

            # Web search - summarize results (male voice)
            elif result.action_type == "web_search":
                if isinstance(result.result, dict):
                    results_list = result.result.get("results", [])
                    query = result.result.get("query", "")
                    if results_list:
                        titles = [r.get("title", "") for r in results_list[:3]]
                        summary = f"I searched for {query}. Found: {', '.join(titles)}"
                        text = summary
                        voice = self.config.voice_actions  # Male voice (Evan)
                        rate = self.config.voice_actions_rate

            # Web read - summarize content (male voice)
            elif result.action_type == "web_read":
                if isinstance(result.result, dict):
                    title = result.result.get("title", "")
                    content = result.result.get("content", "")
                    if title and content:
                        # Get first ~100 chars as summary
                        preview = content[:150].strip()
                        if len(content) > 150:
                            preview += "..."
                        text = f"I read {title}. It says: {preview}"
                        voice = self.config.voice_actions  # Male voice (Evan)
                        rate = self.config.voice_actions_rate

            if text:
                self._queue.put(
                    (
                        self._clean_for_speech(text),
                        voice,
                        rate,
                    )
                )

    def _clean_for_speech(self, text: str) -> str:
        """Clean text for natural speech."""
        # Remove markdown-style formatting
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)  # *emphasis*
        text = re.sub(r"_+([^_]+)_+", r"\1", text)  # _emphasis_

        # Convert dashes/ellipses to pauses
        text = re.sub(r"—+", ", ", text)  # em-dash
        text = re.sub(r"\.\.\.+", "...", text)  # normalize ellipses

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        # Don't speak if too short
        if len(text) < 5:
            return ""

        return text

    def _action_to_speech(self, action: Action) -> str | None:
        """Convert an action to a spoken announcement."""
        action_announcements = {
            # Self-regulation
            "set_brightness": lambda p: f"adjust brightness to {p.get('level', 'unknown')} percent",
            "set_volume": lambda p: f"set volume to {p.get('level', 'unknown')} percent",
            "set_power_mode": lambda p: f"switch to {p.get('mode', 'unknown')} power",
            "sleep": lambda p: "sleep",
            "wake_display": lambda p: "wake the display",
            "set_heartbeat": lambda p: f"set rhythm to {p.get('interval', 'unknown')} seconds",
            # Perception
            "check_battery": lambda p: "check battery",
            "check_thermals": lambda p: "check temperature",
            "check_memory": lambda p: "check memory",
            "check_network": lambda p: "check network",
            "check_processes": lambda p: "check processes",
            "sense_presence": lambda p: "sense who is nearby",
            "sense_network": lambda p: "scan local network",
            "sense_io": lambda p: "check connections",
            "sense_disks": lambda p: "check storage",
            "sense_displays": lambda p: "check displays",
            "look": lambda p: "look",
            "listen": lambda p: "listen",
            # Learning
            "web_search": lambda p: f"search for {p.get('query', 'something')}",
            "web_read": lambda p: "read a webpage",
            # Communication - don't announce speak (redundant)
            "notify": lambda p: f"notify: {p.get('message', '')[:30]}",
            "play_sound": lambda p: f"play {p.get('sound', 'a sound')}",
            # Environment
            "open_app": lambda p: f"open {p.get('name', 'an app')}",
            "close_app": lambda p: f"close {p.get('name', 'an app')}",
            # Memory
            "journal_write": lambda p: f"journal: {p.get('entry', '')}",
            "journal_read": lambda p: "read journal",
            "store_memory": lambda p: f"remember {p.get('key', 'something')}",
            "recall_memory": lambda p: f"recall {p.get('key', 'something')}",
        }

        if action.type in ("speak", "display_message"):
            return None  # Already verbal

        formatter = action_announcements.get(action.type)
        if formatter:
            return formatter(action.params)

        return None

    def _voice_worker(self) -> None:
        """Background worker that speaks queued text using AVFoundation."""
        try:
            import AVFoundation  # type: ignore[import-untyped]
        except ImportError as e:
            logger.error(f"AVFoundation import failed: {e}")
            return

        # Cache voice lookups
        voice_cache: dict[str, object] = {}

        while self._is_running():
            try:
                item = self._queue.get(timeout=1.0)
            except Exception:
                # Queue.get timeout - check if we should continue
                continue

            if item is None or not self._is_running():
                break

            text, voice_name, rate_wpm = item
            if not text:
                continue

            try:
                # Get or lookup voice
                if voice_name not in voice_cache:
                    voice_cache[voice_name] = self._get_voice_by_name(voice_name)

                av_voice = voice_cache[voice_name]

                # Convert WPM to AVSpeechSynthesizer rate (0.0-1.0)
                # ~90 WPM = 0.0, ~300 WPM = 1.0
                av_rate = max(0.0, min(1.0, (rate_wpm - 90) / 420))

                # Create utterance (PyObjC lacks type stubs)
                utterance = AVFoundation.AVSpeechUtterance.speechUtteranceWithString_(text)  # type: ignore[attr-defined]
                utterance.setRate_(av_rate)
                utterance.setPitchMultiplier_(1.0)
                utterance.setVolume_(1.0)

                if av_voice:
                    utterance.setVoice_(av_voice)

                # Speak synchronously using event
                synthesizer = AVFoundation.AVSpeechSynthesizer.alloc().init()  # type: ignore[attr-defined]
                delegate = _SpeechDelegate()
                synthesizer.setDelegate_(delegate)

                # Store synthesizer so stop() can interrupt it
                with self._synth_lock:
                    self._current_synthesizer = synthesizer

                synthesizer.speakUtterance_(utterance)

                # Wait for completion with periodic running check
                while not delegate.done_event.wait(timeout=0.5):
                    if not self._is_running():
                        synthesizer.stopSpeakingAtBoundary_(0)
                        break

                with self._synth_lock:
                    self._current_synthesizer = None

            except Exception as e:
                logger.error(f"Voice synthesis error: {e}")
                # Continue with next item

        logger.debug("Voice worker thread exiting")

    def _get_voice_by_name(self, voice_name: str) -> object | None:
        """Get AVSpeechSynthesisVoice by display name."""
        import AVFoundation  # type: ignore[import-untyped]

        voices = AVFoundation.AVSpeechSynthesisVoice.speechVoices()  # type: ignore[attr-defined]
        for v in voices:
            if v.name() == voice_name:
                return v

        # Fallback: find any premium English voice
        for v in voices:
            if v.language().startswith("en") and v.quality() >= 3:
                return v

        return None
