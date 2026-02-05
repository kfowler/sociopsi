# Phase 3: Audio Perception & Enhanced Cognition

**Goal**: Add audio perception with emotion detection, semantic memory search, and meta-cognitive reflection.

**Estimated Time**: 5-6 hours

## Overview

Phase 3 extends the agent's sensory capabilities with audio perception and enhances its cognitive depth through semantic memory and self-reflection.

### Key Features
1. **Audio Perception**: Capture and process audio input
2. **Speech Recognition**: Transcribe speech using Whisper
3. **Emotion Detection**: Analyze tone, pitch, and sentiment
4. **Semantic Memory**: Vector embeddings for similarity search
5. **Meta-Cognition**: Reflect on own thoughts and processes

## Tasks

### Task 1: Audio Capture System (30 min)
**Goal**: Capture audio from microphone with buffering

**Implementation**:
```python
# src/sociopsi/subsystems/perception/audio.py
import pyaudio
import numpy as np
from collections import deque

class AudioPerception:
    def __init__(self, event_bus, sample_rate=16000, chunk_size=1024):
        self.event_bus = event_bus
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.buffer = deque(maxlen=100)  # ~6 seconds at 16kHz
        self.is_recording = False

    def start_recording(self):
        """Start audio capture."""
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback,
        )
        self.is_recording = True
        self.stream.start_stream()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Handle incoming audio data."""
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        self.buffer.append(audio_data)
        return (in_data, pyaudio.paContinue)

    def get_audio_segment(self, duration_sec=3.0):
        """Get recent audio segment."""
        num_chunks = int(duration_sec * self.sample_rate / self.chunk_size)
        chunks = list(self.buffer)[-num_chunks:]
        if not chunks:
            return None
        return np.concatenate(chunks)
```

**Tests**:
- Test audio capture initialization
- Test buffer management
- Test audio segment retrieval

---

### Task 2: Speech Recognition with Whisper (45 min)
**Goal**: Transcribe speech using OpenAI Whisper

**Dependencies**: Add `openai-whisper` to pyproject.toml

**Implementation**:
```python
# src/sociopsi/subsystems/perception/speech.py
import whisper
import numpy as np

class SpeechRecognition:
    def __init__(self, event_bus, model_name="base"):
        self.event_bus = event_bus
        self.model = whisper.load_model(model_name)

    def transcribe(self, audio_data, sample_rate=16000):
        """Transcribe audio to text.

        Args:
            audio_data: numpy array of audio samples
            sample_rate: sample rate in Hz

        Returns:
            Transcription dict with text, language, confidence
        """
        # Convert to float32 in [-1.0, 1.0]
        audio_float = audio_data.astype(np.float32) / 32768.0

        # Transcribe
        result = self.model.transcribe(
            audio_float,
            language="en",
            fp16=False,
        )

        # Publish event
        self.event_bus.publish("perception.speech.transcribed", {
            "text": result["text"],
            "language": result["language"],
            "segments": result["segments"],
        })

        return result
```

**Tests**:
- Test Whisper model loading
- Test transcription with sample audio
- Test event publishing

---

### Task 3: Emotion Detection from Audio (45 min)
**Goal**: Detect emotional tone from audio features

