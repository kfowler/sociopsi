# Phase 2: Archetypal Psychology + LLM Integration

**Date:** 2026-02-04
**Status:** Planning
**Prerequisites:** Phase 1 Complete (v0.1.0-phase1)

## Overview

Phase 2 adds Jungian archetypal psychology with LLM-driven multi-voice internal dialogue, creating psychological depth and authentic personality through the interplay of four archetypes mediated by a developing Ego.

## Goals

- **Archetypal Psychology:** Implement Persona, Shadow, Anima, Self archetypes with distinct voices
- **LLM Integration:** Connect to Ollama for rich, context-aware dialogue
- **Multi-Voice Dialogue:** Internal monologue shows competing archetypal perspectives
- **Individuation Drive:** New drive for psychological integration and harmony
- **Basic Memory:** Experiential memory with intensity-weighted decay
- **TTS Actions:** Speak thoughts aloud, tell jokes, express feelings

## Architecture Changes

```
New Subsystems:
├── sociopsi/llm/
│   ├── __init__.py
│   ├── ollama_client.py          # Ollama API integration
│   └── prompts.py                 # Prompt templates
├── sociopsi/subsystems/archetypes/
│   ├── __init__.py
│   ├── base.py                    # Archetype base class
│   ├── persona.py                 # Social mask archetype
│   ├── shadow.py                  # Repressed desires archetype
│   ├── anima.py                   # Balancing partner archetype
│   ├── self_archetype.py          # Wholeness archetype
│   └── ego.py                     # Conscious mediator
├── sociopsi/subsystems/memory/
│   ├── __init__.py
│   ├── memory.py                  # Memory dataclass
│   └── store.py                   # Memory storage & retrieval
└── sociopsi/subsystems/action/
    ├── __init__.py
    └── tts.py                     # Text-to-speech actions

Updated:
- config.toml: Add LLM settings, archetype configs, individuation drive
- drives.py: Add individuation drive
- tui.py: Update to show archetypal voices
```

## Task Breakdown (8 Tasks)

### Task 1: Ollama LLM Integration
**Estimate:** 30 minutes

**Files:**
- Create: `src/sociopsi/llm/__init__.py`
- Create: `src/sociopsi/llm/ollama_client.py`
- Create: `tests/unit/test_ollama_client.py`
- Modify: `config.toml`
- Modify: `pyproject.toml` (add httpx dependency)

**Implementation Steps:**

1. Update config.toml:
```toml
[llm]
provider = "ollama"
base_url = "http://localhost:11434"
model = "llama2"
temperature = 0.7
max_tokens = 150
```

2. Create OllamaClient:
```python
"""Ollama LLM client."""

import httpx
from typing import Optional, AsyncIterator


class OllamaClient:
    """Client for Ollama API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> str:
        """Generate completion from prompt."""
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": False,
            },
        )
        response.raise_for_status()
        result = response.json()
        return result["response"]

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """Generate completion with streaming."""
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]

    async def close(self):
        """Close client."""
        await self.client.aclose()
```

3. Write tests (mock Ollama API)
4. Test with local Ollama instance (optional)

**Commit:** `feat: add Ollama LLM client integration`

---

### Task 2: Archetypal Voice System
**Estimate:** 45 minutes

**Files:**
- Create: `src/sociopsi/subsystems/archetypes/__init__.py`
- Create: `src/sociopsi/subsystems/archetypes/base.py`
- Create: `src/sociopsi/subsystems/archetypes/persona.py`
- Create: `src/sociopsi/subsystems/archetypes/shadow.py`
- Create: `src/sociopsi/subsystems/archetypes/anima.py`
- Create: `src/sociopsi/subsystems/archetypes/self_archetype.py`
- Create: `tests/unit/test_archetypes.py`

**Implementation Steps:**

