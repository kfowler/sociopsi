"""Platform speech recognition (STT) backends.

Provides continuous speech recognition with streaming audio → text callbacks.
Darwin backend uses SFSpeechRecognizer + AVAudioEngine.
Linux backend uses vosk with sounddevice for microphone input.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Callback type: called with recognized text and whether it's a final result
type SpeechCallback = Callable[[str, bool], None]


class SpeechBackend(ABC):
    """Abstract speech recognition backend."""

    @abstractmethod
    def start_listening(self, callback: SpeechCallback) -> None:
        """Begin continuous recognition, calling callback(text, is_final) on each result.

        Args:
            callback: Called with (text, is_final) for each recognition result.
                      is_final=True means a complete utterance; False means partial.
        """

    @abstractmethod
    def stop_listening(self) -> None:
        """Stop recognition and release resources."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether STT is available on this platform."""

    @abstractmethod
    def mute(self) -> None:
        """Suppress audio forwarding (e.g. while TTS is speaking)."""

    @abstractmethod
    def unmute(self) -> None:
        """Resume audio forwarding."""


class DarwinSpeechBackend(SpeechBackend):
    """macOS speech recognition using SFSpeechRecognizer + AVAudioEngine."""

    # Error codes that are expected and should not count toward the fatal threshold
    # 203 = no speech detected (normal timeout)
    # 216 = recognition task was cancelled
    # 1110 = request was cancelled
    BENIGN_ERROR_CODES = frozenset({203, 216, 1110})
    MAX_CONSECUTIVE_ERRORS = 3
    ERROR_WINDOW_SECONDS = 5.0

    def __init__(self, locale: str = "en-US", on_device: bool = True) -> None:
        self._locale = locale
        self._on_device = on_device
        self._callback: SpeechCallback | None = None

        # Running state
        self._running = False
        self._running_lock = threading.Lock()

        # Apple framework objects (initialized in start_listening)
        self._audio_engine: Any = None
        self._recognizer: Any = None
        self._delegate: Any = None
        self._request: Any = None
        self._recognition_task: Any = None

        # Mute flag
        self._muted = False

        # Consecutive error tracking
        self._consecutive_errors: int = 0
        self._last_error_time: float = 0.0

        # Availability (set after checking)
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if macOS speech recognition is available."""
        if self._available is not None:
            return self._available
        try:
            from Speech import (
                SFSpeechRecognizer,
                SFSpeechRecognizerAuthorizationStatusAuthorized,
            )

            auth = SFSpeechRecognizer.authorizationStatus()
            available = bool(auth == SFSpeechRecognizerAuthorizationStatusAuthorized)
            self._available = available
            return available
        except ImportError:
            self._available = False
            return False

    def start_listening(self, callback: SpeechCallback) -> None:
        """Begin continuous recognition using SFSpeechRecognizer."""
        import objc
        from AVFoundation import AVAudioEngine
        from Foundation import NSLocale, NSObject
        from Speech import (
            SFSpeechRecognizer,
            SFSpeechRecognizerAuthorizationStatusAuthorized,
            SFSpeechRecognizerAuthorizationStatusNotDetermined,
        )

        self._callback = callback

        with self._running_lock:
            if self._running:
                logger.debug("DarwinSpeechBackend already running")
                return

        # Check authorization
        auth_status = SFSpeechRecognizer.authorizationStatus()
        if auth_status == SFSpeechRecognizerAuthorizationStatusNotDetermined:
            self._request_authorization()
            auth_status = SFSpeechRecognizer.authorizationStatus()

        if auth_status != SFSpeechRecognizerAuthorizationStatusAuthorized:
            logger.warning(f"Speech recognition not authorized (status={auth_status})")
            self._available = False
            return

        # Set up recognizer
        locale = NSLocale.alloc().initWithLocaleIdentifier_(self._locale)
        self._recognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale)
        if self._recognizer is None:
            logger.error(f"Failed to create speech recognizer for locale {self._locale}")
            self._available = False
            return

        if self._on_device and self._recognizer.supportsOnDeviceRecognition():
            logger.info("Using on-device speech recognition")
        elif self._on_device:
            logger.warning("On-device recognition not supported, falling back to server")

        # Set up delegate
        class _Delegate(NSObject):
            def init(self) -> Any:  # noqa: N805
                self = objc.super(_Delegate, self).init()
                return self

            def speechRecognizer_availabilityDidChange_(self, _rec: Any, avail: bool) -> None:  # noqa: N802, N805
                if not avail:
                    logger.warning("Speech recognizer became unavailable")

        delegate = _Delegate.alloc().init()
        if delegate is None:
            logger.error("Failed to create speech recognition delegate")
            self._available = False
            return
        self._delegate = delegate
        self._recognizer.setDelegate_(delegate)

        # Set up audio engine
        try:
            engine = AVAudioEngine.alloc().init()
            input_node = engine.inputNode()
            recording_format = input_node.outputFormatForBus_(0)

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
        except Exception as e:
            logger.error(f"Failed to set up audio engine: {e}")
            self._available = False
            return

        with self._running_lock:
            self._running = True

        self._available = True
        self._start_recognition()
        logger.info(
            f"DarwinSpeechBackend started (locale={self._locale}, on_device={self._on_device})"
        )

    def stop_listening(self) -> None:
        """Stop speech recognition and release resources."""
        with self._running_lock:
            if not self._running:
                return
            self._running = False

        if self._recognition_task is not None:
            self._recognition_task.cancel()
            self._recognition_task = None

        if self._request is not None:
            self._request.endAudio()
            self._request = None

        if self._audio_engine is not None:
            self._audio_engine.inputNode().removeTapOnBus_(0)
            self._audio_engine.stop()
            self._audio_engine = None

        self._recognizer = None
        self._delegate = None
        self._callback = None
        logger.info("DarwinSpeechBackend stopped")

    def mute(self) -> None:
        if not self._muted:
            self._muted = True
            logger.debug("DarwinSpeechBackend muted")

    def unmute(self) -> None:
        if self._muted:
            self._muted = False
            logger.debug("DarwinSpeechBackend unmuted")

    def _is_running(self) -> bool:
        with self._running_lock:
            return self._running

    def _audio_tap_block(self, buffer: Any, _when: Any) -> None:
        """Forward microphone audio to recognition request."""
        if self._muted:
            return
        request = self._request
        if request is not None:
            request.appendAudioPCMBuffer_(buffer)

    def _start_recognition(self) -> None:
        """Create a new recognition request and task."""
        if not self._is_running() or self._recognizer is None:
            return

        from Speech import SFSpeechAudioBufferRecognitionRequest

        request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.setShouldReportPartialResults_(True)

        on_device = self._on_device and self._recognizer.supportsOnDeviceRecognition()
        if on_device:
            request.setRequiresOnDeviceRecognition_(True)

        self._request = request

        self._recognition_task = self._recognizer.recognitionTaskWithRequest_resultHandler_(
            request,
            self._recognition_result_handler,
        )

    def _recognition_result_handler(self, result: Any, error: Any) -> None:
        """Handle recognition results and errors."""
        if result is not None:
            if self._muted:
                pass  # Drop results from pre-mute buffered audio
            elif result.isFinal():
                text = str(result.bestTranscription().formattedString()).strip()
                if text and self._callback:
                    self._callback(text, True)
                self._consecutive_errors = 0
            else:
                partial = str(result.bestTranscription().formattedString())
                if self._callback:
                    self._callback(partial, False)

        if error is not None:
            error_code = error.code()

            if error_code in self.BENIGN_ERROR_CODES:
                logger.debug(f"Benign recognition error (code={error_code}), restarting")
                self._consecutive_errors = 0
            else:
                now = time.monotonic()
                if now - self._last_error_time > self.ERROR_WINDOW_SECONDS:
                    self._consecutive_errors = 1
                else:
                    self._consecutive_errors += 1
                self._last_error_time = now

                logger.warning(
                    f"Speech recognition error ({self._consecutive_errors}/{self.MAX_CONSECUTIVE_ERRORS}): "
                    f"{error.localizedDescription()}"
                )

                if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        "Persistent speech recognition failure. "
                        "Check Siri & Dictation in System Settings."
                    )
                    self._available = False
                    with self._running_lock:
                        self._running = False
                    return

        is_final = result is not None and result.isFinal()
        task_ended = error is not None or is_final

        if task_ended and self._is_running():
            self._restart_recognition()

    def _restart_recognition(self) -> None:
        """Restart recognition task without interrupting audio capture."""
        if self._request is not None:
            self._request.endAudio()
            self._request = None
        self._recognition_task = None
        self._start_recognition()

    def _request_authorization(self) -> None:
        """Request speech recognition authorization (blocks until user responds)."""
        from Foundation import NSDate, NSDefaultRunLoopMode, NSRunLoop
        from Speech import (
            SFSpeechRecognizer,
            SFSpeechRecognizerAuthorizationStatusAuthorized,
        )

        authorized_event = threading.Event()

        def handler(status: int) -> None:
            if status == SFSpeechRecognizerAuthorizationStatusAuthorized:
                logger.info("Speech recognition authorized")
            else:
                logger.warning(f"Speech recognition authorization denied (status={status})")
            authorized_event.set()

        SFSpeechRecognizer.requestAuthorization_(handler)

        run_loop = NSRunLoop.currentRunLoop()
        while not authorized_event.is_set():
            run_loop.runMode_beforeDate_(
                NSDefaultRunLoopMode,
                NSDate.dateWithTimeIntervalSinceNow_(0.1),
            )


class LinuxSpeechBackend(SpeechBackend):
    """Linux speech recognition using vosk with sounddevice."""

    def __init__(self, model_path: str | None = None, sample_rate: int = 16000) -> None:
        self._model_path = model_path
        self._sample_rate = sample_rate
        self._callback: SpeechCallback | None = None
        self._running = False
        self._running_lock = threading.Lock()
        self._muted = False
        self._listen_thread: threading.Thread | None = None
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if vosk and sounddevice are available."""
        if self._available is not None:
            return self._available
        try:
            import sounddevice  # noqa: F401
            import vosk  # noqa: F401

            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def start_listening(self, callback: SpeechCallback) -> None:
        """Begin continuous recognition using vosk."""
        if not self.is_available():
            logger.warning("Vosk or sounddevice not available")
            return

        with self._running_lock:
            if self._running:
                logger.debug("LinuxSpeechBackend already running")
                return

        import json
        import queue

        import sounddevice as sd
        import vosk

        self._callback = callback

        # Find or download model
        model_path = self._model_path
        if model_path is None:
            # Default: use small English model
            from pathlib import Path

            default_model = Path.home() / ".sociopsi" / "vosk-model"
            if default_model.exists():
                model_path = str(default_model)
            else:
                logger.error(
                    f"No vosk model found at {default_model}. "
                    "Download from https://alphacephei.com/vosk/models and extract to "
                    f"{default_model}"
                )
                self._available = False
                return

        try:
            vosk.SetLogLevel(-1)  # Suppress vosk logs
            model = vosk.Model(model_path)
        except Exception as e:
            logger.error(f"Failed to load vosk model from {model_path}: {e}")
            self._available = False
            return

        audio_queue: queue.Queue[bytes] = queue.Queue()

        def audio_callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            if status:
                logger.debug(f"sounddevice status: {status}")
            if not self._muted:
                audio_queue.put(bytes(indata))

        with self._running_lock:
            self._running = True

        def listen_loop() -> None:
            recognizer = vosk.KaldiRecognizer(model, self._sample_rate)
            try:
                with sd.RawInputStream(
                    samplerate=self._sample_rate,
                    blocksize=8000,
                    dtype="int16",
                    channels=1,
                    callback=audio_callback,
                ):
                    logger.info("LinuxSpeechBackend started listening")
                    while self._is_running():
                        try:
                            data = audio_queue.get(timeout=0.5)
                        except queue.Empty:
                            continue

                        if recognizer.AcceptWaveform(data):
                            result = json.loads(recognizer.Result())
                            text = result.get("text", "").strip()
                            if text and self._callback:
                                self._callback(text, True)
                        else:
                            partial_result = json.loads(recognizer.PartialResult())
                            partial_text = partial_result.get("partial", "").strip()
                            if partial_text and self._callback:
                                self._callback(partial_text, False)
            except Exception as e:
                logger.error(f"LinuxSpeechBackend listen loop error: {e}")
            finally:
                with self._running_lock:
                    self._running = False
                logger.info("LinuxSpeechBackend stopped listening")

        self._listen_thread = threading.Thread(target=listen_loop, daemon=True, name="vosk-stt")
        self._listen_thread.start()

    def stop_listening(self) -> None:
        """Stop recognition."""
        with self._running_lock:
            if not self._running:
                return
            self._running = False

        if self._listen_thread is not None:
            self._listen_thread.join(timeout=5.0)
            self._listen_thread = None

        self._callback = None
        logger.info("LinuxSpeechBackend stopped")

    def mute(self) -> None:
        if not self._muted:
            self._muted = True
            logger.debug("LinuxSpeechBackend muted")

    def unmute(self) -> None:
        if self._muted:
            self._muted = False
            logger.debug("LinuxSpeechBackend unmuted")

    def _is_running(self) -> bool:
        with self._running_lock:
            return self._running
