"""Voice command transcription using local Whisper."""

import time
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sociopsi.core.config import Config
from sociopsi.core.event_bus import EventBus


class SpeechInput:
    """Voice command transcription using faster-whisper."""

    def __init__(self, event_bus: EventBus, config: Config) -> None:
        """Initialize speech input.

        Args:
            event_bus: Event bus for publishing events
            config: Configuration
        """
        self.event_bus = event_bus
        self.model_name = config.get("audio.whisper_model", "base.en")
        self.model: Any = None  # Lazy load, WhisperModel type
        self.is_recording = False
        self.audio_buffer: list[NDArray[np.float32]] = []

    async def start_recording(self) -> None:
        """Start recording for voice command."""
        self.is_recording = True
        self.audio_buffer.clear()
        self.event_bus.publish("speech.recording.started", {"timestamp": time.time()})

    async def stop_recording(self) -> None:
        """Stop recording and transcribe."""
        self.is_recording = False

        # Transcribe buffered audio
        text = ""
        if self.audio_buffer:
            text = await self.transcribe(self.audio_buffer)

        if text:
            self.event_bus.publish(
                "command.received", {"text": text, "source": "voice", "timestamp": time.time()}
            )

        self.event_bus.publish(
            "speech.recording.stopped", {"transcribed": text, "timestamp": time.time()}
        )

    async def transcribe(self, audio_data: list[NDArray[np.float32]]) -> str:
        """Transcribe audio using faster-whisper.

        Args:
            audio_data: List of audio arrays

        Returns:
            Transcribed text
        """
        # Lazy load model
        if self.model is None:
            self._load_model()

        if not audio_data:
            return ""

        if self.model is None:
            return ""

        try:
            # Concatenate all audio buffers
            audio = np.concatenate(audio_data)

            # Transcribe
            segments, info = self.model.transcribe(audio, language="en")
            text = " ".join([segment.text for segment in segments])

            return text.strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""

    def _load_model(self) -> None:
        """Load Whisper model (lazy)."""
        try:
            from faster_whisper import WhisperModel

            print(f"Loading Whisper model: {self.model_name}")
            self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            print("Whisper model loaded")
        except Exception as e:
            print(f"Failed to load Whisper model: {e}")
            self.model = None

    def add_audio(self, audio: NDArray[np.float32]) -> None:
        """Add audio to buffer while recording.

        Args:
            audio: Audio samples
        """
        if self.is_recording:
            self.audio_buffer.append(audio.copy())