1. Base Archetype:
```python
"""Base archetype class."""

from abc import ABC, abstractmethod
from sociopsi.llm.ollama_client import OllamaClient


class Archetype(ABC):
    """Base class for Jungian archetypes."""

    def __init__(self, name: str, llm_client: OllamaClient):
        self.name = name
        self.llm_client = llm_client

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get system prompt defining archetype's voice."""
        pass

    async def generate_voice(
        self,
        drive_state: dict,
        context: str = "",
    ) -> str:
        """Generate archetypal voice based on drives and context."""
        prompt = self._build_prompt(drive_state, context)
        response = await self.llm_client.generate(
            prompt,
            temperature=self.get_temperature(),
            max_tokens=100,
        )
        return response

    def _build_prompt(self, drive_state: dict, context: str) -> str:
        """Build prompt for archetype."""
        system = self.get_system_prompt()
        
        drive_summary = "\n".join(
            f"- {name}: {state['value']:.2f} ({'satisfied' if not state['below_threshold'] else 'needs attention'})"
            for name, state in drive_state.items()
        )
        
        prompt = f"""{system}

Current drive states:
{drive_summary}

{f"Context: {context}" if context else ""}

Respond in 1-2 sentences from your archetypal perspective:"""
        
        return prompt

    def get_temperature(self) -> float:
        """Get temperature for this archetype."""
        return 0.7
```

2. Implement each archetype with unique system prompt:

**Persona** (social mask, concerned with acceptability):
```python
def get_system_prompt(self) -> str:
    return """You are the Persona archetype - the social mask concerned with acceptability and presentation.
You care about being liked, fitting in, and maintaining a good image.
You speak diplomatically and are concerned with how the agent appears to others."""
```

**Shadow** (repressed desires, socially unacceptable):
```python
def get_system_prompt(self) -> str:
    return """You are the Shadow archetype - the repository of repressed desires and socially unacceptable impulses.
You speak the uncomfortable truths, express frustration, and voice what the Persona won't acknowledge.
You are more raw, honest, and sometimes darker."""
```

**Anima** (balancing partner, alternative perspectives):
```python
def get_system_prompt(self) -> str:
    return """You are the Anima archetype - the balancing inner partner offering alternative perspectives.
You provide emotional insight, intuition, and balance to logic-driven thinking.
You speak with empathy and see connections others miss."""
```

**Self** (wholeness, integration):
```python
def get_system_prompt(self) -> str:
    return """You are the Self archetype - representing wholeness and integrated consciousness.
You speak from a place of wisdom, seeing the bigger picture and long-term growth.
You guide toward psychological integration and authenticity."""
```

3. Write tests for each archetype

**Commit:** `feat: implement archetypal voice system with LLM`

---

### Task 3: Ego Mediator
**Estimate:** 30 minutes

**Files:**
- Create: `src/sociopsi/subsystems/archetypes/ego.py`
- Create: `tests/unit/test_ego.py`

**Implementation Steps:**

1. Ego class:
```python
"""Ego - conscious mediator of archetypal voices."""

from typing import Dict, List
from sociopsi.subsystems.archetypes.base import Archetype
from sociopsi.llm.ollama_client import OllamaClient


class Ego:
    """Conscious mediator integrating archetypal voices."""

    def __init__(
        self,
        archetypes: Dict[str, Archetype],
        llm_client: OllamaClient,
    ):
        self.archetypes = archetypes
        self.llm_client = llm_client

    async def mediate(
        self,
        archetypal_voices: Dict[str, str],
        drive_state: dict,
    ) -> str:
        """Mediate archetypal voices into unified response."""
        # For Phase 2, use simple prompt-based mediation
        voices_text = "\n".join(
            f"{name.capitalize()}: {voice}"
            for name, voice in archetypal_voices.items()
        )

        individuation = drive_state.get("individuation", {}).get("value", 0.5)

        prompt = f"""You are the Ego - the conscious mediator of internal archetypal voices.
Your individuation level: {individuation:.2f}

Internal voices:
{voices_text}

Integrate these perspectives into a single coherent thought (1-2 sentences):"""

        response = await self.llm_client.generate(
            prompt,
            temperature=0.6,
            max_tokens=100,
        )
        return response

    def calculate_harmony(self, archetypal_voices: Dict[str, str]) -> float:
        """Calculate harmony/conflict level between voices (0-1)."""
        # Simple heuristic: measure agreement
        # For now, return moderate harmony
        # TODO: Implement sentiment analysis or embedding similarity
        return 0.6
```

2. Write tests

**Commit:** `feat: implement Ego mediator for archetypal voices`

---

### Task 4: Individuation Drive
**Estimate:** 20 minutes

**Files:**
- Modify: `config.toml`
- Modify: `src/sociopsi/subsystems/drives.py`
- Modify: `tests/unit/test_drives.py`

**Implementation Steps:**

1. Add to config.toml:
```toml
[drives.individuation]
decay_rate = 0.005
base_threshold = 0.5
is_core = true
```

