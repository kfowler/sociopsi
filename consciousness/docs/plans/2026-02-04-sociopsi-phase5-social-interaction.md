# Phase 5: Social Interaction & Audio Perception

**Date**: 2026-02-04
**Status**: Design Complete, Ready for Implementation
**Estimated Effort**: 20-28 hours

## Overview

Phase 5 transforms the agent from autonomous observer to interactive participant. The agent will accept natural language commands via text and voice, interpret them through archetypal consultation, and respond appropriately. Additionally, the agent gains embodied acoustic awareness through ambient sound monitoring that modulates archetypal activation.

### Goals

1. **Bidirectional Communication**: Users can guide the agent through natural language
2. **Archetypal Command Interpretation**: Commands understood through multiple psychological perspectives
3. **Psychological State Responsiveness**: Consultation speed reflects threat vs calm states
4. **Embodied Acoustic Awareness**: Ambient sound shapes archetypal activation
5. **Multi-Modal Input**: Text (TUI) and voice (speech recognition) inputs
6. **Natural Language Understanding**: Free-form commands, not rigid syntax

### Core Capabilities

- Text input via TUI (dedicated command section)
- Voice input via local Whisper speech recognition (push-to-talk)
- Archetypal command interpretation (all archetypes weigh in on intent)
- Ego synthesis of command classification (query/action/goal)
- State-dependent consultation speed (threat: 0.5-1s, normal: 1-2s, calm: 2-4s)
- Ambient sound monitoring (speech/non-speech, volume, silence)
- Archetypal activation modulation based on acoustic environment
- Query handler for state questions (drives, thoughts, memories)

## Architecture

### New Components

```
Phase 5 Components
├── Command Input System
│   ├── TextInput (TUI widget)
│   ├── SpeechInput (faster-whisper)
│   └── CommandProcessor (unified handler)
├── Command Interpretation
│   ├── ArchetypalInterpreter (LLM-based intent understanding)
│   ├── EgoClassifier (synthesizes into query/action/goal)
│   └── PsychologicalStateCalculator (determines consultation duration)
├── Audio Perception (expand stub)
│   ├── AudioCapture (continuous buffering)
│   ├── AdaptiveSampler (activity-based frequency)
│   ├── SoundClassifier (speech/noise/silence detection)
│   └── ArchetypalModulator (acoustic → archetype weights)
└── Response System
    ├── QueryHandler (state queries)
    ├── ActionExecutor (existing - direct actions)
    └── GoalManager (existing - goal commands)
```

### Event Flow

```
Text Input Flow:
User types → TextInput widget → command.received event →
  ArchetypalInterpreter → Ego synthesis → classification →
  route to handler → execute → response

Voice Input Flow:
User presses Space → SpeechInput activates → Whisper transcription →
  command.received event → (same as text flow)

Ambient Sound Flow:
AudioCapture → AdaptiveSampler → SoundClassifier →
  perception.audio.ambient event → ArchetypalModulator →
  archetype weights updated → influences next consultation
```

### Integration with Existing Systems

- **Event Bus**: All command/audio events published
- **Archetypal Dialogue**: Existing archetypes interpret commands
- **Ego**: Existing Ego synthesizes command classifications
- **Action System**: Existing actions execute from commands
- **Goal System**: Existing goal system handles goal commands
- **Drive System**: Ambient sound can satisfy affiliation drive
- **Memory**: Commands and responses stored as memories

## Subsystem Designs

### 1. Text Input System

**Component**: `TextInput` (Textual widget)

```python
class TextInput(Widget):
    """Command input widget at bottom of TUI."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.history: List[str] = []
        self.history_index = 0

    def on_submit(self, text: str):
        """User pressed Enter."""
        self.event_bus.publish("command.received", {
            "text": text,
            "source": "text",
            "timestamp": time.time()
        })
        self.history.append(text)
        self.clear()

    def on_key(self, key: str):
        """Handle up/down for history navigation."""
        if key == "up":
            self.show_history_prev()
        elif key == "down":
            self.show_history_next()
```

