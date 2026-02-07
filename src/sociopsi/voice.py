"""
Voice output for the psyche.

Uses the platform audio backend for TTS with a queue to manage
speech ordering across multiple psyche component voices.
"""

import logging
import re
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event

from sociopsi.config import AgentConfig
from sociopsi.platform import get_audio_backend
from sociopsi.platform.base import AudioBackend
from sociopsi.types import Action, ActionResult, PsycheComponent, StreamSegment

logger = logging.getLogger(__name__)

# ----------------------------
# Singleton access (thread-safe)
# ----------------------------

_voice_instance: Voice | None = None
_voice_instance_lock = threading.Lock()


def get_voice() -> Voice | None:
    """Get the global voice instance if available."""
    with _voice_instance_lock:
        return _voice_instance


def queue_speech(text: str, voice: str | None = None, rate: int = 200) -> bool:
    """Queue text for speech via the global voice instance."""
    with _voice_instance_lock:
        v = _voice_instance
    if not v or not v.enabled:
        logger.debug("No voice instance (or disabled); not queued.")
        return False
    return v.enqueue(text=text, voice=voice, rate=rate)


# ----------------------------
# Internal types
# ----------------------------


@dataclass(frozen=True)
class SpeechItem:
    text: str
    voice_name: str
    rate_wpm: int


# ----------------------------
# Voice
# ----------------------------


