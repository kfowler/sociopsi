"""Audio perception - ambient sound monitoring and analysis."""

import time
from collections import deque
from typing import Any

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray

from sociopsi.core.config import Config
from sociopsi.core.event_bus import EventBus


class AdaptiveSampler:
    """Adjusts audio analysis frequency based on activity."""

    def __init__(self) -> None:
        """Initialize adaptive sampler."""
        self.current_fps = 3.0  # Start at baseline
        self.min_fps = 1.0
        self.max_fps = 10.0
        self.idle_fps = 3.0
        self.last_sample_time = 0.0

    def should_sample(self) -> bool:
        """Determine if we should analyze this frame.

        Returns:
            True if should sample now
        """
        current_time = time.time()
        interval = 1.0 / self.current_fps

        if current_time - self.last_sample_time >= interval:
            self.last_sample_time = current_time
            return True
        return False

    def update(self, classification: dict[str, Any]) -> None:
        """Adjust sampling rate based on activity.

        Args:
            classification: Sound classification dict
        """
        sound_type = classification["type"]
        volume = classification["volume"]

        if sound_type in ("activity", "loud_noise") or volume > 0.5:
            # High activity, increase FPS
            self.current_fps = min(self.max_fps, self.current_fps + 1.0)
        elif sound_type == "silence":
            # No activity, decrease FPS
            self.current_fps = max(self.min_fps, self.current_fps - 0.5)
        else:
            # Moderate activity, move toward idle
            if self.current_fps > self.idle_fps:
                self.current_fps -= 0.2
            elif self.current_fps < self.idle_fps:
                self.current_fps += 0.2


class SoundClassifier:
    """Classifies audio into speech/noise/silence."""

    def __init__(self) -> None:
        """Initialize sound classifier."""
        self.silence_threshold = 0.02  # RMS threshold

    def classify(self, audio_data: NDArray[np.float32]) -> dict[str, Any]:
        """Classify 1 second of audio.

        Args:
            audio_data: Audio samples

        Returns:
            Classification dict with type, volume, confidence
        """
        # Calculate volume (RMS)
        volume = float(np.sqrt(np.mean(audio_data**2)))

        # Detect silence
        if volume < self.silence_threshold:
            return {"type": "silence", "volume": 0.0, "confidence": 0.95}

        # Detect voiced audio (speech/music) vs noise
        # For MVP: simple heuristic based on zero-crossing rate
        # Note: Cannot distinguish speech from music with this method
        zcr = self._zero_crossing_rate(audio_data)
        is_voiced = 0.05 < zcr < 0.3  # Voiced audio has moderate ZCR

        # Check for loud sudden sounds
        if volume > 0.5:
            return {
                "type": "loud_noise",
                "volume": min(1.0, volume / 0.1),
                "confidence": 0.8,
            }

        return {
            "type": "activity" if is_voiced else "noise",
            "volume": min(1.0, volume / 0.1),  # Normalize
            "confidence": 0.6,  # Lower for heuristic
        }

    def _zero_crossing_rate(self, audio: NDArray[np.float32]) -> float:
        """Calculate zero-crossing rate.

        Args:
            audio: Audio samples

        Returns:
            ZCR value
        """
        return float(np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio)))


class CircularBuffer:
    """Circular buffer for audio samples."""

    def __init__(self, size: int) -> None:
        """Initialize buffer.

        Args:
            size: Buffer size in samples
        """
        self.size = size
        self.buffer: deque[float] = deque(maxlen=size)

    def append(self, data: NDArray[np.float32]) -> None:
        """Append audio data.

        Args:
            data: Audio samples
        """
        for sample in data.flatten():
            self.buffer.append(sample)

    def get_recent(self, duration: float, sample_rate: int = 16000) -> NDArray[np.float64]:
        """Get recent audio.

        Args:
            duration: Duration in seconds
            sample_rate: Sample rate

        Returns:
            Audio samples
        """
        n_samples = int(duration * sample_rate)
        n_samples = min(n_samples, len(self.buffer))

        if n_samples == 0:
            return np.array([])

        # Get last n_samples
        recent = list(self.buffer)[-n_samples:]
        return np.array(recent)

    def clear(self) -> None:
        """Clear buffer."""
        self.buffer.clear()


class AudioPerception:
    """Ambient sound monitoring and analysis."""

    def __init__(self, event_bus: EventBus, config: Config) -> None:
        """Initialize audio perception.

        Args:
            event_bus: Event bus for publishing events
            config: Configuration
        """
        self.event_bus = event_bus
        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.chunk_size = config.get("audio.chunk_size", 1024)
        self.buffer_seconds = config.get("audio.buffer_seconds", 6.0)

        self.buffer = CircularBuffer(size=int(self.sample_rate * self.buffer_seconds))
        self.adaptive_sampler = AdaptiveSampler()
        self.sound_classifier = SoundClassifier()

        self.is_running = False
        self.stream: sd.InputStream | None = None

    def _audio_callback(
        self,
        indata: NDArray[np.float32],
        frames: int,
        time_info: Any,  # sounddevice callback time info dict
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice for each audio chunk.

        Args:
            indata: Input audio data
            frames: Number of frames
            time_info: Timing info
            status: Status flags
        """
        if status:
            print(f"Audio callback status: {status}")
        self.buffer.append(indata)

    async def start(self) -> None:
        """Begin audio capture."""
        try:
            self.is_running = True
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self._audio_callback,
                blocksize=self.chunk_size,
            )
            self.stream = stream
            stream.start()
            print(f"Audio capture started at {self.sample_rate}Hz")
        except Exception as e:
            print(f"Failed to start audio capture: {e}")
            self.is_running = False

    async def stop(self) -> None:
        """Stop audio capture."""
        self.is_running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    async def update(self, dt: float) -> None:
        """Adaptive sampling and classification.

        Args:
            dt: Delta time since last update
        """
        if not self.is_running:
            return

        # Should we analyze this frame?
        if not self.adaptive_sampler.should_sample():
            return

        # Get recent audio (1 second)
        audio_data = self.buffer.get_recent(duration=1.0, sample_rate=self.sample_rate)

        if len(audio_data) == 0:
            return

        # Classify sound
        classification = self.sound_classifier.classify(audio_data)

        # Publish ambient sound event
        self.event_bus.publish(
            "perception.audio.ambient",
            {
                "type": classification["type"],
                "volume": classification["volume"],
                "confidence": classification["confidence"],
            },
        )

        # Update adaptive sampler
        self.adaptive_sampler.update(classification)
