# Socio-Psi

**A fully functional Jungian cognitive architecture with LLM-powered multi-voice internal dialogue.**

[![Tests](https://img.shields.io/badge/tests-200%2B-success)]()
[![Version](https://img.shields.io/badge/version-v0.5.0-blue)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## Overview

Socio-Psi is a research platform implementing Jungian archetypal psychology with homeostatic drives, semantic memory, meta-cognitive reflection, autonomous goal-directed behavior, and bidirectional communication. The agent generates rich internal dialogue between multiple archetypal voices (Persona, Shadow, Anima, Self) mediated by an Ego, accepts text and voice commands interpreted through archetypal consultation, autonomously generates goals when needs arise, and plans and executes action sequences to satisfy those goals.

### Key Features

- 🧠 **Archetypal Psychology**: 4 Jungian archetypes with unique personalities
- 💭 **Multi-Voice Dialogue**: LLM-powered internal conversations
- 🎯 **Homeostatic Drives**: Affiliation, Nurturing, Individuation
- 🎬 **Goal-Directed Behavior**: Autonomous goal generation and planning
- ⚡ **Action System**: 6 extensible actions with conflict detection
- 💬 **Bidirectional Communication**: Text and voice commands
- 🎤 **Speech Recognition**: Local Whisper for voice input
- 🔊 **Acoustic Awareness**: Sound environment modulates consciousness
- 🔍 **Semantic Memory**: Vector embeddings for contextual recall
- 🪞 **Meta-Cognition**: Self-reflection on thoughts and processes
- 👁️ **Visual Perception**: Face detection with OpenCV
- 🗣️ **Text-to-Speech**: Speaks thoughts aloud
- 🖥️ **Terminal UI**: Real-time visualization with Textual

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [Ollama](https://ollama.ai/) running locally
- Webcam (optional, for face detection)
- macOS or Linux

### Installation

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone <repository-url>
cd consciousness

# Install dependencies
uv sync
```

### Setup Ollama

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a model (llama2 recommended)
ollama pull llama2

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### Run Socio-Psi

```bash
# Run the agent
uv run python main.py

# Or use the convenience script
./run.sh
```

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=sociopsi

# Run specific test file
uv run pytest tests/unit/test_drives.py -v
```

## System Architecture

```
┌─────────────────────────────────────────────┐
│            Agent Main Loop                   │
│         (Event-Driven, 10 FPS)              │
└───────────┬─────────────────────────────────┘
            │
    ┌───────┴────────┐
    │   Event Bus    │
    └───────┬────────┘
            │
    ┌───────┴──────────────────────────┐
    │                                   │
┌───┴────┐                      ┌──────┴──────┐
│ Drives │                      │ Perception  │
├────────┤                      ├─────────────┤
│• Affil │                      │• Visual     │
│• Nurt  │                      │• Audio*     │
│• Indiv │                      │• Physical   │
└───┬────┘                      └──────┬──────┘
    │                                  │
┌───┴──────────────────────────────┬──┘
│    Archetypal Dialogue System    │
├──────────────────────────────────┤
│ ┌──────┐ ┌────────┐ ┌───────┐   │
│ │Person│ │ Shadow │ │ Anima │   │
│ └───┬──┘ └───┬────┘ └───┬───┘   │
│     └────────┴──────────┘        │
│            ┌───┴────┐             │
│            │  Ego   │             │
│            │Mediator│             │
│            └───┬────┘             │
└────────────────┼──────────────────┘
                 │
     ┌───────────┴──────────────────┐
     │           │           │       │
┌────┴──────┐ ┌─┴────┐ ┌────┴────┐ │
│ Semantic  │ │ Meta-│ │ Goals & │ │
│ Memory    │ │ Cog  │ │Planning │ │
│           │ │      │ │         │ │
│• Search   │ │• Ref │ │• Generate│ │
│• Recall   │ │• Harm│ │• Plan   │ │
│• Context  │ │• Trnd│ │• Execute│ │
└───────────┘ └──────┘ └────┬────┘ │
                            │      │
                    ┌───────┴──────┴───┐
                    │  Action System   │
                    ├──────────────────┤
                    │• speak  • display│
                    │• focus  • volume │
                    │• sound  • wait   │
                    └──────────────────┘

         *Audio is a stub (future)
```

## Core Subsystems

### 1. Drive System
Homeostatic needs that decay over time and trigger behaviors when low:
- **Affiliation**: Satisfied by social interaction (face detection)
- **Nurturing**: Satisfied by caretaking behaviors
- **Individuation**: Satisfied by psychological harmony

### 2. Archetypal Dialogue
LLM-powered multi-voice system with unique personalities:
- **Persona**: Social mask, diplomatic (temp=0.7)
- **Shadow**: Repressed desires, raw honesty (temp=0.8)
- **Anima**: Emotional balance, empathy (temp=0.7)
- **Self**: Wholeness, wisdom (temp=0.6)
- **Ego**: Conscious mediator, synthesizes voices (temp=0.6)

### 3. Semantic Memory
Vector embeddings for similarity-based recall:
- Uses sentence-transformers (all-MiniLM-L6-v2)
- Stores up to 100 memories with intensity-weighted decay
- Contextual retrieval via cosine similarity
- Auto-syncs embeddings with memory updates

### 4. Meta-Cognition
Self-reflection on thoughts and processes:
- Tracks recent thoughts and harmony levels
- Analyzes trends (improving/declining/stable)
- LLM-powered reflection every 30 seconds
- Publishes insights via event bus

### 5. Goal-Directed Behavior
Autonomous goal generation and action planning:
- **Goal Generation**: When drives fall below threshold, archetypes propose goals via LLM
- **Ego Selection**: Ego chooses and prioritizes goals based on urgency and feasibility
- **Action Planning**: Each archetype proposes a plan, Ego synthesizes into coherent sequence
- **Plan Execution**: Actions executed with real-time monitoring and conflict detection
- **Early Success**: Goals complete when success criteria met, skipping remaining steps
- **Parallel Goals**: Multiple non-conflicting goals can execute simultaneously

### 6. Perception
Multi-modal sensory input:
- **Visual**: Face detection (OpenCV + MediaPipe)
- **Physical**: Battery and CPU monitoring
- **Audio**: Ambient sound monitoring with adaptive sampling (1-10 FPS)
- **Sound Classification**: Speech/noise/silence detection via zero-crossing rate
- **Speech Recognition**: Local Whisper (faster-whisper) for voice commands

### 7. Action System
Extensible output behaviors:
- **speak**: Text-to-speech output with emotion
- **update_display**: Modify TUI sections with styling
- **focus_perception**: Direct attention to perception modality
- **adjust_volume**: Change TTS volume (0.0-1.0)
- **emit_sound**: Play non-speech sounds (chime, beep, alert)
- **wait**: Pause for duration or until event condition
- **Conflict Detection**: Actions declare which other actions they conflict with
- **Event-Driven**: All actions publish start/completion events

### 8. Command System
Bidirectional communication with the agent:
- **Text Input**: CommandInput widget in TUI with command history
- **Voice Input**: Push-to-talk speech recognition (faster-whisper)
- **Archetypal Interpretation**: All archetypes interpret command intent via LLM
- **Ego Classification**: Synthesizes perspectives into query/action/goal routing
- **Query Responses**: Answer questions about drives, thoughts, harmony, goals
- **Psychological Responsiveness**: Consultation speed varies by state (threat: 0.5-1s, calm: 2-4s)

### 9. Acoustic Awareness
Sound environment shapes consciousness:
- **Adaptive Sampling**: Audio analysis adjusts from 1-10 FPS based on activity
- **Sound Classification**: Detects speech, noise, or silence
- **Archetypal Modulation**: Acoustic environment modulates archetype activation
  - Silence → Self/Anima boost (contemplation)
  - Speech → Anima/Persona boost (social awareness)
  - Loud noise → Shadow boost (survival mode)
- **Smooth Transitions**: Weight changes interpolated for natural shifts

## Configuration

Edit `config.toml` to customize behavior:

```toml
[drives.affiliation]
decay_rate = 0.01
base_threshold = 0.4

[llm]
model = "llama2"
base_url = "http://localhost:11434"
temperature = 0.7

[memory]
max_memories = 100
embedding_model = "all-MiniLM-L6-v2"

[metacognition]
reflection_interval = 30.0

[goals]
max_active_goals = 3
check_interval = 15.0

[planning]
max_plan_length = 10

[execution]
enabled = true

[commands]
consultation_min_duration = 0.5  # Threat state
consultation_max_duration = 4.0  # Calm state

[audio]
sample_rate = 16000
whisper_model = "base.en"
push_to_talk_key = "space"

[archetypal_modulation]
enabled = true
weight_transition_speed = 0.1
```

## Development

### Project Structure

```
sociopsi/
├── src/sociopsi/
│   ├── core/              # Core systems
│   │   ├── agent.py       # Main agent loop
│   │   ├── event_bus.py   # Pub/sub system
│   │   └── config.py      # Configuration
│   ├── subsystems/        # Cognitive subsystems
│   │   ├── drives.py      # Homeostatic drives
│   │   ├── archetypal_dialogue.py
│   │   ├── semantic_memory.py
│   │   ├── metacognition.py
│   │   ├── archetypes/    # Jungian archetypes
│   │   ├── perception/    # Sensory input
│   │   ├── goals/         # Goal system
│   │   ├── planning/      # Action planning
│   │   ├── execution/     # Plan execution
│   │   └── commands/      # Command processing
│   ├── actions/           # Output behaviors & actions
│   │   ├── action_types.py  # Action definitions
│   │   ├── registry.py      # Action registry
│   │   ├── speak.py         # TTS action
│   │   ├── update_display.py
│   │   ├── focus_perception.py
│   │   ├── adjust_volume.py
│   │   ├── emit_sound.py
│   │   └── wait.py
│   ├── llm/              # LLM integration
│   │   └── ollama_client.py
│   ├── utils/            # Utilities
│   └── presentation/     # TUI
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── docs/                 # Documentation
│   └── plans/            # Implementation plans
├── config.toml           # Configuration
└── main.py              # Entry point
```

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=sociopsi --cov-report=html

# Specific subsystem
uv run pytest tests/unit/test_drives.py -v

# Type checking
uv run pyright src/

# Linting
uv run ruff check src/
```

### Adding New Features

1. **New Archetype**: Extend `Archetype` base class
2. **New Drive**: Add to `config.toml` and `DriveSystem`
3. **New Perception**: Implement in `subsystems/perception/`
4. **New Action**: Create action definition and register in `actions/`
5. **New Goal Type**: Extend goal generation in archetypes
6. **New Planning Strategy**: Modify `ActionPlanner` synthesis

All subsystems communicate via the event bus for loose coupling.

## Performance

- **Main Loop**: ~10 FPS (100ms tick)
- **Dialogue Generation**: Every 10 seconds
- **Meta-Reflection**: Every 30 seconds
- **Memory Operations**: O(n) for search (n ≤ 100)
- **Drive Updates**: O(d) where d = number of drives (3)

## Troubleshooting

### Ollama Connection Issues
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if needed
ollama serve
```

### Camera Not Working
On macOS, grant camera permissions:
1. System Settings → Privacy & Security → Camera
2. Enable for your terminal app
3. Restart the application

### TTS Not Working
TTS (pyttsx3) may fail on some systems:
- The agent will continue without audio
- Check terminal for warning messages
- TTS can be disabled in config: `enabled = false`

### Import Errors
```bash
# Reinstall dependencies
uv sync --reinstall
```

## Testing

- **200+ unit tests** covering all subsystems
- **1 skipped test** (requires camera hardware)
- **100% passing** in automated testing
- **Type-checked** with pyright
- **Linted** with ruff

```bash
# Run full test suite
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/unit/test_semantic_memory.py::test_semantic_search
```

## Documentation

- `STATUS.md`: Comprehensive project status
- `PROGRESS.md`: Phase-by-phase development history
- `docs/plans/`: Detailed implementation plans for each phase
- Inline documentation: Docstrings throughout codebase

## Contributing

This is a research project. Contributions welcome:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `uv run pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Jungian psychology and archetypal theory
- Ollama for local LLM inference
- Sentence Transformers for semantic embeddings
- Textual for beautiful terminal interfaces

## References

- Jung, C. G. (1968). *The Archetypes and the Collective Unconscious*
- Broadbent, D. E. (1977). *The cognitive psychology of human-machine interaction*
- Minsky, M. (1988). *The Society of Mind*

## Contact

For questions or collaboration: [Your contact info]

## Status

**Version**: v0.5.0-phase5
**Status**: ✅ Social Interaction & Audio Perception Complete
**Tests**: 200+/200+ passing
**Last Updated**: 2026-02-04

---

Built with ❤️ and 🧠 by [Your Name]