**Features**:
- Always visible at bottom of TUI
- Command history (up/down arrow navigation)
- Clear after submit
- Publish `command.received` event

### 2. Speech Input System

**Component**: `SpeechInput` (faster-whisper integration)

```python
class SpeechInput:
    """Voice command transcription using local Whisper."""

    def __init__(self, event_bus: EventBus, config: Config):
        self.event_bus = event_bus
        self.model_name = config.get("audio.whisper_model", "base.en")
        self.model = None  # Lazy load
        self.is_recording = False
        self.audio_buffer = []

    async def start_recording(self):
        """Activated by Space key press."""
        self.is_recording = True
        self.audio_buffer.clear()
        self.event_bus.publish("speech.recording.started", {})

    async def stop_recording(self):
        """Activated by Space key release."""
        self.is_recording = False

        # Transcribe buffered audio
        text = await self.transcribe(self.audio_buffer)

        if text:
            self.event_bus.publish("command.received", {
                "text": text,
                "source": "voice",
                "timestamp": time.time()
            })

        self.event_bus.publish("speech.recording.stopped", {
            "transcribed": text or ""
        })

    async def transcribe(self, audio_data: bytes) -> str:
        """Use faster-whisper to transcribe."""
        if not self.model:
            self._load_model()

        segments, info = self.model.transcribe(audio_data)
        return " ".join([segment.text for segment in segments])
```

**Features**:
- Push-to-talk activation (Space key)
- Local Whisper model (base.en for speed)
- Lazy model loading (only when first used)
- Publishes same `command.received` event as text
- Visual indicator in TUI when recording

**Future Enhancement**: Always-transcribe mode where all detected speech gets transcribed, archetypal consultation determines if it's directed at agent or ambient context.

### 3. Command Processor & Archetypal Interpretation

**Component**: `CommandProcessor`

```python
class CommandProcessor:
    """Processes commands through archetypal consultation."""

    def __init__(self, event_bus: EventBus, archetypes: List[Archetype],
                 ego: Ego, drive_system: DriveSystem):
        self.event_bus = event_bus
        self.archetypes = archetypes
        self.ego = ego
        self.drive_system = drive_system

        event_bus.subscribe("command.received", self.on_command)

    async def on_command(self, data: dict):
        """Handle incoming command."""
        command_text = data["text"]

        # Calculate psychological state
        state = self._calculate_state()
        consultation_duration = self._get_consultation_duration(state)

        # Archetypal interpretation
        interpretations = await self._archetypal_interpretation(
            command_text, consultation_duration
        )

        # Ego synthesis
        classification = await self._ego_classification(
            command_text, interpretations
        )

        # Route to handler
        await self._route_command(classification)

    def _calculate_state(self) -> str:
        """Determine psychological state: threat/normal/calm."""
        drives = self.drive_system.get_all_drives()
        avg_level = sum(d.level for d in drives) / len(drives)
        harmony = self.ego.last_harmony_level  # From last dialogue

        if avg_level < 0.3 or harmony < 0.3:
            return "threat"
        elif avg_level > 0.7 and harmony > 0.7:
            return "calm"
        else:
            return "normal"

    def _get_consultation_duration(self, state: str) -> float:
        """Map state to consultation duration."""
        durations = {
            "threat": random.uniform(0.5, 1.0),
            "normal": random.uniform(1.0, 2.0),
            "calm": random.uniform(2.0, 4.0)
        }
        return durations[state]

    async def _archetypal_interpretation(self, command: str,
                                          duration: float) -> List[dict]:
        """Each archetype interprets command intent."""
        interpretations = []

        for archetype in self.archetypes:
            prompt = f"""The user said: "{command}"

From your perspective as {archetype.name}, interpret this command:
- What does the user want?
- What is their intent/motivation?
- Is this a query (asking for information), an action (do something), or a goal (pursue over time)?
- Rate your confidence (0-1)

Respond in 1-2 sentences."""

            response = await archetype.generate(prompt)

            interpretations.append({
                "archetype": archetype.name,
                "interpretation": response,
                "timestamp": time.time()
            })

        # Simulate consultation duration
        await asyncio.sleep(duration)

        return interpretations

    async def _ego_classification(self, command: str,
                                    interpretations: List[dict]) -> dict:
        """Ego synthesizes archetypal perspectives into classification."""
        perspectives = "\n".join([
            f"- {i['archetype']}: {i['interpretation']}"
            for i in interpretations
        ])

        prompt = f"""User command: "{command}"

Archetypal perspectives:
{perspectives}

Synthesize these perspectives into a classification:
- Type: query | action | goal
- Intent: (one sentence describing what user wants)
- Parameters: (extract any relevant parameters like drive names, values, etc.)
- Confidence: (0-1, how clear is this classification)

Format as JSON."""

        response = await self.ego.generate(prompt)
        classification = self._parse_classification(response)

        self.event_bus.publish("command.classified", classification)
        return classification

    async def _route_command(self, classification: dict):
        """Route to appropriate handler."""
        cmd_type = classification["type"]

        if cmd_type == "query":
            self.event_bus.publish("command.query", classification)
        elif cmd_type == "action":
            self.event_bus.publish("command.action", classification)
        elif cmd_type == "goal":
            self.event_bus.publish("command.goal", classification)
```