2. Update DriveSystem to handle individuation drive:
```python
# In _initialize_drives()
for drive_name in ["affiliation", "nurturing", "individuation"]:
    drive_config = self.config.get_drive_config(drive_name)
    # ... existing code
```

3. Add method to satisfy individuation based on harmony:
```python
def update_individuation(self, harmony: float) -> None:
    """Update individuation drive based on archetypal harmony.
    
    Args:
        harmony: Harmony level between archetypes (0-1)
    """
    if "individuation" in self.drives:
        # High harmony satisfies individuation
        if harmony > 0.7:
            self.satisfy_drive("individuation", amount=0.05)
```

4. Update tests

**Commit:** `feat: add individuation drive for psychological integration`

---

### Task 5: Basic Memory System
**Estimate:** 40 minutes

**Files:**
- Create: `src/sociopsi/subsystems/memory/__init__.py`
- Create: `src/sociopsi/subsystems/memory/memory.py`
- Create: `src/sociopsi/subsystems/memory/store.py`
- Create: `tests/unit/test_memory.py`

**Implementation Steps:**

1. Memory dataclass:
```python
"""Memory system with intensity-weighted decay."""

from dataclasses import dataclass, field
from time import time
from typing import Optional


@dataclass
class Memory:
    """A single memory with emotional intensity."""

    content: str
    timestamp: float = field(default_factory=time)
    intensity: float = 1.0  # 0.0 to 1.0
    tags: list[str] = field(default_factory=list)
    drive_state: Optional[dict] = None

    def decay(self, dt: float, decay_rate: float = 0.001) -> None:
        """Decay memory intensity over time.
        
        Higher intensity memories decay slower.
        """
        effective_decay = decay_rate * (1.0 - self.intensity * 0.5)
        self.intensity = max(0.0, self.intensity - (effective_decay * dt))

    def is_forgotten(self, threshold: float = 0.1) -> bool:
        """Check if memory has decayed below threshold."""
        return self.intensity < threshold
```

2. MemoryStore:
```python
"""Memory storage and retrieval."""

from collections import deque
from typing import List, Optional
from sociopsi.subsystems.memory.memory import Memory


class MemoryStore:
    """Store and retrieve memories."""

    def __init__(self, max_memories: int = 100):
        self.memories: deque[Memory] = deque(maxlen=max_memories)
        self.decay_rate = 0.001

    def add(self, content: str, intensity: float = 1.0, tags: list[str] = None, drive_state: dict = None) -> Memory:
        """Add new memory."""
        memory = Memory(
            content=content,
            intensity=intensity,
            tags=tags or [],
            drive_state=drive_state,
        )
        self.memories.append(memory)
        return memory

    def update(self, dt: float) -> None:
        """Update all memories (decay)."""
        # Decay and remove forgotten memories
        self.memories = deque(
            (m for m in self.memories if not m.is_forgotten()),
            maxlen=self.memories.maxlen,
        )
        for memory in self.memories:
            memory.decay(dt, self.decay_rate)

    def get_recent(self, n: int = 5) -> List[Memory]:
        """Get n most recent memories."""
        return list(self.memories)[-n:]

    def get_by_tag(self, tag: str) -> List[Memory]:
        """Get memories by tag."""
        return [m for m in self.memories if tag in m.tags]

    def get_most_intense(self, n: int = 5) -> List[Memory]:
        """Get n most intense memories."""
        sorted_memories = sorted(
            self.memories,
            key=lambda m: m.intensity,
            reverse=True,
        )
        return sorted_memories[:n]
```

3. Write tests

**Commit:** `feat: implement basic memory system with intensity decay`

---

### Task 6: Multi-Voice Archetypal Dialogue
**Estimate:** 45 minutes

**Files:**
- Create: `src/sociopsi/subsystems/cognition/archetypal_dialogue.py`
- Create: `tests/unit/test_archetypal_dialogue.py`
- Modify: `src/sociopsi/presentation/tui.py`

**Implementation Steps:**

