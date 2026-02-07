"""Continuous speech recognition for the agent.

Thin wrapper around the platform speech backend that buffers recognized
utterances for the agent's perception loop. The actual STT implementation
is delegated to platform.speech (Darwin: SFSpeechRecognizer, Linux: vosk).
"""

from __future__ import annotations

import logging
import sys
import threading
from collections import deque
from typing import TYPE_CHECKING

from sociopsi.config import AgentConfig
from sociopsi.event_bus import get_event_bus
from sociopsi.platform import SpeechBackend, get_speech_backend
from sociopsi.terminal import colors

if TYPE_CHECKING:
    from sociopsi.ux.base import UXRenderer

logger = logging.getLogger(__name__)

# Maximum number of buffered utterances before oldest are dropped
MAX_UTTERANCES = 10


class Ear:
    """Continuous speech recognition for the agent.

    Uses the platform speech backend to stream microphone audio through
    speech recognition. Recognized utterances are buffered and drained
    by the agent each perception cycle.
    """

    def __init__(
        self,
        config: AgentConfig,
        renderer: UXRenderer | None = None,
    ) -> None:
        self.config = config
        self._enabled = bool(config.ear_enabled)
        self._locale = config.ear_locale
        self._on_device = config.ear_on_device
        self._renderer = renderer

        # Thread-safe utterance buffer
        self._utterances: deque[str] = deque(maxlen=MAX_UTTERANCES)
        self._utterances_lock = threading.Lock()

        # Current partial transcription (for logging only)
        self._partial: str = ""

        # Running state
        self._running = False
        self._running_lock = threading.Lock()

        # Platform speech backend (initialized in start())
        self._backend: SpeechBackend | None = None

        # Event bus for publishing speech events
        self._event_bus = get_event_bus()

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self.config.ear_enabled)

    def start(self) -> None:
        """Begin continuous speech recognition.

        Creates the platform speech backend and starts listening.
        No-op if ear is disabled or backend is unavailable.
        """
        if not self.enabled:
            logger.debug("Ear.start() skipped: ear is disabled")
            return

        with self._running_lock:
            if self._running:
                logger.debug("Ear.start() skipped: already running")
                return

        logger.debug("Ear starting up...")

        try:
            backend = get_speech_backend(
                locale=self._locale,
                on_device=self._on_device,
            )
        except Exception as e:
            logger.error(f"No speech backend available: {e}")
            self._enabled = False
            return

        if not backend.is_available():
            logger.warning("Speech recognition not available on this platform. Ear disabled.")
            self._enabled = False
            return

        self._backend = backend
        backend.start_listening(self._on_speech)

        with self._running_lock:
            self._running = True

        logger.info(f"Ear started (locale={self._locale}, on_device={self._on_device})")

    def stop(self) -> None:
        """Stop speech recognition and release resources."""
        with self._running_lock:
            if not self._running:
                logger.debug("Ear.stop() skipped: not running")
                return
            self._running = False

        logger.debug("Ear shutting down...")

        if self._backend is not None:
            self._backend.stop_listening()
            self._backend = None

        with self._utterances_lock:
            dropped = len(self._utterances)
            self._utterances.clear()
        if dropped:
            logger.debug(f"Dropped {dropped} unread utterance(s) from buffer")

        logger.info("Ear stopped")

    def get_utterances(self) -> list[str]:
        """Drain and return all buffered utterances.

        Returns:
            List of recognized utterance strings (may be empty).
        """
        with self._utterances_lock:
            result = list(self._utterances)
            self._utterances.clear()
        if result:
            logger.debug(f"Drained {len(result)} utterance(s) from buffer")
        return result

    @property
    def partial(self) -> str:
        """Current partial (in-progress) transcription."""
        return self._partial

    def mute(self) -> None:
        """Suppress audio forwarding (e.g. while the agent is speaking)."""
        if self._backend is not None:
            self._backend.mute()
        self._partial = ""
        logger.debug("Ear muted")

    def unmute(self) -> None:
        """Resume audio forwarding after mute."""
        if self._backend is not None:
            self._backend.unmute()
        logger.debug("Ear unmuted")

    def _on_speech(self, text: str, is_final: bool) -> None:
        """Callback from platform speech backend.

        Args:
            text: Recognized text (partial or final).
            is_final: True if this is a complete utterance.
        """
        if is_final:
            text = text.strip()
            if text:
                with self._utterances_lock:
                    self._utterances.append(text)
                self._partial = ""

                # Render final transcription
                if self._renderer is not None:
                    self._renderer.render_speech(text, is_final=True)
                else:
                    sys.stdout.write(f'\r\033[K{colors.GREEN}[SPEECH]{colors.RESET} "{text}"\n')
                    sys.stdout.flush()

                # Publish on event bus
                self._event_bus.publish(
                    "perception.speech",
                    {"text": text, "is_final": True},
                )

                logger.info(f"Speech recognized: {text}")
        else:
            # Partial result - overwrite current line in-place
            self._partial = text
            if self._renderer is not None:
                self._renderer.render_speech(text, is_final=False)
            else:
                sys.stdout.write(
                    f"\r\033[K{colors.DIM}[HEARING]{colors.RESET} {colors.DIM}{text}{colors.RESET}"
                )
                sys.stdout.flush()
