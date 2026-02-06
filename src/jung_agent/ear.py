"""Continuous speech recognition using macOS SFSpeechRecognizer.

Listens to the microphone at all times and delivers recognized
utterances to the agent's perception loop via a thread-safe buffer.
Recognition tasks are seamlessly restarted on timeout (~60s limit).
"""

import logging
import sys
import threading
import time
from collections import deque
from typing import Any, Self

import objc
from AVFoundation import AVAudioEngine
from Foundation import NSLocale, NSObject, NSRunLoop
from Speech import (
    SFSpeechAudioBufferRecognitionRequest,
    SFSpeechRecognizer,
    SFSpeechRecognizerAuthorizationStatusAuthorized,
    SFSpeechRecognizerAuthorizationStatusNotDetermined,
)

from jung_agent.config import AgentConfig
from jung_agent.event_bus import get_event_bus
from jung_agent.terminal import colors

logger = logging.getLogger(__name__)

# Maximum number of buffered utterances before oldest are dropped
MAX_UTTERANCES = 10

# If this many consecutive errors occur within this window, disable the ear
MAX_CONSECUTIVE_ERRORS = 3
ERROR_WINDOW_SECONDS = 5.0

# Error codes that are expected and should not count toward the fatal threshold
# 203 = no speech detected (normal timeout)
# 216 = recognition task was cancelled
# 1110 = request was cancelled
BENIGN_ERROR_CODES = frozenset({203, 216, 1110})


# ----------------------------
# PyObjC Delegate
# ----------------------------


class SpeechRecognitionDelegate(NSObject):
    """Delegate for SFSpeechRecognizer availability changes."""

    def init(self) -> Self:
        self = objc.super(SpeechRecognitionDelegate, self).init()
        if self is None:
            return None  # type: ignore[return-value]
        self._available: bool = False
        return self

    def speechRecognizer_availabilityDidChange_(  # noqa: N802
        self,
        _speech_recognizer: Any,
        available: bool,
    ) -> None:
        """Called when recognizer availability changes."""
        self._available = available
        if not available:
            logger.warning("Speech recognizer became unavailable")
        else:
            logger.info("Speech recognizer is available")


# ----------------------------
# Ear
# ----------------------------