**Key Design Points**:
- Every command goes through archetypal consultation
- Consultation duration varies with psychological state
- Each archetype provides interpretation via LLM
- Ego synthesizes into classification (query/action/goal)
- Classification published to event bus for routing

### 4. Audio Perception System

**Component**: `AudioPerception` (expand existing stub)

```python
class AudioPerception:
    """Ambient sound monitoring and analysis."""

    def __init__(self, event_bus: EventBus, config: Config):
        self.event_bus = event_bus
        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.chunk_size = config.get("audio.chunk_size", 1024)
        self.buffer_seconds = config.get("audio.buffer_seconds", 6.0)

        self.buffer = CircularBuffer(
            size=int(self.sample_rate * self.buffer_seconds)
        )
        self.adaptive_sampler = AdaptiveSampler()
        self.sound_classifier = SoundClassifier()

        self.is_running = False
        self.stream = None

    async def start(self):
        """Begin audio capture."""
        self.is_running = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self._audio_callback
        )
        self.stream.start()

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk."""
        self.buffer.append(indata)

    async def update(self, dt: float):
        """Adaptive sampling and classification."""
        if not self.is_running:
            return

        # Should we analyze this frame?
        if not self.adaptive_sampler.should_sample():
            return

        # Get recent audio
        audio_data = self.buffer.get_recent(duration=1.0)

        # Classify sound
        classification = self.sound_classifier.classify(audio_data)

        # Publish ambient sound event
        self.event_bus.publish("perception.audio.ambient", {
            "type": classification["type"],  # "speech" | "noise" | "silence"
            "volume": classification["volume"],  # 0.0 - 1.0
            "confidence": classification["confidence"]
        })

        # Update adaptive sampler
        self.adaptive_sampler.update(classification)
```

**Component**: `AdaptiveSampler`

```python
class AdaptiveSampler:
    """Adjusts audio analysis frequency based on activity."""

    def __init__(self):
        self.current_fps = 3.0  # Start at baseline
        self.min_fps = 1.0
        self.max_fps = 10.0
        self.idle_fps = 3.0
        self.last_sample_time = 0

    def should_sample(self) -> bool:
        """Determine if we should analyze this frame."""
        current_time = time.time()
        interval = 1.0 / self.current_fps

        if current_time - self.last_sample_time >= interval:
            self.last_sample_time = current_time
            return True
        return False

    def update(self, classification: dict):
        """Adjust sampling rate based on activity."""
        sound_type = classification["type"]
        volume = classification["volume"]

        if sound_type == "speech" or volume > 0.5:
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
```

