"""Continuous speech recognition using macOS SFSpeechRecognizer.

Listens to the microphone at all times and delivers recognized
utterances to the agent's perception loop via a thread-safe buffer.
Recognition tasks are seamlessly restarted on timeout (~60s limit).
"""

import logging
import threading
from collections import deque
from typing import Any, Self

import objc
from AVFoundation import AVAudioEngine
from Foundation import NSLocale, NSObject, NSRunLoop
from Speech import (
    SFSpeechAudioBufferRecognitionRequest,
    SFSpeechRecognizer,
    SFSpeechRecognizerAuthorizationStatus,
)

from jung_agent.config import AgentConfig
from jung_agent.event_bus import get_event_bus

logger = logging.getLogger(__name__)

# Maximum number of buffered utterances before oldest are dropped
MAX_UTTERANCES = 10


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
            return

        with self._running_lock:
            if self._running:
                return

        # Check authorization
        auth_status = SFSpeechRecognizer.authorizationStatus()
        if auth_status == SFSpeechRecognizerAuthorizationStatus.notDetermined:
            # Request authorization (blocking - waits for user response)
            self._request_authorization()
            auth_status = SFSpeechRecognizer.authorizationStatus()

        if auth_status != SFSpeechRecognizerAuthorizationStatus.authorized:
            logger.warning(
                f"Speech recognition not authorized (status={auth_status}). Ear will be disabled."
            )
            self._enabled = False
            return

        # Set up recognizer
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
        delegate = SpeechRecognitionDelegate.alloc().init()
        if delegate is None:
            logger.error("Failed to create speech recognition delegate")
            self._enabled = False
            return
        self._delegate = delegate
        self._recognizer.setDelegate_(delegate)

        # Set up audio engine
        try:
            self._setup_audio_engine()
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
                return
            self._running = False

        # Cancel active recognition
        if self._recognition_task is not None:
            self._recognition_task.cancel()
            self._recognition_task = None

        # End request
        if self._request is not None:
            self._request.endAudio()
            self._request = None

        # Stop audio engine
        if self._audio_engine is not None:
            self._audio_engine.inputNode().removeTapOnBus_(0)
            self._audio_engine.stop()
            self._audio_engine = None

        self._recognizer = None
        self._delegate = None

        with self._utterances_lock:
            self._utterances.clear()

        logger.info("Ear stopped")

    def get_utterances(self) -> list[str]:
        """Drain and return all buffered utterances.

        Returns:
            List of recognized utterance strings (may be empty).
        """
        with self._utterances_lock:
            result = list(self._utterances)
            self._utterances.clear()
        return result

    @property
    def partial(self) -> str:
        """Current partial (in-progress) transcription."""
        return self._partial

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
        """
        request = self._request
        if request is not None:
            request.appendAudioPCMBuffer_(buffer)

    # ----------------------------
    # Recognition Lifecycle
    # ----------------------------

    def _start_recognition(self) -> None:
        """Create a new recognition request and task."""
        if not self._is_running() or self._recognizer is None:
            return

        # Create a new request
        request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.setShouldReportPartialResults_(True)

        if self._on_device and self._recognizer.supportsOnDeviceRecognition():
            request.setRequiresOnDeviceRecognition_(True)

        self._request = request

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
        partial and final transcription results.
        """
        if result is not None:
            transcription = result.bestTranscription().formattedString()

            if result.isFinal():
                # Final result - complete utterance
                text = str(transcription).strip()
                if text:
                    with self._utterances_lock:
                        self._utterances.append(text)
                    self._partial = ""

                    # Publish on event bus
                    self._event_bus.publish(
                        "perception.speech",
                        {"text": text, "is_final": True},
                    )

                    logger.info(f"Speech recognized: {text}")
            else:
                # Partial result - update for display
                self._partial = str(transcription)

        if error is not None:
            error_code = error.code()
            # Code 203 = no speech detected (normal timeout)
            # Code 216 = recognition task was cancelled
            # Code 1110 = request was cancelled
            if error_code not in (203, 216, 1110):
                logger.warning(f"Speech recognition error: {error.localizedDescription()}")

        # If the task ended (final result or error), restart
        is_final = result is not None and result.isFinal()
        task_ended = error is not None or is_final

        if task_ended and self._is_running():
            self._restart_recognition()

    def _restart_recognition(self) -> None:
        """Restart recognition task without interrupting audio capture."""
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
        authorized_event = threading.Event()

        def handler(status: int) -> None:
            if status == SFSpeechRecognizerAuthorizationStatus.authorized:
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