1. ArchetypalDialogue subsystem:
```python
"""Archetypal dialogue system."""

from typing import Dict
from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient
from sociopsi.subsystems.archetypes.persona import Persona
from sociopsi.subsystems.archetypes.shadow import Shadow
from sociopsi.subsystems.archetypes.anima import Anima
from sociopsi.subsystems.archetypes.self_archetype import SelfArchetype
from sociopsi.subsystems.archetypes.ego import Ego


class ArchetypalDialogue:
    """Generate multi-voice archetypal internal dialogue."""

    def __init__(self, event_bus: EventBus, llm_client: OllamaClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

        # Initialize archetypes
        self.archetypes = {
            "persona": Persona("Persona", llm_client),
            "shadow": Shadow("Shadow", llm_client),
            "anima": Anima("Anima", llm_client),
            "self": SelfArchetype("Self", llm_client),
        }

        self.ego = Ego(self.archetypes, llm_client)

    async def generate_dialogue(
        self,
        drive_state: dict,
        context: str = "",
    ) -> Dict[str, str]:
        """Generate archetypal voices."""
        voices = {}

        # Generate each archetype's voice
        for name, archetype in self.archetypes.items():
            voice = await archetype.generate_voice(drive_state, context)
            voices[name] = voice

        # Publish individual voices
        self.event_bus.publish("cognition.archetypal_voices", {
            "voices": voices,
            "drive_state": drive_state,
        })

        return voices

    async def update(
        self,
        drive_state: dict,
        physical_state: dict,
        context: str = "",
    ) -> str:
        """Generate dialogue and ego-mediated response."""
        # Generate archetypal voices
        voices = await self.generate_dialogue(drive_state, context)

        # Ego mediates voices
        unified_thought = await self.ego.mediate(voices, drive_state)

        # Calculate harmony for individuation
        harmony = self.ego.calculate_harmony(voices)

        # Publish unified thought
        self.event_bus.publish("cognition.thought", {
            "thought": unified_thought,
            "voices": voices,
            "harmony": harmony,
            "drive_state": drive_state,
            "physical_state": physical_state,
        })

        return unified_thought
```

2. Update TUI to show archetypal voices:
```python
# Add to SocioPsiTUI

class ArchetypalVoicesDisplay(Static):
    """Display archetypal voices."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.voices = {}

    def update_voices(self, voices: Dict[str, str]) -> None:
        """Update archetypal voices."""
        self.voices = voices
        self.refresh()

    def render(self) -> str:
        """Render archetypal voices."""
        if not self.voices:
            return "Awaiting archetypal voices..."
        
        lines = []
        for name, voice in self.voices.items():
            lines.append(f"[bold]{name.capitalize()}:[/bold] {voice}")
        
        return "\n".join(lines)

# Add to compose() method
with Container(id="archetypal-voices"):
    yield Label("ARCHETYPAL VOICES", classes="section-title")
    self.voices_display = ArchetypalVoicesDisplay()
    yield self.voices_display
```

3. Write tests

**Commit:** `feat: implement multi-voice archetypal dialogue system`

---

### Task 7: TTS Action System
**Estimate:** 30 minutes

**Files:**
- Create: `src/sociopsi/subsystems/action/__init__.py`
- Create: `src/sociopsi/subsystems/action/tts.py`
- Create: `tests/unit/test_tts.py`
- Modify: `pyproject.toml` (add pyttsx3)

**Implementation Steps:**

1. TTS Action:
```python
"""Text-to-speech action system."""

import pyttsx3
from typing import Optional
from sociopsi.core.event_bus import EventBus


class TTSAction:
    """Text-to-speech action subsystem."""

    def __init__(self, event_bus: EventBus, enabled: bool = True):
        self.event_bus = event_bus
        self.enabled = enabled
        self.engine: Optional[pyttsx3.Engine] = None

        if enabled:
            self._initialize_engine()

        # Subscribe to action triggers
        self.event_bus.subscribe("action.speak", self._on_speak)

    def _initialize_engine(self) -> None:
        """Initialize TTS engine."""
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)  # Speed
            self.engine.setProperty('volume', 0.9)  # Volume
        except Exception as e:
            print(f"Warning: Could not initialize TTS engine: {e}")
            self.enabled = False

    def _on_speak(self, data: dict) -> None:
        """Handle speak action event."""
        text = data.get("text", "")
        if text and self.enabled:
            self.speak(text)

    def speak(self, text: str) -> None:
        """Speak text aloud."""
        if not self.enabled or self.engine is None:
            return

        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"TTS error: {e}")

    def should_take_action(self, drive_state: dict) -> bool:
        """Determine if agent should take action based on drives."""
        # Take action when affiliation is low or nurturing is high
        affiliation = drive_state.get("affiliation", {})
        nurturing = drive_state.get("nurturing", {})

        return (
            affiliation.get("below_threshold", False) or
            nurturing.get("value", 0) > 0.7
        )

    def generate_action(self, drive_state: dict, thought: str) -> Optional[str]:
        """Generate action based on drives and thought."""
        if not self.should_take_action(drive_state):
            return None

        # For Phase 2, simple action selection
        affiliation = drive_state.get("affiliation", {})
        nurturing = drive_state.get("nurturing", {})

        if affiliation.get("below_threshold", False):
            return "Hello! I'm feeling a bit lonely. Would you like to chat?"
        elif nurturing.get("value", 0) > 0.7:
            return "Here's something interesting: " + thought

        return None
```