**Component**: `SoundClassifier`

```python
class SoundClassifier:
    """Classifies audio into speech/noise/silence."""

    def __init__(self):
        self.silence_threshold = 0.02  # RMS threshold
        self.speech_detector = None  # Could use webrtcvad or similar

    def classify(self, audio_data: np.ndarray) -> dict:
        """Classify 1 second of audio."""
        # Calculate volume (RMS)
        volume = np.sqrt(np.mean(audio_data**2))

        # Detect silence
        if volume < self.silence_threshold:
            return {
                "type": "silence",
                "volume": 0.0,
                "confidence": 0.95
            }

        # Detect speech vs non-speech
        # For MVP: simple heuristic based on zero-crossing rate
        # Future: Use webrtcvad or deep learning model
        zcr = self._zero_crossing_rate(audio_data)
        is_speech = 0.05 < zcr < 0.3  # Speech has moderate ZCR

        return {
            "type": "speech" if is_speech else "noise",
            "volume": min(1.0, volume / 0.1),  # Normalize
            "confidence": 0.7  # Lower for heuristic
        }

    def _zero_crossing_rate(self, audio: np.ndarray) -> float:
        """Calculate zero-crossing rate."""
        return np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio))
```

**Future Enhancement (Phase 6+)**: Rich sound classification using deep learning models to detect specific events (door opening, footsteps, laughter, etc.).

### 5. Archetypal Modulation System

**Component**: `ArchetypalModulator`

```python
class ArchetypalModulator:
    """Modulates archetype activation based on acoustic environment."""

    def __init__(self, event_bus: EventBus, archetypes: Dict[str, Archetype]):
        self.event_bus = event_bus
        self.archetypes = archetypes
        self.base_weights = {name: 1.0 for name in archetypes}
        self.current_weights = self.base_weights.copy()

        event_bus.subscribe("perception.audio.ambient", self.on_ambient_sound)

    def on_ambient_sound(self, data: dict):
        """Adjust archetype weights based on acoustic environment."""
        sound_type = data["type"]
        volume = data["volume"]

        # Reset to base
        new_weights = self.base_weights.copy()

        if sound_type == "silence":
            # Quiet contemplation - Self more active
            new_weights["Self"] = 1.5
            new_weights["Anima"] = 1.2
            new_weights["Persona"] = 0.8
            new_weights["Shadow"] = 0.7

        elif sound_type == "speech":
            # Social environment - Anima and Persona more active
            new_weights["Anima"] = 1.4
            new_weights["Persona"] = 1.3
            new_weights["Self"] = 0.9
            new_weights["Shadow"] = 0.8

        elif sound_type == "noise" and volume > 0.7:
            # Loud/chaotic - Shadow more active (survival mode)
            new_weights["Shadow"] = 1.6
            new_weights["Persona"] = 1.1
            new_weights["Anima"] = 0.8
            new_weights["Self"] = 0.7

        elif sound_type == "noise":
            # Moderate ambient noise - balanced with slight Persona emphasis
            new_weights["Persona"] = 1.2

        # Smooth transition (don't snap weights)
        self.current_weights = self._interpolate_weights(
            self.current_weights, new_weights, alpha=0.1
        )

        # Publish weight update
        self.event_bus.publish("archetypes.weights.updated", {
            "weights": self.current_weights.copy()
        })

    def get_weight(self, archetype_name: str) -> float:
        """Get current weight for archetype."""
        return self.current_weights.get(archetype_name, 1.0)

    def _interpolate_weights(self, current: dict, target: dict,
                              alpha: float) -> dict:
        """Smooth weight transitions."""
        return {
            name: current[name] * (1 - alpha) + target[name] * alpha
            for name in current
        }
```