**Implementation**:
```python
# src/sociopsi/subsystems/perception/emotion.py
import librosa
import numpy as np

class EmotionDetection:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def analyze_emotion(self, audio_data, sample_rate=16000):
        """Analyze emotional content of audio.

        Returns:
            dict with valence, arousal, and dominant emotion
        """
        # Extract features
        audio_float = audio_data.astype(np.float32) / 32768.0

        # Pitch (fundamental frequency)
        pitches, magnitudes = librosa.piptrack(
            y=audio_float,
            sr=sample_rate,
        )
        pitch_mean = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0

        # Energy (RMS)
        rms = librosa.feature.rms(y=audio_float)[0]
        energy_mean = np.mean(rms)

        # Spectral centroid (brightness)
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_float,
            sr=sample_rate,
        )[0]
        brightness = np.mean(spectral_centroid)

        # Map to valence/arousal
        # High pitch + high energy = excited (high arousal, positive valence)
        # Low pitch + low energy = sad (low arousal, negative valence)
        arousal = self._normalize(energy_mean, 0.0, 0.1)
        valence = self._normalize(pitch_mean, 80, 300)

        # Determine dominant emotion
        emotion = self._classify_emotion(valence, arousal)

        emotion_data = {
            "valence": valence,
            "arousal": arousal,
            "emotion": emotion,
            "pitch_mean": float(pitch_mean),
            "energy_mean": float(energy_mean),
            "brightness": float(brightness),
        }

        # Publish event
        self.event_bus.publish("perception.emotion.detected", emotion_data)

        return emotion_data

    def _normalize(self, value, min_val, max_val):
        """Normalize value to [0, 1]."""
        return np.clip((value - min_val) / (max_val - min_val), 0.0, 1.0)

    def _classify_emotion(self, valence, arousal):
        """Classify emotion from valence/arousal."""
        if arousal > 0.6:
            return "excited" if valence > 0.5 else "angry"
        elif arousal > 0.3:
            return "happy" if valence > 0.5 else "sad"
        else:
            return "calm" if valence > 0.5 else "depressed"
```

**Tests**:
- Test emotion analysis with synthetic audio
- Test valence/arousal calculation
- Test emotion classification
- Test event publishing

---

### Task 4: Semantic Memory with Embeddings (60 min)
**Goal**: Add vector embeddings for semantic similarity search

**Dependencies**: Add `sentence-transformers` to pyproject.toml

**Implementation**:
```python
# src/sociopsi/subsystems/semantic_memory.py
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Tuple
from sociopsi.subsystems.memory import Memory, MemorySystem

class SemanticMemory(MemorySystem):
    """Memory system with semantic similarity search."""

    def __init__(self, max_memories=100, forget_threshold=0.1, model_name="all-MiniLM-L6-v2"):
        super().__init__(max_memories, forget_threshold)
        self.encoder = SentenceTransformer(model_name)
        self.embeddings = []

    def add_memory(self, content: str, intensity: float = 0.5, decay_rate: float = 0.01):
        """Add memory with embedding."""
        super().add_memory(content, intensity, decay_rate)

        # Generate embedding
        embedding = self.encoder.encode(content, convert_to_tensor=False)
        self.embeddings.append(embedding)

        # Trim embeddings to match memories
        if len(self.embeddings) > len(self.memories):
            self.embeddings = self.embeddings[-len(self.memories):]

    def update(self, dt: float):
        """Update memories and sync embeddings."""
        initial_count = len(self.memories)
        super().update(dt)

        # If memories were removed, remove corresponding embeddings
        if len(self.memories) < initial_count:
            # Rebuild embeddings for remaining memories
            self.embeddings = [
                self.encoder.encode(m.content, convert_to_tensor=False)
                for m in self.memories
            ]

    def search_similar(self, query: str, count: int = 5, min_strength: float = 0.1) -> List[Tuple[Memory, float]]:
        """Search for semantically similar memories.

        Args:
            query: Search query
            count: Number of results
            min_strength: Minimum memory strength

        Returns:
            List of (memory, similarity_score) tuples
        """
        if not self.memories:
            return []

        # Encode query
        query_embedding = self.encoder.encode(query, convert_to_tensor=False)

        # Calculate cosine similarities
        similarities = []
        for i, (memory, embedding) in enumerate(zip(self.memories, self.embeddings)):
            if memory.strength >= min_strength:
                similarity = self._cosine_similarity(query_embedding, embedding)
                similarities.append((memory, float(similarity), i))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        return [(mem, sim) for mem, sim, _ in similarities[:count]]

    def _cosine_similarity(self, a, b):
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

**Tests**:
- Test semantic memory initialization
- Test embedding generation
- Test similarity search
- Test memory update with embedding sync
- Test cosine similarity calculation

---

### Task 5: Meta-Cognition System (45 min)
**Goal**: Enable reflection on own thoughts and processes

**Implementation**:
```python
# src/sociopsi/subsystems/metacognition.py
from typing import Dict, List
from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient

class MetaCognition:
    """Meta-cognitive reflection on thoughts and processes."""

    def __init__(self, event_bus: EventBus, llm_client: OllamaClient):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.recent_thoughts = []
        self.max_thoughts = 5

        # Subscribe to dialogue events
        self.event_bus.subscribe("dialogue.complete", self._on_thought)

    def _on_thought(self, data: dict):
        """Track recent thoughts."""
        thought = data["mediated_thought"]
        harmony = data["harmony"]

        self.recent_thoughts.append({
            "thought": thought,
            "harmony": harmony,
            "archetypal_voices": data.get("archetypal_voices", {}),
        })

        # Keep only recent thoughts
        if len(self.recent_thoughts) > self.max_thoughts:
            self.recent_thoughts.pop(0)

    async def reflect(self, drive_state: dict) -> str:
        """Reflect on recent thoughts and current state.

        Args:
            drive_state: Current drive states

        Returns:
            Meta-cognitive reflection
        """
        if not self.recent_thoughts:
            return "No thoughts to reflect upon yet."

        # Build reflection prompt
        thoughts_summary = "\n".join([
            f"- {t['thought']} (harmony: {t['harmony']:.2f})"
            for t in self.recent_thoughts
        ])

        # Get drive summary
        drive_summary = "\n".join([
            f"- {name}: {state['value']:.2f} ({'below' if state['below_threshold'] else 'above'} threshold)"
            for name, state in drive_state.items()
        ])

        prompt = f"""You are engaging in meta-cognition - reflecting on your own thought processes.

Recent thoughts:
{thoughts_summary}

Current drives:
{drive_summary}

Reflect on:
1. What patterns do you notice in your thoughts?
2. Are your drives being satisfied or frustrated?
3. How is your psychological integration (harmony levels)?
4. What might you need to focus on?

Provide a brief (2-3 sentences) meta-cognitive reflection:"""

        reflection = await self.llm_client.generate(
            prompt,
            temperature=0.7,
            max_tokens=150,
        )

        # Publish meta-cognition event
        self.event_bus.publish("metacognition.reflection", {
            "reflection": reflection,
            "drive_state": drive_state,
            "thought_count": len(self.recent_thoughts),
        })

        return reflection.strip()
```

**Tests**:
- Test meta-cognition initialization
- Test thought tracking
- Test reflection generation
- Test event publishing

---

### Task 6: Audio Integration (30 min)
**Goal**: Integrate audio perception with agent main loop

**Changes to agent.py**:
```python
# Add to imports
from sociopsi.subsystems.perception.audio import AudioPerception
from sociopsi.subsystems.perception.speech import SpeechRecognition
from sociopsi.subsystems.perception.emotion import EmotionDetection
from sociopsi.subsystems.semantic_memory import SemanticMemory
from sociopsi.subsystems.metacognition import MetaCognition

# In __init__:
# Replace MemorySystem with SemanticMemory
self.memory_system = SemanticMemory(max_memories=100, forget_threshold=0.1)

# Add audio perception
self.audio_perception = AudioPerception(self.event_bus)
self.speech_recognition = SpeechRecognition(self.event_bus)
self.emotion_detection = EmotionDetection(self.event_bus)

# Add meta-cognition
self.metacognition = MetaCognition(self.event_bus, self.llm_client)

# Add timers
self.last_audio_process_time = time.time()
self.audio_process_interval = 5.0  # Process audio every 5 seconds
self.last_reflection_time = time.time()
self.reflection_interval = 30.0  # Reflect every 30 seconds

# In _setup_event_handlers:
self.event_bus.subscribe("perception.speech.transcribed", self._on_speech)
self.event_bus.subscribe("perception.emotion.detected", self._on_emotion)

# Event handlers:
def _on_speech(self, data: dict):
    """Handle speech transcription."""
    text = data["text"]
    if self.tui:
        self.tui.update_perception(f"Heard: {text}")
    # Add to memory
    self.memory_system.add_memory(f"User said: {text}", intensity=0.8)
    # Satisfy affiliation drive
    self.drive_system.satisfy_drive("affiliation", amount=0.15)