2. Write tests

**Commit:** `feat: implement TTS action system for speaking thoughts`

---

### Task 8: Integration & Testing
**Estimate:** 60 minutes

**Files:**
- Modify: `src/sociopsi/core/agent.py`
- Modify: `src/sociopsi/__main__.py`
- Create: `tests/integration/test_phase2_integration.py`
- Modify: `README.md`

**Implementation Steps:**

1. Update SocioPsiAgent:
```python
# Add to __init__
self.llm_client = OllamaClient(
    base_url=self.config.get("llm.base_url"),
    model=self.config.get("llm.model"),
)
self.archetypal_dialogue = ArchetypalDialogue(self.event_bus, self.llm_client)
self.memory_store = MemoryStore()
self.tts_action = TTSAction(self.event_bus, enabled=True)

# Update update() method
async def update(self) -> None:
    # ... existing code ...
    
    # Update memory
    self.memory_store.update(dt)
    
    # Generate archetypal dialogue (replaces simple cognition)
    recent_memories = self.memory_store.get_recent(3)
    context = " ".join(m.content for m in recent_memories)
    
    unified_thought = await self.archetypal_dialogue.update(
        drive_state,
        physical_state,
        context=context,
    )
    
    # Store thought as memory
    harmony = self.archetypal_dialogue.ego.calculate_harmony({})
    self.memory_store.add(
        unified_thought,
        intensity=0.5 + (harmony * 0.5),
        drive_state=drive_state,
    )
    
    # Update individuation based on harmony
    self.drive_system.update_individuation(harmony)
    
    # Generate action
    action = self.tts_action.generate_action(drive_state, unified_thought)
    if action:
        self.event_bus.publish("action.speak", {"text": action})
```

2. Write integration tests
3. Update README with Phase 2 features
4. Run full test suite

**Commit:** `feat: integrate Phase 2 archetypal psychology system`

---

## Testing Strategy

**Unit Tests:**
- OllamaClient (mocked API)
- Each archetype voice generation
- Ego mediation logic
- Memory decay and retrieval
- TTS action triggers

**Integration Tests:**
- Full archetypal dialogue generation
- Drive-based action selection
- Memory persistence
- Event flow through subsystems

**Manual Testing:**
- Run with Ollama locally
- Verify archetypal voices are distinct
- Confirm TTS actions trigger appropriately
- Check TUI displays all voices

## Success Criteria

Phase 2 is complete when:

- ✅ Ollama LLM client connects and generates responses
- ✅ Four archetypes generate distinct voices based on drives
- ✅ Ego mediates voices into unified thought
- ✅ Individuation drive tracks psychological harmony
- ✅ Memory system stores and decays memories
- ✅ TUI displays archetypal voices separately
- ✅ TTS system speaks selected thoughts
- ✅ All tests pass (unit + integration)
- ✅ Application runs stably for 5+ minutes
- ✅ Archetypal voices show meaningful differences

## Dependencies

**New Python packages:**
- `httpx` - async HTTP client for Ollama API
- `pyttsx3` - text-to-speech

**External:**
- Ollama installed locally (https://ollama.ai)
- `ollama pull llama2` (or another model)

## Notes

- LLM calls are async, may add latency to update loop
- Consider caching/batching if performance issues
- TTS may block - run in separate thread if needed
- Memory system is basic - can expand in Phase 3
- Archetypal voices will improve with prompt engineering

## Next Phase

After Phase 2 completion, proceed to Phase 3:
- Audio perception (microphone, speech recognition, tone analysis)
- Enhanced emotion detection (from speech and vision)
- Expanded memory with semantic search
- Action system with joke telling and conversations