**Key Design Points**:
- Acoustic environment modulates archetype activation weights
- Silence → Self and Anima stronger (contemplation, empathy)
- Speech → Anima and Persona stronger (social awareness)
- Loud noise → Shadow stronger (survival, alertness)
- Smooth transitions prevent jarring shifts
- Weights affect archetype participation in consultations

### 6. Query Handler System

**Component**: `QueryHandler`

```python
class QueryHandler:
    """Handles state query commands."""

    def __init__(self, event_bus: EventBus, agent: SocioPsiAgent):
        self.event_bus = event_bus
        self.agent = agent

        event_bus.subscribe("command.query", self.on_query)

    async def on_query(self, classification: dict):
        """Handle query command."""
        intent = classification["intent"]
        params = classification.get("parameters", {})

        # Determine query type
        if "drive" in intent.lower():
            response = self._query_drives()
        elif "thought" in intent.lower() or "thinking" in intent.lower():
            response = self._query_thoughts()
        elif "memory" in intent.lower() or "remember" in intent.lower():
            response = self._query_memories(params)
        elif "harmony" in intent.lower() or "integration" in intent.lower():
            response = self._query_harmony()
        elif "goal" in intent.lower():
            response = self._query_goals()
        else:
            response = self._query_general_state()

        # Publish response
        self.event_bus.publish("command.response", {
            "text": response,
            "query": intent
        })

    def _query_drives(self) -> str:
        """Return current drive levels."""
        drives = self.agent.drive_system.get_all_drives()
        lines = ["Current drives:"]
        for drive in drives:
            status = "✓" if drive.level > drive.threshold else "✗"
            lines.append(f"  {status} {drive.name}: {drive.level:.2f}")
        return "\n".join(lines)

    def _query_thoughts(self) -> str:
        """Return recent thoughts."""
        recent = self.agent.memory_system.get_recent_memories(limit=3)
        if not recent:
            return "No recent thoughts."
        lines = ["Recent thoughts:"]
        for mem in recent:
            lines.append(f"  - {mem.content}")
        return "\n".join(lines)

    def _query_memories(self, params: dict) -> str:
        """Search memories by query."""
        query = params.get("query", "")
        if not query:
            return self._query_thoughts()  # Fallback

        similar = self.agent.memory_system.search_similar(query, limit=3)
        if not similar:
            return f"No memories found for '{query}'."

        lines = [f"Memories related to '{query}':"]
        for mem, score in similar:
            lines.append(f"  - {mem.content} (relevance: {score:.2f})")
        return "\n".join(lines)

    def _query_harmony(self) -> str:
        """Return current harmony level."""
        harmony = self.agent.ego.last_harmony_level
        trend = self.agent.metacognition.calculate_harmony_trend()
        return f"Harmony: {harmony:.2f} (trend: {trend})"

    def _query_goals(self) -> str:
        """Return active goals."""
        active = self.agent.goal_manager.get_active_goals()
        if not active:
            return "No active goals."
        lines = ["Active goals:"]
        for goal in active:
            lines.append(f"  - {goal.description} (priority: {goal.priority:.2f})")
        return "\n".join(lines)

    def _query_general_state(self) -> str:
        """General state overview."""
        drives = self._query_drives()
        thoughts = self._query_thoughts()
        return f"{drives}\n\n{thoughts}"
```

### 7. TUI Integration

**Updates to `SocioPsiTUI`**:

```python
class SocioPsiTUI(App):
    """Enhanced TUI with command input."""

    def compose(self):
        yield Header()
        yield Container(
            DriveDisplay(id="drives"),
            PerceptionDisplay(id="perception"),
            MonologueDisplay(id="monologue"),
            CommandInput(id="command_input"),  # NEW
            CommandHistory(id="command_history"),  # NEW (optional)
            id="main_container"
        )
        yield Footer()

    def on_mount(self):
        # Subscribe to command response events
        self.agent.event_bus.subscribe("command.response",
                                        self.on_command_response)
        self.agent.event_bus.subscribe("speech.recording.started",
                                        self.on_recording_started)
        self.agent.event_bus.subscribe("speech.recording.stopped",
                                        self.on_recording_stopped)

    def on_command_response(self, data: dict):
        """Display command response in monologue."""
        response_text = data["text"]
        self.query_one("#monologue").add_message(f"[Agent] {response_text}")

    def on_recording_started(self, data: dict):
        """Visual indicator that recording is active."""
        self.query_one("#command_input").add_class("recording")

    def on_recording_stopped(self, data: dict):
        """Remove recording indicator."""
        self.query_one("#command_input").remove_class("recording")
        transcribed = data.get("transcribed", "")
        if transcribed:
            self.query_one("#command_input").set_text(transcribed)
```

**CommandInput Widget**:

```python
class CommandInput(Static):
    """Command input widget with history."""

    def compose(self):
        yield Label("Command:")
        yield Input(placeholder="Type a command or press Space to speak...",
                    id="input_field")

    def on_input_submitted(self, event):
        """User pressed Enter."""
        text = event.value
        if text.strip():
            self.post_message(CommandSubmitted(text))
            event.input.value = ""  # Clear
```

## Implementation Tasks

### Task 1: Text Command Input (~2-3 hours)

**Goal**: Add text input to TUI and basic command processing.

**Subtasks**:
1. Create `CommandInput` widget in `presentation/tui.py`
2. Add input section to TUI layout (bottom)
3. Implement command history (up/down arrows)
4. Wire up to event bus (`command.received` event)
5. Add visual feedback for command submission

**Deliverables**:
- Text input widget functional in TUI
- Commands publish to event bus
- Command history navigation works
- Tests: widget rendering, event publishing, history

### Task 2: Command Processor & Archetypal Interpretation (~4-5 hours)

**Goal**: Process commands through archetypal consultation.

**Subtasks**:
1. Create `CommandProcessor` in `subsystems/commands/processor.py`
2. Implement psychological state calculation (threat/normal/calm)
3. Implement archetypal interpretation (each archetype via LLM)
4. Implement Ego classification synthesis
5. Add consultation duration variation (0.5-1s / 1-2s / 2-4s)
6. Wire up to existing archetypes and Ego

**Deliverables**:
- `CommandProcessor` class operational
- All commands go through archetypal consultation
- Ego synthesizes classification (query/action/goal)
- Consultation speed varies with psychological state
- Tests: state calculation, interpretation, classification

### Task 3: Query Handler (~2-3 hours)

**Goal**: Answer user queries about agent state.

**Subtasks**:
1. Create `QueryHandler` in `subsystems/commands/query_handler.py`
2. Implement drive queries
3. Implement thought/memory queries
4. Implement harmony/goal queries
5. Format responses as readable text
6. Publish responses to event bus

**Deliverables**:
- `QueryHandler` handles all query types
- Responses formatted and published
- Tests: each query type, edge cases (no data)

### Task 4: Action & Goal Command Routing (~2-3 hours)

**Goal**: Route action/goal commands to existing systems.

**Subtasks**:
1. Create action command handler (wraps `ActionExecutor`)
2. Create goal command handler (wraps `GoalManager`)
3. Extract parameters from classification
4. Map natural language to actions/goals
5. Handle errors gracefully (unknown action, invalid params)

**Deliverables**:
- Action commands execute actions
- Goal commands create goals
- Parameter extraction works
- Tests: routing, parameter mapping, errors

### Task 5: Audio Perception System (~5-6 hours)

**Goal**: Ambient sound monitoring with adaptive sampling.

**Subtasks**:
1. Expand `AudioPerception` stub in `subsystems/perception/audio.py`
2. Implement `AdaptiveSampler` (activity-based FPS)
3. Implement `SoundClassifier` (speech/noise/silence detection)
4. Add audio capture with sounddevice
5. Publish `perception.audio.ambient` events
6. Test with real audio (verify classification accuracy)