def _on_emotion(self, data: dict):
    """Handle emotion detection."""
    emotion = data["emotion"]
    valence = data["valence"]
    arousal = data["arousal"]
    if self.tui:
        self.tui.update_perception(f"Emotion: {emotion} (v:{valence:.2f}, a:{arousal:.2f})")
    # High positive valence satisfies affiliation
    if valence > 0.6:
        self.drive_system.satisfy_drive("affiliation", amount=0.1)

# In update():
# Process audio periodically
time_since_audio = current_time - self.last_audio_process_time
if time_since_audio >= self.audio_process_interval:
    await self._process_audio()
    self.last_audio_process_time = current_time

# Reflect periodically
time_since_reflection = current_time - self.last_reflection_time
if time_since_reflection >= self.reflection_interval:
    reflection = await self.metacognition.reflect(drive_state)
    if self.tui:
        self.tui.add_thought(f"[Meta] {reflection}")
    self.last_reflection_time = current_time

async def _process_audio(self):
    """Process recent audio."""
    if not self.audio_perception.is_recording:
        return

    # Get recent audio
    audio_segment = self.audio_perception.get_audio_segment(duration_sec=3.0)
    if audio_segment is None or len(audio_segment) < 1000:
        return

    # Transcribe speech
    result = self.speech_recognition.transcribe(audio_segment)
    text = result["text"].strip()

    # Only process if we got actual speech
    if text and len(text) > 3:
        # Analyze emotion
        self.emotion_detection.analyze_emotion(audio_segment)
```

**Tests**:
- Update integration tests for audio components
- Test audio processing in main loop
- Test meta-cognition reflection

---

### Task 7: Configuration Updates (15 min)
**Goal**: Add audio and meta-cognition config

**config.toml updates**:
```toml
[audio]
sample_rate = 16000
chunk_size = 1024
enabled = true

[speech]
model = "base"  # Whisper model: tiny, base, small, medium, large
enabled = true

[emotion]
enabled = true

[metacognition]
enabled = true
reflection_interval = 30.0  # seconds
```

---

### Task 8: Testing & Integration (45 min)
**Goal**: Comprehensive testing and integration validation

**Tasks**:
1. Write unit tests for all new components
2. Update integration tests
3. Test audio capture and processing
4. Test speech recognition
5. Test emotion detection
6. Test semantic memory search
7. Test meta-cognition reflection
8. Verify all tests pass

---

## Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing ...
    "pyaudio>=0.2.14",
    "openai-whisper>=20231117",
    "librosa>=0.10.1",
    "sentence-transformers>=2.2.2",
]
```

## Testing Strategy

1. **Unit Tests**: Test each component in isolation with mocked dependencies
2. **Integration Tests**: Test audio→speech→emotion pipeline
3. **Performance Tests**: Ensure audio processing doesn't block main loop

## Success Criteria

- [ ] Audio capture working with circular buffer
- [ ] Speech transcription with Whisper
- [ ] Emotion detection from audio features
- [ ] Semantic memory with similarity search
- [ ] Meta-cognitive reflection
- [ ] All tests passing (95+ tests)
- [ ] Type checking passing
- [ ] Audio processing integrated in agent loop

## Implementation Order

1. Audio capture (foundation)
2. Speech recognition (core feature)
3. Emotion detection (enhancement)
4. Semantic memory (memory upgrade)
5. Meta-cognition (reflection)
6. Agent integration (bring it all together)
7. Configuration (settings)
8. Testing (validation)

## Estimated Time Breakdown

- Task 1 (Audio): 30 min
- Task 2 (Speech): 45 min
- Task 3 (Emotion): 45 min
- Task 4 (Semantic): 60 min
- Task 5 (Meta): 45 min
- Task 6 (Integration): 30 min
- Task 7 (Config): 15 min
- Task 8 (Testing): 45 min

**Total**: ~5 hours

## Notes

- Whisper models vary in size: tiny (39M), base (74M), small (244M)
- Use "base" for good balance of speed/accuracy
- Audio processing happens every 5 seconds to avoid blocking
- Meta-cognition reflects every 30 seconds
- Semantic memory uses all-MiniLM-L6-v2 (lightweight, fast)