class Ear:
    """Continuous speech recognition for the agent.

    Uses SFSpeechRecognizer via PyObjC to stream microphone audio
    through Apple's on-device speech recognition. Recognized utterances
    are buffered and drained by the agent each perception cycle.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._enabled = bool(config.ear_enabled)
        self._locale = config.ear_locale
        self._on_device = config.ear_on_device

        # Thread-safe utterance buffer
        self._utterances: deque[str] = deque(maxlen=MAX_UTTERANCES)
        self._utterances_lock = threading.Lock()

        # Current partial transcription (for logging only)
        self._partial: str = ""

        # Running state
        self._running = False
        self._running_lock = threading.Lock()

        # Apple framework objects (initialized in start())
        self._audio_engine: AVAudioEngine | None = None
        self._recognizer: SFSpeechRecognizer | None = None
        self._delegate: SpeechRecognitionDelegate | None = None
        self._request: SFSpeechAudioBufferRecognitionRequest | None = None
        self._recognition_task: Any | None = None  # SFSpeechRecognitionTask

        # Mute flag - suppresses audio forwarding while voice is speaking
        self._muted = False

        # Consecutive error tracking for fatal error detection
        self._consecutive_errors: int = 0
        self._last_error_time: float = 0.0

        # Event bus for publishing speech events
        self._event_bus = get_event_bus()

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self.config.ear_enabled)

    def start(self) -> None:
        """Begin continuous speech recognition.

        Requests authorization, sets up the audio engine, and starts
        the first recognition task. No-op if ear is disabled or
        authorization is denied.
        """
        if not self.enabled:
            logger.debug("Ear.start() skipped: ear is disabled")
            return

        with self._running_lock:
            if self._running:
                logger.debug("Ear.start() skipped: already running")
                return

        logger.debug("Ear starting up...")

        # Check authorization
        auth_status = SFSpeechRecognizer.authorizationStatus()
        logger.debug(f"Current speech recognition authorization status: {auth_status}")
        if auth_status == SFSpeechRecognizerAuthorizationStatusNotDetermined:
            # Request authorization (blocking - waits for user response)
            logger.info("Requesting speech recognition authorization from user...")
            self._request_authorization()
            auth_status = SFSpeechRecognizer.authorizationStatus()
            logger.debug(f"Authorization status after request: {auth_status}")

        if auth_status != SFSpeechRecognizerAuthorizationStatusAuthorized:
            logger.warning(
                f"Speech recognition not authorized (status={auth_status}). Ear will be disabled."
            )
            self._enabled = False
            return

        # Set up recognizer
        logger.debug(f"Creating SFSpeechRecognizer for locale '{self._locale}'")
        locale = NSLocale.alloc().initWithLocaleIdentifier_(self._locale)
        self._recognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale)
        if self._recognizer is None:
            logger.error(f"Failed to create speech recognizer for locale {self._locale}")
            self._enabled = False
            return

        if self._on_device and self._recognizer.supportsOnDeviceRecognition():
            logger.info("Using on-device speech recognition")
        elif self._on_device:
            logger.warning("On-device recognition not supported, falling back to server")

        # Set up delegate
        logger.debug("Creating speech recognition delegate")
        delegate = SpeechRecognitionDelegate.alloc().init()
        if delegate is None:
            logger.error("Failed to create speech recognition delegate")
            self._enabled = False
            return
        self._delegate = delegate
        self._recognizer.setDelegate_(delegate)

        # Set up audio engine
        logger.debug("Setting up AVAudioEngine...")
        try:
            self._setup_audio_engine()
            logger.debug("AVAudioEngine initialized and running")
        except Exception as e:
            logger.error(f"Failed to set up audio engine: {e}")
            self._enabled = False
            return

        with self._running_lock:
            self._running = True

        # Start first recognition task
        self._start_recognition()

        logger.info(f"Ear started (locale={self._locale}, on_device={self._on_device})")

    def stop(self) -> None:
        """Stop speech recognition and release resources."""
        with self._running_lock:
            if not self._running:
                logger.debug("Ear.stop() skipped: not running")
                return
            self._running = False

        logger.debug("Ear shutting down...")

        # Cancel active recognition
        if self._recognition_task is not None:
            logger.debug("Cancelling active recognition task")
            self._recognition_task.cancel()
            self._recognition_task = None

        # End request
        if self._request is not None:
            logger.debug("Ending active recognition request")
            self._request.endAudio()
            self._request = None

        # Stop audio engine
        if self._audio_engine is not None:
            logger.debug("Stopping audio engine")
            self._audio_engine.inputNode().removeTapOnBus_(0)
            self._audio_engine.stop()
            self._audio_engine = None

        self._recognizer = None
        self._delegate = None

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
        if not self._muted:
            self._muted = True
            self._partial = ""
            logger.debug("Ear muted")

    def unmute(self) -> None:
        """Resume audio forwarding after mute."""
        if self._muted:
            self._muted = False
            logger.debug("Ear unmuted")

    def _is_running(self) -> bool:
        with self._running_lock:
            return self._running

    # ----------------------------
    # Audio Engine
    # ----------------------------

    def _setup_audio_engine(self) -> None:
        """Set up AVAudioEngine with a tap on the microphone input."""
        engine = AVAudioEngine.alloc().init()
        input_node = engine.inputNode()
        recording_format = input_node.outputFormatForBus_(0)

        # Install tap on input node - feeds audio to recognition request
        input_node.installTapOnBus_bufferSize_format_block_(
            0,
            1024,
            recording_format,
            self._audio_tap_block,
        )

        engine.prepare()
        success, error = engine.startAndReturnError_(None)
        if not success:
            raise RuntimeError(f"Audio engine failed to start: {error}")

        self._audio_engine = engine

    def _audio_tap_block(
        self,
        buffer: Any,  # AVAudioPCMBuffer
        _when: Any,  # AVAudioTime
    ) -> None:
        """Called for each audio buffer from the microphone.

        Forwards audio to the active recognition request.
        Skips forwarding when muted to prevent hearing own speech.
        """
        if self._muted:
            return
        request = self._request
        if request is not None:
            request.appendAudioPCMBuffer_(buffer)

    # ----------------------------
    # Recognition Lifecycle
    # ----------------------------

    def _start_recognition(self) -> None:
        """Create a new recognition request and task."""
        if not self._is_running() or self._recognizer is None:
            logger.debug("_start_recognition skipped: not running or no recognizer")
            return

        # Create a new request
        request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.setShouldReportPartialResults_(True)

        on_device = self._on_device and self._recognizer.supportsOnDeviceRecognition()
        if on_device:
            request.setRequiresOnDeviceRecognition_(True)

        self._request = request

        logger.debug(f"Starting recognition task (on_device={on_device})")

        # Start recognition task with result handler
        self._recognition_task = self._recognizer.recognitionTaskWithRequest_resultHandler_(
            request,
            self._recognition_result_handler,
        )

    def _recognition_result_handler(
        self,
        result: Any,  # SFSpeechRecognitionResult
        error: Any,  # NSError
    ) -> None:
        """Handle recognition results and errors.

        Called on the main thread by SFSpeechRecognizer. Processes
        partial and final transcription results. Detects persistent
        errors (e.g. Siri disabled) and gracefully disables the ear
        instead of looping forever.
        """
        if result is not None:
            if self._muted:
                # Drop results from pre-mute buffered audio, but still
                # allow error handling and task restart below to proceed.
                pass
            elif result.isFinal():
                # Final result - complete utterance
                text = str(result.bestTranscription().formattedString()).strip()
                if text:
                    with self._utterances_lock:
                        self._utterances.append(text)
                    self._partial = ""

                    # Print final transcription to console
                    sys.stdout.write(f'\r\033[K{colors.GREEN}[SPEECH]{colors.RESET} "{text}"\n')
                    sys.stdout.flush()

                    # Publish on event bus
                    self._event_bus.publish(
                        "perception.speech",
                        {"text": text, "is_final": True},
                    )

                    logger.info(f"Speech recognized: {text}")

                # Successful recognition resets error counter
                self._consecutive_errors = 0
            else:
                # Partial result - overwrite current line in-place
                partial = str(result.bestTranscription().formattedString())
                self._partial = partial
                sys.stdout.write(
                    f"\r\033[K{colors.DIM}[HEARING]{colors.RESET} {colors.DIM}{partial}{colors.RESET}"
                )
                sys.stdout.flush()

        if error is not None:
            error_code = error.code()

            if error_code in BENIGN_ERROR_CODES:
                # Expected errors (timeout, cancellation) - reset counter
                # Code 203 = no speech timeout: show the user the ear is still alive
                if error_code == 203:
                    sys.stdout.write(f"\r\033[K{colors.DIM}[HEARING] (listening...){colors.RESET}")
                    sys.stdout.flush()
                logger.debug(f"Benign recognition error (code={error_code}), restarting")
                self._consecutive_errors = 0
            else:
                now = time.monotonic()
                if now - self._last_error_time > ERROR_WINDOW_SECONDS:
                    # Errors spaced far apart - reset counter
                    self._consecutive_errors = 1
                else:
                    self._consecutive_errors += 1
                self._last_error_time = now

                logger.warning(
                    f"Speech recognition error ({self._consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): "
                    f"{error.localizedDescription()}"
                )

                if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        "Persistent speech recognition failure detected. "
                        "Disabling ear. Check that Siri & Dictation are "
                        "enabled in System Settings > Privacy & Security."
                    )
                    sys.stdout.write(
                        f"\r\033[K{colors.RED}[HEARING] Disabled: "
                        f"enable Siri & Dictation in System Settings > "
                        f"Privacy & Security{colors.RESET}\n"
                    )
                    sys.stdout.flush()
                    self._enabled = False
                    with self._running_lock:
                        self._running = False
                    return

        # If the task ended (final result or error), restart
        is_final = result is not None and result.isFinal()
        task_ended = error is not None or is_final

        if task_ended and self._is_running():
            self._restart_recognition()

    def _restart_recognition(self) -> None:
        """Restart recognition task without interrupting audio capture."""
        logger.debug("Restarting recognition task")

        # End the old request
        if self._request is not None:
            self._request.endAudio()
            self._request = None

        self._recognition_task = None

        # Start a new recognition session
        self._start_recognition()

    # ----------------------------
    # Authorization
    # ----------------------------

    def _request_authorization(self) -> None:
        """Request speech recognition authorization (blocks until user responds)."""
        logger.debug("Requesting speech recognition authorization...")
        authorized_event = threading.Event()

        def handler(status: int) -> None:
            if status == SFSpeechRecognizerAuthorizationStatusAuthorized:
                logger.info("Speech recognition authorized")
            else:
                logger.warning(f"Speech recognition authorization denied (status={status})")
            authorized_event.set()

        SFSpeechRecognizer.requestAuthorization_(handler)

        # Pump run loop while waiting for authorization dialog
        run_loop = NSRunLoop.currentRunLoop()
        while not authorized_event.is_set():
            from Foundation import NSDate, NSDefaultRunLoopMode

            run_loop.runMode_beforeDate_(
                NSDefaultRunLoopMode,
                NSDate.dateWithTimeIntervalSinceNow_(0.1),
            )