**Deliverables**:
- Audio capture and buffering working
- Adaptive sampling adjusts frequency
- Sound classification (basic but functional)
- Events published
- Tests: sampling logic, classification, events

### Task 6: Archetypal Modulation (~2-3 hours)

**Goal**: Acoustic environment modulates archetype weights.

**Subtasks**:
1. Create `ArchetypalModulator` in `subsystems/archetypes/modulator.py`
2. Subscribe to `perception.audio.ambient` events
3. Implement weight calculation (silence/speech/noise → weights)
4. Smooth weight transitions (interpolation)
5. Integrate with `ArchetypalDialogue` (weights affect participation)

**Deliverables**:
- Archetype weights adjust based on sound
- Smooth transitions prevent jarring shifts
- Weights affect consultation participation
- Tests: weight calculation, interpolation, integration

### Task 7: Speech Recognition (~3-4 hours)

**Goal**: Voice commands via local Whisper.

**Subtasks**:
1. Create `SpeechInput` in `subsystems/commands/speech_input.py`
2. Integrate faster-whisper library
3. Implement push-to-talk (Space key)
4. Add recording indicator in TUI
5. Transcribe and publish `command.received`
6. Handle errors (model load failure, transcription failure)

**Deliverables**:
- Push-to-talk voice input works
- Whisper transcribes accurately
- Same event flow as text commands
- Visual feedback during recording
- Tests: recording lifecycle, transcription

### Task 8: Agent Integration (~2-3 hours)

**Goal**: Wire all Phase 5 systems into agent main loop.

**Subtasks**:
1. Add `CommandProcessor` to agent initialization
2. Add `QueryHandler` to agent initialization
3. Add expanded `AudioPerception` to agent initialization
4. Add `ArchetypalModulator` to agent initialization
5. Add `SpeechInput` to agent initialization
6. Wire all event subscriptions
7. Update agent update loop (audio perception updates)

**Deliverables**:
- All Phase 5 systems initialized in agent
- Event subscriptions connected
- Audio perception updates each frame
- Full integration operational

### Task 9: Configuration (~1 hour)

**Goal**: Add Phase 5 config sections.

**Subtasks**:
1. Add `[commands]` section (enabled flag)
2. Add `[audio]` section updates (whisper_model, push_to_talk_key)
3. Add `[archetypal_modulation]` section (weight multipliers)
4. Document all new config options

**Deliverables**:
- config.toml updated
- All Phase 5 features configurable
- Documentation in comments

### Task 10: Testing & Documentation (~2-3 hours)

**Goal**: Comprehensive testing and docs.

**Subtasks**:
1. Write integration tests (end-to-end command flow)
2. Write unit tests for all new components
3. Update PROGRESS.md with Phase 5 completion
4. Update STATUS.md with new capabilities
5. Update README.md with command examples
6. Run full test suite, verify all passing

**Deliverables**:
- All tests passing (target: 200+ total)
- PROGRESS.md updated
- STATUS.md updated
- README.md updated

## Testing Strategy

### Unit Tests

**CommandProcessor** (~10 tests):
- Psychological state calculation (threat/normal/calm)
- Consultation duration mapping
- Archetypal interpretation mock responses
- Ego classification synthesis
- Command routing

**QueryHandler** (~8 tests):
- Each query type (drives, thoughts, memories, harmony, goals)
- Empty state handling
- Response formatting

**AudioPerception** (~8 tests):
- Audio capture and buffering
- Adaptive sampling logic
- Sound classification (speech/noise/silence)
- Event publishing

**ArchetypalModulator** (~6 tests):
- Weight calculation for each sound type
- Weight interpolation
- Integration with dialogue system

**SpeechInput** (~6 tests):
- Recording lifecycle (start/stop)
- Transcription (mocked Whisper)
- Event publishing
- Error handling

### Integration Tests