class Voice:
    """Text-to-speech voice for the psyche.

    Uses the platform audio backend with a bounded queue for
    speech ordering across multiple component voices.
    """

    MAX_QUEUE_SIZE = 50

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._enabled = bool(config.voice_enabled)
        self._running = False
        self._running_lock = threading.Lock()

        # Speech queue
        self._queue: deque[SpeechItem] = deque()
        self._queue_lock = threading.Lock()
        self._finished_event = Event()
        self._finished_event.set()  # Start as "not speaking"

        # Platform audio backend
        self._audio: AudioBackend | None = None

        # Worker thread for draining queue
        self._worker_thread: threading.Thread | None = None
        self._stop_event = Event()

        # Callbacks for speaking state changes (used to mute/unmute ear)
        self._on_speak_start: Callable[[], None] | None = None
        self._on_speak_end: Callable[[], None] | None = None

        # Voice mapping for components
        self._component_voices: dict[PsycheComponent, str] = {
            "anima": config.voice_anima,
            "shadow": config.voice_shadow,
            "persona": config.voice_persona,
            "self": config.voice_self,
            "default": config.voice_default,
        }

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self.config.voice_enabled)

    def start(self) -> None:
        """Start the voice system and register singleton."""
        global _voice_instance

        if not self.enabled:
            return

        with self._running_lock:
            if self._running:
                return
            self._running = True

        # Initialize platform audio backend
        try:
            self._audio = get_audio_backend()
        except Exception:
            logger.error("No audio backend available for this platform")
            self._running = False
            return

        # Verify configured voices are available
        self._validate_voices()

        # Start worker thread
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._drain_queue, name="voice-worker", daemon=True
        )
        self._worker_thread.start()

        with _voice_instance_lock:
            _voice_instance = self

        logger.info("Voice system started with platform audio backend")

    def stop(self, wait_for_completion: bool = False) -> None:
        """Stop the voice system."""
        global _voice_instance

        if wait_for_completion:
            self._finished_event.wait(timeout=30.0)

        with self._running_lock:
            if not self._running:
                return
            self._running = False

        self._stop_event.set()

        with self._queue_lock:
            self._queue.clear()

        self._finished_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        with _voice_instance_lock:
            if _voice_instance is self:
                _voice_instance = None

        logger.info("Voice system stopped")

    def _validate_voices(self) -> None:
        """Log which configured voices are available."""
        if not self._audio:
            return
        voices_to_check = {
            self.config.voice_anima,
            self.config.voice_shadow,
            self.config.voice_persona,
            self.config.voice_self,
            self.config.voice_default,
            self.config.voice_actions,
        }
        for voice_name in voices_to_check:
            if self._audio.voice_available(voice_name):
                logger.debug(f"Voice available: {voice_name}")
            else:
                logger.debug(f"Voice not found: {voice_name}")

    def _drain_queue(self) -> None:
        """Worker thread: drain speech queue sequentially."""
        while not self._stop_event.is_set():
            item: SpeechItem | None = None

            with self._queue_lock:
                if self._queue:
                    item = self._queue.popleft()
                else:
                    self._finished_event.set()

            if item is None:
                # Wait briefly before checking again
                self._stop_event.wait(timeout=0.05)
                continue

            # Notify speaking start (mute ear)
            if self._on_speak_start is not None:
                try:
                    self._on_speak_start()
                except Exception:
                    pass

            # Speak using platform backend (blocking)
            try:
                if self._audio:
                    self._audio.speak(item.text, voice=item.voice_name, rate=item.rate_wpm)
            except Exception:
                logger.debug(f"Speech failed for: {item.text[:40]}...")

            # Check if queue is empty after this item
            with self._queue_lock:
                if not self._queue:
                    self._finished_event.set()
                    # Notify speaking end (unmute ear)
                    if self._on_speak_end is not None:
                        try:
                            self._on_speak_end()
                        except Exception:
                            pass

    def _is_running(self) -> bool:
        with self._running_lock:
            return self._running

    # ----------------------------
    # Enqueue
    # ----------------------------

    def enqueue(self, text: str, voice: str | None = None, rate: int | None = None) -> bool:
        """Enqueue speech with bounded queue (drop oldest if full)."""
        if not self.enabled or not self._is_running():
            return False

        cleaned = self._clean_for_speech(text)
        if not cleaned:
            return False

        voice_name = voice or self.config.voice_default
        rate_wpm = int(rate if rate is not None else self.config.voice_rate)

        item = SpeechItem(text=cleaned, voice_name=voice_name, rate_wpm=rate_wpm)

        with self._queue_lock:
            while len(self._queue) >= self.MAX_QUEUE_SIZE:
                dropped = self._queue.popleft()
                logger.debug(f"Dropped queued speech (full): {dropped.text[:40]}...")
            self._queue.append(item)
            self._finished_event.clear()

        return True

    # ----------------------------
    # Public orchestration APIs
    # ----------------------------

    def speak_stream(self, segments: list[StreamSegment]) -> None:
        """Speak the internal monologue with component-specific voices."""
        if not self.enabled:
            return

        for seg in segments:
            voice = self._component_voices.get(seg.component, self.config.voice_default)
            self.enqueue(seg.text, voice=voice, rate=self.config.voice_rate)

    def announce_actions(self, actions: list[Action]) -> None:
        """Announce intended actions (actions voice, deliberate)."""
        if not self.enabled or not actions:
            return

        parts: list[str] = []
        for action in actions:
            s = self._action_to_speech(action)
            if s:
                parts.append(s)

        if parts:
            text = "I will " + ", and ".join(parts) + "."
            self.enqueue(text, voice=self.config.voice_actions, rate=self.config.voice_actions_rate)

    def speak_perceptions(self, results: list[ActionResult]) -> None:
        """Speak what was perceived/learned."""
        if not self.enabled:
            return

        for result in results:
            if not result.success:
                continue

            text: str | None = None
            voice = self.config.voice_anima
            rate = self.config.voice_rate

            if result.action_type in ("look", "look_for", "describe_image"):
                if isinstance(result.result, dict):
                    desc = result.result.get("description", "")
                    if desc and "no vision model" not in desc.lower():
                        text = f"I see: {desc}"

            elif result.action_type in ("listen", "listen_for", "transcribe"):
                if isinstance(result.result, dict):
                    transcription = result.result.get("transcription")
                    if transcription:
                        text = f"I hear: {transcription}"
                    else:
                        audio_desc = result.result.get("description", "")
                        if audio_desc and "install" not in audio_desc.lower():
                            text = f"I hear: {audio_desc}"

            elif result.action_type == "web_search":
                if isinstance(result.result, dict):
                    results_list = result.result.get("results", [])
                    query = result.result.get("query", "")
                    if results_list:
                        titles = [
                            r.get("title", "") for r in results_list[:3] if isinstance(r, dict)
                        ]
                        if titles:
                            text = f"I searched for {query}. Found: {', '.join(titles)}"
                            voice = self.config.voice_actions
                            rate = self.config.voice_actions_rate

            elif result.action_type == "web_read":
                if isinstance(result.result, dict):
                    title = result.result.get("title", "")
                    content = result.result.get("content", "")
                    if title and content:
                        preview = content[:150].strip()
                        if len(content) > 150:
                            preview += "..."
                        text = f"I read {title}. It says: {preview}"
                        voice = self.config.voice_actions
                        rate = self.config.voice_actions_rate

            if text:
                self.enqueue(text, voice=voice, rate=rate)

    # ----------------------------
    # Text cleaning
    # ----------------------------

    _CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
    _INLINE_CODE_RE = re.compile(r"`([^`]+)`")
    _URL_RE = re.compile(r"https?://\S+")
    _MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def _clean_for_speech(self, text: str) -> str:
        """Clean text for natural speech."""
        if not text:
            return ""

        text = self._CODE_FENCE_RE.sub(" ", text)
        text = self._MD_LINK_RE.sub(r"\1", text)
        text = self._INLINE_CODE_RE.sub(" ", text)
        text = self._URL_RE.sub(" ", text)
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        text = re.sub(r"_+([^_]+)_+", r"\1", text)
        text = re.sub(r"—+", ", ", text)
        text = re.sub(r"\.\.\.+", "...", text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > 800:
            text = text[:800].rstrip() + "..."

        if len(text) < 5:
            return ""

        return text

    # ----------------------------
    # Action announcements
    # ----------------------------

    def _action_to_speech(self, action: Action) -> str | None:
        action_announcements = {
            "set_brightness": lambda p: f"adjust brightness to {p.get('level', 'unknown')} percent",
            "set_volume": lambda p: f"set volume to {p.get('level', 'unknown')} percent",
            "set_power_mode": lambda p: f"switch to {p.get('mode', 'unknown')} power",
            "sleep": lambda p: "sleep",
            "wake_display": lambda p: "wake the display",
            "set_heartbeat": lambda p: f"set rhythm to {p.get('interval', 'unknown')} seconds",
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
            "web_search": lambda p: f"search for {p.get('query', 'something')}",
            "web_read": lambda p: "read a webpage",
            "notify": lambda p: f"notify: {str(p.get('message', ''))[:30]}",
            "play_sound": lambda p: f"play {p.get('sound', 'a sound')}",
            "open_app": lambda p: f"open {p.get('name', 'an app')}",
            "close_app": lambda p: f"close {p.get('name', 'an app')}",
            "journal_write": lambda p: "journal",
            "journal_read": lambda p: "read journal",
            "store_memory": lambda p: f"remember {p.get('key', 'something')}",
            "recall_memory": lambda p: f"recall {p.get('key', 'something')}",
        }

        if action.type in ("speak", "display_message"):
            return None

        formatter = action_announcements.get(action.type)
        if formatter:
            try:
                return formatter(action.params)
            except Exception:
                return None
        return None