**End-to-End Command Flow** (~8 tests):
- Text command → archetypal consultation → query response
- Text command → action execution
- Text command → goal creation
- Voice command → transcription → execution
- Psychological state affects consultation duration
- Ambient sound → archetype weight modulation → consultation

### Manual Testing

- Type various commands, verify responses
- Speak commands via push-to-talk, verify transcription
- Test in different acoustic environments (quiet, speech, noise)
- Verify archetypal weights shift appropriately
- Test psychological state transitions (low drives → fast consultation)

## Success Criteria

Phase 5 is complete when:

1. ✓ Users can type commands in TUI
2. ✓ Users can speak commands via push-to-talk (Space key)
3. ✓ All commands interpreted through archetypal consultation
4. ✓ Ego synthesizes command classification (query/action/goal)
5. ✓ Consultation speed varies with psychological state (threat/normal/calm)
6. ✓ Query commands return accurate state information
7. ✓ Action commands execute existing actions
8. ✓ Goal commands create goals in goal system
9. ✓ Ambient sound monitored continuously
10. ✓ Sound classification detects speech/noise/silence
11. ✓ Archetypal weights modulated by acoustic environment
12. ✓ All tests passing (target: 200+ total)
13. ✓ Documentation updated

## Configuration

```toml
[commands]
enabled = true
consultation_min_duration = 0.5  # Threat state
consultation_max_duration = 4.0  # Calm state

[audio]
enabled = true
sample_rate = 16000
chunk_size = 1024
buffer_seconds = 6.0
whisper_model = "base.en"  # Options: tiny, base, small, medium
push_to_talk_key = "space"

[archetypal_modulation]
enabled = true
weight_transition_speed = 0.1  # Interpolation alpha
silence_self_boost = 1.5
speech_anima_boost = 1.4
noise_shadow_boost = 1.6
```

## Dependencies

**New**:
- `faster-whisper` - Local speech recognition
- `sounddevice` - Audio capture
- `numpy` - Audio signal processing

**Existing** (no changes):
- All Phase 1-4 dependencies

## Future Enhancements (Phase 6+)

### Always-Transcribe Mode
Currently: Push-to-talk activates transcription
Future: All detected speech transcribed, archetypal consultation determines if directed at agent vs ambient context

### Rich Sound Classification
Currently: Basic speech/noise/silence detection
Future: Deep learning model for specific events (door, footsteps, laughter, applause, keyboard typing)

### Emotional Tone Detection
Currently: No emotion detection
Future: Analyze ambient speech for emotional valence without transcribing words

### Command Learning
Currently: Static command understanding
Future: Learn from user corrections ("No, I meant X"), adapt classification over time

### Multi-Turn Dialogue
Currently: Single-shot commands and responses
Future: Maintain conversation context across multiple exchanges

## Timeline Estimate

- Task 1 (Text Input): ~2-3 hours
- Task 2 (Command Processor): ~4-5 hours
- Task 3 (Query Handler): ~2-3 hours
- Task 4 (Action/Goal Routing): ~2-3 hours
- Task 5 (Audio Perception): ~5-6 hours
- Task 6 (Archetypal Modulation): ~2-3 hours
- Task 7 (Speech Recognition): ~3-4 hours
- Task 8 (Agent Integration): ~2-3 hours
- Task 9 (Configuration): ~1 hour
- Task 10 (Testing/Docs): ~2-3 hours

**Total**: ~25-35 hours of development

## Notes

- This phase significantly increases complexity (speech recognition, audio processing)
- faster-whisper's base.en model is good balance of speed/accuracy
- Archetypal modulation creates rich emergent behavior (environment shapes consciousness)
- Push-to-talk for MVP prevents accidental transcription, but always-transcribe is more immersive
- Command interpretation through archetypes is psychologically rich but adds latency
- Consider caching common command classifications if performance becomes issue
- Ambient sound monitoring should not satisfy drives directly (unlike face detection) - it modulates archetypal activation instead
