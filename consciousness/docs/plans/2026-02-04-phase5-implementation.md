# Phase 5: Social Interaction & Audio Perception - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform agent from autonomous observer to interactive participant with text/voice commands and embodied acoustic awareness.

**Architecture:** Command input (text + voice) → archetypal consultation → Ego classification (query/action/goal) → routing → execution. Ambient sound monitoring modulates archetypal activation weights based on acoustic environment.

**Tech Stack:** Textual (TUI widgets), faster-whisper (speech recognition), sounddevice (audio capture), numpy (signal processing), existing LLM/archetypal systems.

---

## Task 1: Text Command Input Widget

**Files:**
- Create: `src/sociopsi/presentation/widgets/command_input.py`
- Modify: `src/sociopsi/presentation/tui.py:50-80`
- Test: `tests/unit/test_command_input.py`

### Step 1: Write failing test for CommandInput widget

```python
# tests/unit/test_command_input.py
import pytest
from sociopsi.presentation.widgets.command_input import CommandInput
from sociopsi.core.event_bus import EventBus


def test_command_input_initialization():
    """CommandInput widget initializes with event bus."""
    event_bus = EventBus()
    widget = CommandInput(event_bus)
    assert widget.event_bus == event_bus
    assert widget.history == []


def test_command_input_submit_publishes_event():
    """Submitting command publishes command.received event."""
    event_bus = EventBus()
    widget = CommandInput(event_bus)

    received_events = []
    event_bus.subscribe("command.received", lambda data: received_events.append(data))

    widget.on_submit("test command")

    assert len(received_events) == 1
    assert received_events[0]["text"] == "test command"
    assert received_events[0]["source"] == "text"


def test_command_input_history():
    """Commands added to history."""
    event_bus = EventBus()
    widget = CommandInput(event_bus)

    widget.on_submit("command 1")
    widget.on_submit("command 2")

    assert len(widget.history) == 2
    assert widget.history[0] == "command 1"
    assert widget.history[1] == "command 2"
```

### Step 2: Run test to verify it fails

```bash
uv run pytest tests/unit/test_command_input.py -v
```

Expected: FAIL with "No module named 'sociopsi.presentation.widgets.command_input'"

### Step 3: Create CommandInput widget

```python
# src/sociopsi/presentation/widgets/command_input.py
"""Command input widget for TUI."""

import time
from typing import List
from textual.widget import Widget
from textual.containers import Container
from textual.widgets import Input, Static
from sociopsi.core.event_bus import EventBus


class CommandInput(Container):
    """Command input widget with history."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize command input.

        Args:
            event_bus: Event bus for publishing commands
        """
        super().__init__()
        self.event_bus = event_bus
        self.history: List[str] = []
        self.history_index = 0

    def compose(self):
        """Compose widget layout."""
        yield Static("Command:", classes="command-label")
        yield Input(placeholder="Type a command...", id="command-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission.

        Args:
            event: Input submitted event
        """
        text = event.value.strip()
        if text:
            self.on_submit(text)
            event.input.value = ""  # Clear input

    def on_submit(self, text: str) -> None:
        """Publish command event.

        Args:
            text: Command text
        """
        self.event_bus.publish("command.received", {
            "text": text,
            "source": "text",
            "timestamp": time.time()
        })
        self.history.append(text)
        self.history_index = len(self.history)
```

### Step 4: Create widgets __init__.py

```python
# src/sociopsi/presentation/widgets/__init__.py
"""TUI widgets."""

from sociopsi.presentation.widgets.command_input import CommandInput

__all__ = ["CommandInput"]
```

### Step 5: Run test to verify it passes

```bash
uv run pytest tests/unit/test_command_input.py -v
```

Expected: 3 passed

### Step 6: Commit

```bash
git add src/sociopsi/presentation/widgets/ tests/unit/test_command_input.py
git commit -m "feat: add CommandInput widget with event publishing

- CommandInput widget publishes command.received events
- Command history tracking
- 3 tests passing"
```

---

## Task 2: Integrate CommandInput into TUI

**Files:**
- Modify: `src/sociopsi/presentation/tui.py:1-150`
- Test: Manual (visual verification)

### Step 1: Import CommandInput in TUI

```python
# src/sociopsi/presentation/tui.py
# Add to imports at top
from sociopsi.presentation.widgets import CommandInput
```

### Step 2: Add CommandInput to TUI compose method

Find the `compose` method in `SocioPsiTUI` class and add CommandInput:

```python
def compose(self):
    """Compose the application layout."""
    yield Header()
    yield Container(
        DriveDisplay(id="drives"),
        MonologueDisplay(id="monologue"),
        CommandInput(self.agent.event_bus),  # NEW
        id="main_container"
    )
    yield Footer()
```

### Step 3: Test TUI visually

```bash
# Don't run main.py yet (audio systems not implemented)
# Just verify file syntax
uv run python -c "from sociopsi.presentation.tui import SocioPsiTUI"
```

Expected: No import errors

### Step 4: Commit

```bash
git add src/sociopsi/presentation/tui.py
git commit -m "feat: integrate CommandInput widget into TUI layout"
```

---

## Task 3: Command Processor Foundation

**Files:**
- Create: `src/sociopsi/subsystems/commands/__init__.py`
- Create: `src/sociopsi/subsystems/commands/processor.py`
- Test: `tests/unit/test_command_processor.py`

### Step 1: Write failing tests for CommandProcessor

```python
# tests/unit/test_command_processor.py
import pytest
from sociopsi.subsystems.commands.processor import CommandProcessor
from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.drives import DriveSystem
from sociopsi.core.config import Config


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    return Config({"drives": {"affiliation": {"decay_rate": 0.01, "base_threshold": 0.4}}})


@pytest.fixture
def drive_system(event_bus, config):
    return DriveSystem(event_bus, config)


def test_command_processor_initialization(event_bus, drive_system):
    """CommandProcessor initializes and subscribes to events."""
    processor = CommandProcessor(event_bus, [], None, drive_system)
    assert processor.event_bus == event_bus
    assert processor.drive_system == drive_system


def test_calculate_psychological_state_threat(event_bus, drive_system, config):
    """Low drives trigger threat state."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    # Set all drives to low level
    for drive in drive_system.drives.values():
        drive.level = 0.2

    state = processor._calculate_state()
    assert state == "threat"


def test_calculate_psychological_state_calm(event_bus, drive_system, config):
    """High drives and harmony trigger calm state."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    # Set drives to high level
    for drive in drive_system.drives.values():
        drive.level = 0.8

    # Mock high harmony
    processor.last_harmony = 0.85

    state = processor._calculate_state()
    assert state == "calm"


def test_calculate_psychological_state_normal(event_bus, drive_system, config):
    """Mid-range drives trigger normal state."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    # Set drives to mid level
    for drive in drive_system.drives.values():
        drive.level = 0.5

    processor.last_harmony = 0.6

    state = processor._calculate_state()
    assert state == "normal"


def test_get_consultation_duration_ranges(event_bus, drive_system, config):
    """Consultation duration matches state ranges."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    threat_duration = processor._get_consultation_duration("threat")
    assert 0.5 <= threat_duration <= 1.0

    normal_duration = processor._get_consultation_duration("normal")
    assert 1.0 <= normal_duration <= 2.0

    calm_duration = processor._get_consultation_duration("calm")
    assert 2.0 <= calm_duration <= 4.0
```

### Step 2: Run test to verify it fails

```bash
uv run pytest tests/unit/test_command_processor.py -v
```

Expected: FAIL with "No module named 'sociopsi.subsystems.commands'"

### Step 3: Create CommandProcessor foundation

```python
# src/sociopsi/subsystems/commands/__init__.py
"""Command processing subsystem."""

from sociopsi.subsystems.commands.processor import CommandProcessor

__all__ = ["CommandProcessor"]
```

```python
# src/sociopsi/subsystems/commands/processor.py
"""Command processor with archetypal consultation."""

import random
from typing import List, Optional, Any
from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.drives import DriveSystem


class CommandProcessor:
    """Processes commands through archetypal consultation."""

    def __init__(
        self,
        event_bus: EventBus,
        archetypes: List[Any],  # Will use proper type later
        ego: Optional[Any],  # Will use proper type later
        drive_system: DriveSystem
    ) -> None:
        """Initialize command processor.

        Args:
            event_bus: Event bus for pub/sub
            archetypes: List of archetypal voices
            ego: Ego mediator
            drive_system: Drive system for state calculation
        """
        self.event_bus = event_bus
        self.archetypes = archetypes
        self.ego = ego
        self.drive_system = drive_system
        self.last_harmony = 0.5  # Default mid-range

        event_bus.subscribe("command.received", self.on_command)

    async def on_command(self, data: dict) -> None:
        """Handle incoming command.

        Args:
            data: Command data with 'text', 'source', 'timestamp'
        """
        # TODO: Implement full flow
        pass

    def _calculate_state(self) -> str:
        """Determine psychological state: threat/normal/calm.

        Returns:
            State string: "threat", "normal", or "calm"
        """
        # Calculate average drive level
        if not self.drive_system.drives:
            return "normal"

        avg_level = sum(d.level for d in self.drive_system.drives.values()) / len(
            self.drive_system.drives
        )
        harmony = self.last_harmony

        # Threat: low drives or low harmony
        if avg_level < 0.3 or harmony < 0.3:
            return "threat"
        # Calm: high drives and high harmony
        elif avg_level > 0.7 and harmony > 0.7:
            return "calm"
        # Normal: everything else
        else:
            return "normal"

    def _get_consultation_duration(self, state: str) -> float:
        """Map state to consultation duration.

        Args:
            state: Psychological state

        Returns:
            Duration in seconds
        """
        durations = {
            "threat": (0.5, 1.0),
            "normal": (1.0, 2.0),
            "calm": (2.0, 4.0)
        }
        min_dur, max_dur = durations[state]
        return random.uniform(min_dur, max_dur)
```

### Step 4: Run tests to verify they pass

```bash
uv run pytest tests/unit/test_command_processor.py -v
```

Expected: 5 passed

### Step 5: Commit

```bash
git add src/sociopsi/subsystems/commands/ tests/unit/test_command_processor.py
git commit -m "feat: add CommandProcessor with psychological state calculation

- CommandProcessor calculates threat/normal/calm states
- Consultation duration varies by state (0.5-4s)
- 5 tests passing"
```

---

## Task 4: Archetypal Command Interpretation

**Files:**
- Modify: `src/sociopsi/subsystems/commands/processor.py:30-100`
- Test: `tests/unit/test_command_processor.py`

### Step 1: Write failing test for archetypal interpretation

```python
# tests/unit/test_command_processor.py
# Add to existing file

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_archetypal_interpretation(event_bus, drive_system):
    """Each archetype interprets command."""
    # Mock archetypes
    mock_archetypes = []
    for name in ["Persona", "Shadow", "Anima", "Self"]:
        archetype = MagicMock()
        archetype.name = name
        archetype.generate = AsyncMock(return_value=f"{name} interpretation")
        mock_archetypes.append(archetype)

    processor = CommandProcessor(event_bus, mock_archetypes, None, drive_system)

    interpretations = await processor._archetypal_interpretation(
        "what are you thinking?", duration=0.1
    )

    assert len(interpretations) == 4
    assert interpretations[0]["archetype"] == "Persona"
    assert "interpretation" in interpretations[0]["interpretation"]

    # Verify each archetype was called
    for archetype in mock_archetypes:
        archetype.generate.assert_called_once()
```

### Step 2: Run test to verify it fails

```bash
uv run pytest tests/unit/test_command_processor.py::test_archetypal_interpretation -v
```

Expected: FAIL with "object has no attribute '_archetypal_interpretation'"

### Step 3: Implement archetypal interpretation

```python
# src/sociopsi/subsystems/commands/processor.py
# Add to CommandProcessor class

import asyncio


async def _archetypal_interpretation(
    self, command: str, duration: float
) -> List[dict]:
    """Each archetype interprets command intent.

    Args:
        command: User command text
        duration: How long consultation should take

    Returns:
        List of archetypal interpretations
    """
    interpretations = []

    for archetype in self.archetypes:
        prompt = f"""The user said: "{command}"

From your perspective as {archetype.name}, interpret this command:
- What does the user want?
- What is their intent/motivation?
- Is this a query (asking for information), an action (do something), or a goal (pursue over time)?

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
```

Add import at top:

```python
import time
```

### Step 4: Run test to verify it passes

```bash
uv run pytest tests/unit/test_command_processor.py::test_archetypal_interpretation -v
```

Expected: 1 passed

### Step 5: Commit

```bash
git add src/sociopsi/subsystems/commands/processor.py tests/unit/test_command_processor.py
git commit -m "feat: implement archetypal command interpretation

- Each archetype interprets command via LLM
- Consultation simulates duration
- 6 tests passing (1 new)"
```

---

## Task 5: Ego Command Classification

**Files:**
- Modify: `src/sociopsi/subsystems/commands/processor.py:100-200`
- Test: `tests/unit/test_command_processor.py`

### Step 1: Write failing test for Ego classification

```python
# tests/unit/test_command_processor.py
# Add to existing file

@pytest.mark.asyncio
async def test_ego_classification(event_bus, drive_system):
    """Ego synthesizes classification from interpretations."""
    mock_ego = MagicMock()
    mock_ego.generate = AsyncMock(return_value='{"type": "query", "intent": "Check drive state", "confidence": 0.9}')

    processor = CommandProcessor(event_bus, [], mock_ego, drive_system)

    interpretations = [
        {"archetype": "Persona", "interpretation": "User wants polite update"},
        {"archetype": "Shadow", "interpretation": "User is checking on us"},
    ]

    classification = await processor._ego_classification(
        "what are your drives?", interpretations
    )

    assert classification["type"] == "query"
    assert classification["intent"] == "Check drive state"
    assert classification["confidence"] == 0.9
    mock_ego.generate.assert_called_once()


def test_parse_classification_json():
    """Parse JSON classification response."""
    processor = CommandProcessor(EventBus(), [], None, DriveSystem(EventBus(), Config({})))

    json_str = '{"type": "action", "intent": "Speak thoughts", "parameters": {}, "confidence": 0.8}'
    result = processor._parse_classification(json_str)

    assert result["type"] == "action"
    assert result["intent"] == "Speak thoughts"
    assert result["confidence"] == 0.8


def test_parse_classification_fallback():
    """Fallback for invalid JSON."""
    processor = CommandProcessor(EventBus(), [], None, DriveSystem(EventBus(), Config({})))

    invalid = "Not valid JSON at all"
    result = processor._parse_classification(invalid)

    assert result["type"] == "query"  # Default
    assert result["confidence"] == 0.5
```

### Step 2: Run tests to verify they fail

```bash
uv run pytest tests/unit/test_command_processor.py::test_ego_classification -v
uv run pytest tests/unit/test_command_processor.py::test_parse_classification_json -v
uv run pytest tests/unit/test_command_processor.py::test_parse_classification_fallback -v
```

Expected: 3 failures

### Step 3: Implement Ego classification

```python
# src/sociopsi/subsystems/commands/processor.py
# Add to CommandProcessor class

import json


async def _ego_classification(
    self, command: str, interpretations: List[dict]
) -> dict:
    """Ego synthesizes archetypal perspectives into classification.

    Args:
        command: User command text
        interpretations: List of archetypal interpretations

    Returns:
        Classification dict with type, intent, parameters, confidence
    """
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


def _parse_classification(self, response: str) -> dict:
    """Parse LLM classification response.

    Args:
        response: LLM response (should be JSON)

    Returns:
        Classification dict
    """
    try:
        # Try to parse as JSON
        parsed = json.loads(response)
        return {
            "type": parsed.get("type", "query"),
            "intent": parsed.get("intent", "Unknown intent"),
            "parameters": parsed.get("parameters", {}),
            "confidence": parsed.get("confidence", 0.5)
        }
    except json.JSONDecodeError:
        # Fallback for non-JSON responses
        return {
            "type": "query",
            "intent": response[:100],  # First 100 chars
            "parameters": {},
            "confidence": 0.5
        }
```

### Step 4: Run tests to verify they pass

```bash
uv run pytest tests/unit/test_command_processor.py -v -k "ego_classification or parse_classification"
```

Expected: 3 passed

### Step 5: Commit

```bash
git add src/sociopsi/subsystems/commands/processor.py tests/unit/test_command_processor.py
git commit -m "feat: implement Ego command classification synthesis

- Ego synthesizes archetypal perspectives via LLM
- JSON parsing with fallback handling
- 9 tests passing (3 new)"
```

---

## Task 6: Command Routing

**Files:**
- Modify: `src/sociopsi/subsystems/commands/processor.py:200-250`
- Test: `tests/unit/test_command_processor.py`

### Step 1: Write failing test for command routing

```python
# tests/unit/test_command_processor.py
# Add to existing file

@pytest.mark.asyncio
async def test_route_command_query(event_bus, drive_system):
    """Query commands route to command.query event."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    published_events = []
    event_bus.subscribe("command.query", lambda data: published_events.append(data))

    classification = {"type": "query", "intent": "Check drives"}
    await processor._route_command(classification)

    assert len(published_events) == 1
    assert published_events[0]["type"] == "query"


@pytest.mark.asyncio
async def test_route_command_action(event_bus, drive_system):
    """Action commands route to command.action event."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    published_events = []
    event_bus.subscribe("command.action", lambda data: published_events.append(data))

    classification = {"type": "action", "intent": "Speak thoughts"}
    await processor._route_command(classification)

    assert len(published_events) == 1
    assert published_events[0]["type"] == "action"


@pytest.mark.asyncio
async def test_route_command_goal(event_bus, drive_system):
    """Goal commands route to command.goal event."""
    processor = CommandProcessor(event_bus, [], None, drive_system)

    published_events = []
    event_bus.subscribe("command.goal", lambda data: published_events.append(data))

    classification = {"type": "goal", "intent": "Satisfy affiliation"}
    await processor._route_command(classification)

    assert len(published_events) == 1
    assert published_events[0]["type"] == "goal"
```

### Step 2: Run tests to verify they fail

```bash
uv run pytest tests/unit/test_command_processor.py -v -k "route_command"
```

Expected: 3 failures with "has no attribute '_route_command'"

### Step 3: Implement command routing

```python
# src/sociopsi/subsystems/commands/processor.py
# Add to CommandProcessor class

async def _route_command(self, classification: dict) -> None:
    """Route command to appropriate handler.

    Args:
        classification: Command classification with type
    """
    cmd_type = classification["type"]

    if cmd_type == "query":
        self.event_bus.publish("command.query", classification)
    elif cmd_type == "action":
        self.event_bus.publish("command.action", classification)
    elif cmd_type == "goal":
        self.event_bus.publish("command.goal", classification)
```

### Step 4: Run tests to verify they pass

```bash
uv run pytest tests/unit/test_command_processor.py -v -k "route_command"
```

Expected: 3 passed

### Step 5: Complete on_command implementation

```python
# src/sociopsi/subsystems/commands/processor.py
# Update on_command method in CommandProcessor class

async def on_command(self, data: dict) -> None:
    """Handle incoming command.

    Args:
        data: Command data with 'text', 'source', 'timestamp'
    """
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
```

### Step 6: Run all CommandProcessor tests

```bash
uv run pytest tests/unit/test_command_processor.py -v
```

Expected: 12 passed

### Step 7: Commit

```bash
git add src/sociopsi/subsystems/commands/processor.py tests/unit/test_command_processor.py
git commit -m "feat: implement command routing and complete processor flow

- Commands route to query/action/goal events
- Full on_command flow: state → consultation → classification → routing
- 12 tests passing (3 new)"
```

---

## Task 7: Query Handler

**Files:**
- Create: `src/sociopsi/subsystems/commands/query_handler.py`
- Modify: `src/sociopsi/subsystems/commands/__init__.py`
- Test: `tests/unit/test_query_handler.py`

### Step 1: Write failing tests for QueryHandler

```python
# tests/unit/test_query_handler.py
import pytest
from sociopsi.subsystems.commands.query_handler import QueryHandler
from sociopsi.core.event_bus import EventBus
from sociopsi.subsystems.drives import Drive, DriveSystem
from sociopsi.subsystems.memory import Memory, MemorySystem
from sociopsi.core.config import Config
from unittest.mock import MagicMock


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_agent():
    agent = MagicMock()

    # Mock drive system
    agent.drive_system.get_all_drives.return_value = [
        Drive("affiliation", decay_rate=0.01, base_threshold=0.4, level=0.6),
        Drive("nurturing", decay_rate=0.008, base_threshold=0.3, level=0.8),
    ]

    # Mock memory system
    agent.memory_system.get_recent_memories.return_value = [
        Memory(content="Thought about nature", intensity=0.7),
        Memory(content="Reflected on harmony", intensity=0.8),
    ]

    # Mock ego
    agent.ego.last_harmony_level = 0.75

    # Mock goal manager
    agent.goal_manager.get_active_goals.return_value = []

    return agent


def test_query_handler_initialization(event_bus, mock_agent):
    """QueryHandler initializes and subscribes to events."""
    handler = QueryHandler(event_bus, mock_agent)
    assert handler.event_bus == event_bus
    assert handler.agent == mock_agent


@pytest.mark.asyncio
async def test_query_drives(event_bus, mock_agent):
    """Query drives returns current drive levels."""
    handler = QueryHandler(event_bus, mock_agent)

    published_events = []
    event_bus.subscribe("command.response", lambda data: published_events.append(data))

    await handler.on_query({"intent": "what are your drives"})

    assert len(published_events) == 1
    response = published_events[0]["text"]
    assert "affiliation" in response.lower()
    assert "0.6" in response or "0.60" in response


@pytest.mark.asyncio
async def test_query_thoughts(event_bus, mock_agent):
    """Query thoughts returns recent memories."""
    handler = QueryHandler(event_bus, mock_agent)

    published_events = []
    event_bus.subscribe("command.response", lambda data: published_events.append(data))

    await handler.on_query({"intent": "what are you thinking"})

    assert len(published_events) == 1
    response = published_events[0]["text"]
    assert "nature" in response.lower() or "harmony" in response.lower()


@pytest.mark.asyncio
async def test_query_harmony(event_bus, mock_agent):
    """Query harmony returns harmony level."""
    handler = QueryHandler(event_bus, mock_agent)

    published_events = []
    event_bus.subscribe("command.response", lambda data: published_events.append(data))

    await handler.on_query({"intent": "how is your harmony"})

    assert len(published_events) == 1
    response = published_events[0]["text"]
    assert "0.75" in response or "harmony" in response.lower()
```

### Step 2: Run tests to verify they fail

```bash
uv run pytest tests/unit/test_query_handler.py -v
```

Expected: 4 failures with "No module named 'sociopsi.subsystems.commands.query_handler'"

### Step 3: Implement QueryHandler

```python
# src/sociopsi/subsystems/commands/query_handler.py
"""Query handler for state queries."""

from typing import Any
from sociopsi.core.event_bus import EventBus


class QueryHandler:
    """Handles state query commands."""

    def __init__(self, event_bus: EventBus, agent: Any) -> None:
        """Initialize query handler.

        Args:
            event_bus: Event bus for pub/sub
            agent: SocioPsiAgent instance
        """
        self.event_bus = event_bus
        self.agent = agent

        event_bus.subscribe("command.query", self.on_query)

    async def on_query(self, classification: dict) -> None:
        """Handle query command.

        Args:
            classification: Query classification with intent
        """
        intent = classification["intent"].lower()
        params = classification.get("parameters", {})

        # Determine query type
        if "drive" in intent:
            response = self._query_drives()
        elif "thought" in intent or "thinking" in intent:
            response = self._query_thoughts()
        elif "memory" in intent or "remember" in intent:
            response = self._query_memories(params)
        elif "harmony" in intent or "integration" in intent:
            response = self._query_harmony()
        elif "goal" in intent:
            response = self._query_goals()
        else:
            response = self._query_general_state()

        # Publish response
        self.event_bus.publish("command.response", {
            "text": response,
            "query": classification["intent"]
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
        """Search memories by query.

        Args:
            params: Parameters dict (may contain 'query')
        """
        query = params.get("query", "")
        if not query:
            return self._query_thoughts()  # Fallback

        # Search will be implemented later with semantic memory
        return self._query_thoughts()

    def _query_harmony(self) -> str:
        """Return current harmony level."""
        harmony = self.agent.ego.last_harmony_level
        return f"Harmony: {harmony:.2f}"

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

### Step 4: Update __init__.py

```python
# src/sociopsi/subsystems/commands/__init__.py
"""Command processing subsystem."""

from sociopsi.subsystems.commands.processor import CommandProcessor
from sociopsi.subsystems.commands.query_handler import QueryHandler

__all__ = ["CommandProcessor", "QueryHandler"]
```

### Step 5: Run tests to verify they pass

```bash
uv run pytest tests/unit/test_query_handler.py -v
```

Expected: 4 passed

### Step 6: Commit

```bash
git add src/sociopsi/subsystems/commands/ tests/unit/test_query_handler.py
git commit -m "feat: implement QueryHandler for state queries

- QueryHandler answers drive/thought/harmony/goal queries
- Formatted text responses
- 4 tests passing"
```

---

## Task 8: Audio Perception Foundation

**Files:**
- Modify: `src/sociopsi/subsystems/perception/audio.py:1-150`
- Test: `tests/unit/test_audio_perception.py`

### Step 1: Write tests for audio perception basics

```python
# tests/unit/test_audio_perception.py
import pytest
import numpy as np
from sociopsi.subsystems.perception.audio import (
    AudioPerception,
    AdaptiveSampler,
    SoundClassifier
)
from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    return Config({
        "audio": {
            "sample_rate": 16000,
            "chunk_size": 1024,
            "buffer_seconds": 6.0
        }
    })


def test_adaptive_sampler_initialization():
    """AdaptiveSampler initializes with default FPS."""
    sampler = AdaptiveSampler()
    assert sampler.current_fps == 3.0
    assert sampler.min_fps == 1.0
    assert sampler.max_fps == 10.0


def test_adaptive_sampler_increases_on_activity():
    """FPS increases when activity detected."""
    sampler = AdaptiveSampler()
    initial_fps = sampler.current_fps

    sampler.update({"type": "speech", "volume": 0.8})

    assert sampler.current_fps > initial_fps


def test_adaptive_sampler_decreases_on_silence():
    """FPS decreases during silence."""
    sampler = AdaptiveSampler()
    sampler.current_fps = 5.0  # Start higher

    sampler.update({"type": "silence", "volume": 0.0})

    assert sampler.current_fps < 5.0


def test_sound_classifier_silence():
    """SoundClassifier detects silence."""
    classifier = SoundClassifier()

    # Very quiet audio (near zero)
    audio = np.random.randn(16000) * 0.01
    result = classifier.classify(audio)

    assert result["type"] == "silence"
    assert result["volume"] < 0.1


def test_sound_classifier_loud_noise():
    """SoundClassifier detects loud noise."""
    classifier = SoundClassifier()

    # Loud random noise
    audio = np.random.randn(16000) * 0.2
    result = classifier.classify(audio)

    assert result["type"] in ["speech", "noise"]
    assert result["volume"] > 0.5


def test_audio_perception_initialization(event_bus, config):
    """AudioPerception initializes with config."""
    audio = AudioPerception(event_bus, config)

    assert audio.sample_rate == 16000
    assert audio.chunk_size == 1024
    assert not audio.is_running
```

### Step 2: Run tests to verify they fail

```bash
uv run pytest tests/unit/test_audio_perception.py -v
```

Expected: 6 failures (classes/methods don't exist yet)

### Step 3: Implement AdaptiveSampler

```python
# src/sociopsi/subsystems/perception/audio.py
# Replace stub with full implementation

import time
import numpy as np
from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config


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

    def update(self, classification: dict) -> None:
        """Adjust sampling rate based on activity.

        Args:
            classification: Sound classification dict
        """
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

### Step 4: Implement SoundClassifier

```python
# src/sociopsi/subsystems/perception/audio.py
# Add to same file


class SoundClassifier:
    """Classifies audio into speech/noise/silence."""

    def __init__(self) -> None:
        """Initialize sound classifier."""
        self.silence_threshold = 0.02  # RMS threshold

    def classify(self, audio_data: np.ndarray) -> dict:
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
            return {
                "type": "silence",
                "volume": 0.0,
                "confidence": 0.95
            }

        # Detect speech vs non-speech
        # For MVP: simple heuristic based on zero-crossing rate
        zcr = self._zero_crossing_rate(audio_data)
        is_speech = 0.05 < zcr < 0.3  # Speech has moderate ZCR

        return {
            "type": "speech" if is_speech else "noise",
            "volume": min(1.0, volume / 0.1),  # Normalize
            "confidence": 0.7  # Lower for heuristic
        }

    def _zero_crossing_rate(self, audio: np.ndarray) -> float:
        """Calculate zero-crossing rate.

        Args:
            audio: Audio samples

        Returns:
            ZCR value
        """
        return float(np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio)))
```

### Step 5: Implement AudioPerception foundation

```python
# src/sociopsi/subsystems/perception/audio.py
# Add to same file


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

        self.adaptive_sampler = AdaptiveSampler()
        self.sound_classifier = SoundClassifier()

        self.is_running = False
        self.stream = None

        # Note: Full audio capture will be implemented in next task

    async def start(self) -> None:
        """Begin audio capture."""
        self.is_running = True
        # TODO: Start audio stream

    async def stop(self) -> None:
        """Stop audio capture."""
        self.is_running = False
        if self.stream:
            self.stream.stop()

    async def update(self, dt: float) -> None:
        """Adaptive sampling and classification.

        Args:
            dt: Delta time since last update
        """
        if not self.is_running:
            return

        # TODO: Implement full update loop
```

### Step 6: Run tests to verify they pass

```bash
uv run pytest tests/unit/test_audio_perception.py -v
```

Expected: 6 passed

### Step 7: Commit

```bash
git add src/sociopsi/subsystems/perception/audio.py tests/unit/test_audio_perception.py
git commit -m "feat: implement audio perception foundation

- AdaptiveSampler adjusts FPS based on activity
- SoundClassifier detects speech/noise/silence via ZCR
- AudioPerception foundation ready for audio capture
- 6 tests passing"
```

---

## Task 9: Audio Capture Integration

**Files:**
- Modify: `src/sociopsi/subsystems/perception/audio.py:150-250`
- Test: Manual (requires microphone)

### Step 1: Add audio buffer class

```python
# src/sociopsi/subsystems/perception/audio.py
# Add before AudioPerception class

from collections import deque


class CircularBuffer:
    """Circular buffer for audio samples."""

    def __init__(self, size: int) -> None:
        """Initialize buffer.

        Args:
            size: Buffer size in samples
        """
        self.size = size
        self.buffer = deque(maxlen=size)

    def append(self, data: np.ndarray) -> None:
        """Append audio data.

        Args:
            data: Audio samples
        """
        for sample in data.flatten():
            self.buffer.append(sample)

    def get_recent(self, duration: float, sample_rate: int = 16000) -> np.ndarray:
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
```

### Step 2: Complete AudioPerception with audio capture

```python
# src/sociopsi/subsystems/perception/audio.py
# Update AudioPerception class

import sounddevice as sd


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

        self.buffer = CircularBuffer(
            size=int(self.sample_rate * self.buffer_seconds)
        )
        self.adaptive_sampler = AdaptiveSampler()
        self.sound_classifier = SoundClassifier()

        self.is_running = False
        self.stream = None

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info: dict, status: sd.CallbackFlags) -> None:
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
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self._audio_callback,
                blocksize=self.chunk_size
            )
            self.stream.start()
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
        audio_data = self.buffer.get_recent(
            duration=1.0, sample_rate=self.sample_rate
        )

        if len(audio_data) == 0:
            return

        # Classify sound
        classification = self.sound_classifier.classify(audio_data)

        # Publish ambient sound event
        self.event_bus.publish("perception.audio.ambient", {
            "type": classification["type"],
            "volume": classification["volume"],
            "confidence": classification["confidence"]
        })

        # Update adaptive sampler
        self.adaptive_sampler.update(classification)
```

### Step 3: Test audio capture manually

```bash
# Test import and initialization
uv run python -c "from sociopsi.subsystems.perception.audio import AudioPerception; from sociopsi.core.event_bus import EventBus; from sociopsi.core.config import Config; audio = AudioPerception(EventBus(), Config({})); print('Audio perception initialized')"
```

Expected: No errors, "Audio perception initialized" printed

### Step 4: Commit

```bash
git add src/sociopsi/subsystems/perception/audio.py
git commit -m "feat: integrate audio capture with sounddevice

- CircularBuffer for audio samples
- Audio callback appends to buffer
- update() analyzes audio and publishes events
- Adaptive sampling with configurable FPS"
```

---

## Task 10: Archetypal Modulation

**Files:**
- Create: `src/sociopsi/subsystems/archetypes/modulator.py`
- Modify: `src/sociopsi/subsystems/archetypes/__init__.py`
- Test: `tests/unit/test_archetypal_modulator.py`

### Step 1: Write failing tests for ArchetypalModulator

```python
# tests/unit/test_archetypal_modulator.py
import pytest
from sociopsi.subsystems.archetypes.modulator import ArchetypalModulator
from sociopsi.core.event_bus import EventBus
from unittest.mock import MagicMock


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_archetypes():
    return {
        "Persona": MagicMock(),
        "Shadow": MagicMock(),
        "Anima": MagicMock(),
        "Self": MagicMock()
    }


def test_modulator_initialization(event_bus, mock_archetypes):
    """ArchetypalModulator initializes with base weights."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    assert modulator.current_weights["Persona"] == 1.0
    assert modulator.current_weights["Shadow"] == 1.0
    assert modulator.current_weights["Anima"] == 1.0
    assert modulator.current_weights["Self"] == 1.0


def test_modulator_silence_boosts_self(event_bus, mock_archetypes):
    """Silence environment boosts Self and Anima."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    # Publish silence event
    event_bus.publish("perception.audio.ambient", {
        "type": "silence",
        "volume": 0.0,
        "confidence": 0.95
    })

    # Self should be boosted
    assert modulator.current_weights["Self"] > 1.0
    assert modulator.current_weights["Anima"] > 1.0
    assert modulator.current_weights["Shadow"] < 1.0


def test_modulator_speech_boosts_anima(event_bus, mock_archetypes):
    """Speech environment boosts Anima and Persona."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    event_bus.publish("perception.audio.ambient", {
        "type": "speech",
        "volume": 0.6,
        "confidence": 0.8
    })

    assert modulator.current_weights["Anima"] > 1.0
    assert modulator.current_weights["Persona"] > 1.0


def test_modulator_loud_noise_boosts_shadow(event_bus, mock_archetypes):
    """Loud noise boosts Shadow (survival mode)."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    event_bus.publish("perception.audio.ambient", {
        "type": "noise",
        "volume": 0.9,
        "confidence": 0.7
    })

    assert modulator.current_weights["Shadow"] > 1.0


def test_modulator_smooth_transitions(event_bus, mock_archetypes):
    """Weight transitions are smooth, not abrupt."""
    modulator = ArchetypalModulator(event_bus, mock_archetypes)

    initial_self = modulator.current_weights["Self"]

    # Single silence event shouldn't jump to 1.5 immediately
    event_bus.publish("perception.audio.ambient", {
        "type": "silence",
        "volume": 0.0,
        "confidence": 0.95
    })

    # Should be between initial and target
    assert initial_self < modulator.current_weights["Self"] < 1.5
```

### Step 2: Run tests to verify they fail

```bash
uv run pytest tests/unit/test_archetypal_modulator.py -v
```

Expected: 5 failures with "No module named 'sociopsi.subsystems.archetypes.modulator'"

### Step 3: Implement ArchetypalModulator

```python
# src/sociopsi/subsystems/archetypes/modulator.py
"""Archetypal modulation based on acoustic environment."""

from typing import Dict, Any
from sociopsi.core.event_bus import EventBus


class ArchetypalModulator:
    """Modulates archetype activation based on acoustic environment."""

    def __init__(self, event_bus: EventBus, archetypes: Dict[str, Any]) -> None:
        """Initialize archetypal modulator.

        Args:
            event_bus: Event bus for subscribing to ambient sound
            archetypes: Dict of archetype name to archetype instance
        """
        self.event_bus = event_bus
        self.archetypes = archetypes
        self.base_weights = {name: 1.0 for name in archetypes}
        self.current_weights = self.base_weights.copy()

        event_bus.subscribe("perception.audio.ambient", self.on_ambient_sound)

    def on_ambient_sound(self, data: dict) -> None:
        """Adjust archetype weights based on acoustic environment.

        Args:
            data: Ambient sound event data
        """
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
        """Get current weight for archetype.

        Args:
            archetype_name: Name of archetype

        Returns:
            Current weight
        """
        return self.current_weights.get(archetype_name, 1.0)

    def _interpolate_weights(self, current: dict, target: dict,
                              alpha: float) -> dict:
        """Smooth weight transitions.

        Args:
            current: Current weights
            target: Target weights
            alpha: Interpolation factor (0-1)

        Returns:
            Interpolated weights
        """
        return {
            name: current[name] * (1 - alpha) + target[name] * alpha
            for name in current
        }
```

### Step 4: Update __init__.py

```python
# src/sociopsi/subsystems/archetypes/__init__.py
# Add to existing exports

from sociopsi.subsystems.archetypes.modulator import ArchetypalModulator

__all__ = [
    "Archetype",
    "Persona",
    "Shadow",
    "Anima",
    "Self",
    "ArchetypalModulator"  # NEW
]
```

### Step 5: Run tests to verify they pass

```bash
uv run pytest tests/unit/test_archetypal_modulator.py -v
```

Expected: 5 passed

### Step 6: Commit

```bash
git add src/sociopsi/subsystems/archetypes/ tests/unit/test_archetypal_modulator.py
git commit -m "feat: implement archetypal modulation system

- Acoustic environment modulates archetype weights
- Silence boosts Self/Anima, speech boosts Anima/Persona, noise boosts Shadow
- Smooth weight transitions via interpolation
- 5 tests passing"
```

---

**Midpoint Checkpoint: Core command and audio systems complete. Next: speech recognition, integration, and configuration.**

---

## Task 11: Speech Recognition System

**Files:**
- Create: `src/sociopsi/subsystems/commands/speech_input.py`
- Modify: `src/sociopsi/subsystems/commands/__init__.py`
- Test: `tests/unit/test_speech_input.py`

### Step 1: Add faster-whisper dependency

```bash
# Add to pyproject.toml dependencies
uv add faster-whisper
```

### Step 2: Write tests for SpeechInput

```python
# tests/unit/test_speech_input.py
import pytest
from sociopsi.subsystems.commands.speech_input import SpeechInput
from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    return Config({"audio": {"whisper_model": "base.en"}})


def test_speech_input_initialization(event_bus, config):
    """SpeechInput initializes with config."""
    speech = SpeechInput(event_bus, config)

    assert speech.model_name == "base.en"
    assert not speech.is_recording
    assert speech.model is None  # Lazy load


@pytest.mark.asyncio
async def test_start_recording(event_bus, config):
    """Starting recording sets state and publishes event."""
    speech = SpeechInput(event_bus, config)

    published_events = []
    event_bus.subscribe("speech.recording.started",
                        lambda data: published_events.append(data))

    await speech.start_recording()

    assert speech.is_recording
    assert len(published_events) == 1


@pytest.mark.asyncio
async def test_stop_recording_no_audio(event_bus, config):
    """Stopping recording with no audio."""
    speech = SpeechInput(event_bus, config)
    speech.is_recording = True

    published_events = []
    event_bus.subscribe("speech.recording.stopped",
                        lambda data: published_events.append(data))

    await speech.stop_recording()

    assert not speech.is_recording
    assert len(published_events) == 1
    assert published_events[0]["transcribed"] == ""


@pytest.mark.asyncio
async def test_stop_recording_with_transcription(event_bus, config):
    """Stopping recording transcribes and publishes command."""
    speech = SpeechInput(event_bus, config)
    speech.is_recording = True
    speech.audio_buffer = [np.random.randn(16000).astype(np.float32)]

    # Mock transcription
    with patch.object(speech, 'transcribe', new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = "test command"

        command_events = []
        event_bus.subscribe("command.received",
                            lambda data: command_events.append(data))

        await speech.stop_recording()

        assert len(command_events) == 1
        assert command_events[0]["text"] == "test command"
        assert command_events[0]["source"] == "voice"
```

### Step 3: Run tests to verify they fail

```bash
uv run pytest tests/unit/test_speech_input.py -v
```

Expected: 4 failures

### Step 4: Implement SpeechInput

```python
# src/sociopsi/subsystems/commands/speech_input.py
"""Voice command transcription using local Whisper."""

import time
import numpy as np
from typing import List, Optional
from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config


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
        self.model = None  # Lazy load
        self.is_recording = False
        self.audio_buffer: List[np.ndarray] = []

    async def start_recording(self) -> None:
        """Start recording for voice command."""
        self.is_recording = True
        self.audio_buffer.clear()
        self.event_bus.publish("speech.recording.started", {
            "timestamp": time.time()
        })

    async def stop_recording(self) -> None:
        """Stop recording and transcribe."""
        self.is_recording = False

        # Transcribe buffered audio
        text = ""
        if self.audio_buffer:
            text = await self.transcribe(self.audio_buffer)

        if text:
            self.event_bus.publish("command.received", {
                "text": text,
                "source": "voice",
                "timestamp": time.time()
            })

        self.event_bus.publish("speech.recording.stopped", {
            "transcribed": text,
            "timestamp": time.time()
        })

    async def transcribe(self, audio_data: List[np.ndarray]) -> str:
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

    def add_audio(self, audio: np.ndarray) -> None:
        """Add audio to buffer while recording.

        Args:
            audio: Audio samples
        """
        if self.is_recording:
            self.audio_buffer.append(audio.copy())
```

### Step 5: Update __init__.py

```python
# src/sociopsi/subsystems/commands/__init__.py
"""Command processing subsystem."""

from sociopsi.subsystems.commands.processor import CommandProcessor
from sociopsi.subsystems.commands.query_handler import QueryHandler
from sociopsi.subsystems.commands.speech_input import SpeechInput

__all__ = ["CommandProcessor", "QueryHandler", "SpeechInput"]
```

### Step 6: Run tests to verify they pass

```bash
uv run pytest tests/unit/test_speech_input.py -v
```

Expected: 4 passed

### Step 7: Commit

```bash
git add src/sociopsi/subsystems/commands/ tests/unit/test_speech_input.py pyproject.toml
git commit -m "feat: implement speech recognition with faster-whisper

- SpeechInput with push-to-talk recording
- Lazy model loading (base.en)
- Transcription publishes command.received events
- 4 tests passing"
```

---

## Task 12: Agent Integration - Phase 5 Systems

**Files:**
- Modify: `src/sociopsi/core/agent.py:1-500`
- Test: Integration tests

### Step 1: Add Phase 5 imports to agent

```python
# src/sociopsi/core/agent.py
# Add to imports section

from sociopsi.subsystems.commands import (
    CommandProcessor,
    QueryHandler,
    SpeechInput
)
from sociopsi.subsystems.archetypes import ArchetypalModulator
```

### Step 2: Initialize Phase 5 systems in agent __init__

Find the `__init__` method and add Phase 5 systems after existing initializations:

```python
# Add after existing subsystem initializations (around line 100-150)

# Phase 5: Command processing
self.command_processor = CommandProcessor(
    self.event_bus,
    list(self.archetypes.values()),
    self.ego,
    self.drive_system
)

self.query_handler = QueryHandler(self.event_bus, self)

# Phase 5: Speech input
self.speech_input = SpeechInput(self.event_bus, config)

# Phase 5: Audio perception (expand stub)
self.audio_perception = AudioPerception(self.event_bus, config)

# Phase 5: Archetypal modulation
self.archetypal_modulator = ArchetypalModulator(
    self.event_bus,
    self.archetypes
)
```

### Step 3: Start audio perception in agent start method

Find the `start` method and add audio perception start:

```python
async def start(self):
    """Start the agent."""
    self.running = True

    # Start visual perception
    await self.visual_perception.start()

    # Phase 5: Start audio perception
    await self.audio_perception.start()

    print("Agent started")
```

### Step 4: Update audio perception in agent update loop

Find the `update` method and add audio perception update:

```python
async def update(self, dt: float):
    """Update agent state.

    Args:
        dt: Delta time since last update
    """
    # ... existing updates ...

    # Phase 5: Update audio perception
    await self.audio_perception.update(dt)

    # ... rest of update logic ...
```

### Step 5: Update command processor harmony tracking

Add after dialogue updates in the update method:

```python
# After dialogue.complete event handling
# Update command processor's harmony tracking
if hasattr(self, 'command_processor'):
    self.command_processor.last_harmony = self.ego.last_harmony_level
```

### Step 6: Stop audio perception in agent stop method

Find the `stop` method and add audio stop:

```python
async def stop(self):
    """Stop the agent."""
    self.running = False

    # Stop visual perception
    await self.visual_perception.stop()

    # Phase 5: Stop audio perception
    if hasattr(self, 'audio_perception'):
        await self.audio_perception.stop()

    print("Agent stopped")
```

### Step 7: Test agent initialization

```bash
uv run python -c "from sociopsi.core.agent import SocioPsiAgent; from sociopsi.core.config import Config; agent = SocioPsiAgent(Config({})); print('Agent initialized with Phase 5 systems')"
```

Expected: No errors, "Agent initialized with Phase 5 systems" printed

### Step 8: Commit

```bash
git add src/sociopsi/core/agent.py
git commit -m "feat: integrate Phase 5 systems into agent

- CommandProcessor, QueryHandler, SpeechInput initialized
- AudioPerception started/stopped in agent lifecycle
- ArchetypalModulator modulates based on audio
- Harmony tracking updated for command processor"
```

---

## Task 13: TUI Response Display

**Files:**
- Modify: `src/sociopsi/presentation/tui.py:50-200`
- Test: Manual (visual verification)

### Step 1: Subscribe to command response events in TUI

Find the `on_mount` method in `SocioPsiTUI` and add subscriptions:

```python
def on_mount(self):
    """Called when app is mounted."""
    # ... existing subscriptions ...

    # Phase 5: Command response subscriptions
    self.agent.event_bus.subscribe(
        "command.response",
        self.on_command_response
    )
    self.agent.event_bus.subscribe(
        "speech.recording.started",
        self.on_recording_started
    )
    self.agent.event_bus.subscribe(
        "speech.recording.stopped",
        self.on_recording_stopped
    )
```

### Step 2: Add command response handler

Add these methods to `SocioPsiTUI` class:

```python
def on_command_response(self, data: dict) -> None:
    """Handle command response event.

    Args:
        data: Response data with 'text' and 'query'
    """
    response_text = data["text"]

    # Display in monologue
    monologue = self.query_one("#monologue")
    monologue.add_thought(f"[Response] {response_text}")


def on_recording_started(self, data: dict) -> None:
    """Visual indicator that recording is active.

    Args:
        data: Recording start event data
    """
    command_input = self.query_one(CommandInput)
    # Add visual indicator (e.g., change border color)
    # This will be styled via CSS


def on_recording_stopped(self, data: dict) -> None:
    """Remove recording indicator.

    Args:
        data: Recording stop event data with 'transcribed'
    """
    command_input = self.query_one(CommandInput)
    # Remove visual indicator

    transcribed = data.get("transcribed", "")
    if transcribed:
        # Show transcribed text in monologue
        monologue = self.query_one("#monologue")
        monologue.add_thought(f"[Voice Command] {transcribed}")
```

### Step 3: Test TUI initialization

```bash
uv run python -c "from sociopsi.presentation.tui import SocioPsiTUI; from sociopsi.core.agent import SocioPsiAgent; from sociopsi.core.config import Config; print('TUI with Phase 5 support ready')"
```

Expected: No errors

### Step 4: Commit

```bash
git add src/sociopsi/presentation/tui.py
git commit -m "feat: add command response display to TUI

- Subscribe to command.response events
- Display responses in monologue
- Visual indicators for speech recording
- Voice command transcriptions shown"
```

---

## Task 14: Configuration

**Files:**
- Modify: `config.toml:50-100`

### Step 1: Add Phase 5 configuration sections

```toml
# config.toml
# Add at end of file

# Phase 5: Command Processing
[commands]
enabled = true
consultation_min_duration = 0.5  # Threat state (seconds)
consultation_max_duration = 4.0  # Calm state (seconds)

# Phase 5: Audio Perception
[audio]
enabled = true
sample_rate = 16000
chunk_size = 1024
buffer_seconds = 6.0
whisper_model = "base.en"  # Options: tiny.en, base.en, small.en, medium.en
push_to_talk_key = "space"

# Phase 5: Archetypal Modulation
[archetypal_modulation]
enabled = true
weight_transition_speed = 0.1  # Interpolation alpha (0-1)
silence_self_boost = 1.5
silence_anima_boost = 1.2
speech_anima_boost = 1.4
speech_persona_boost = 1.3
noise_shadow_boost = 1.6
```

### Step 2: Document configuration in comments

Add comments above sections:

```toml
# Phase 5: Command Processing
# Controls how commands are interpreted through archetypal consultation
# - consultation_min_duration: Fastest response time (threat state)
# - consultation_max_duration: Slowest, most contemplative (calm state)
[commands]
# ... config values ...

# Phase 5: Audio Perception
# Ambient sound monitoring and speech recognition
# - whisper_model: Smaller = faster but less accurate
# - push_to_talk_key: Key to activate voice recording
[audio]
# ... config values ...

# Phase 5: Archetypal Modulation
# How acoustic environment affects archetype activation
# - Boost values > 1.0 increase archetype influence
# - Values < 1.0 decrease influence
[archetypal_modulation]
# ... config values ...
```

### Step 3: Verify configuration loads

```bash
uv run python -c "from sociopsi.core.config import Config; c = Config({}); print('Commands enabled:', c.get('commands.enabled', False)); print('Audio enabled:', c.get('audio.enabled', False))"
```

Expected: Both print "True"

### Step 4: Commit

```bash
git add config.toml
git commit -m "feat: add Phase 5 configuration sections

- [commands] section for consultation durations
- [audio] section for sample rate, Whisper model
- [archetypal_modulation] section for weight boosts
- Documented all config options"
```

---

## Task 15: Integration Testing

**Files:**
- Create: `tests/integration/test_phase5_integration.py`
- Test: Full integration tests

### Step 1: Write Phase 5 integration tests

```python
# tests/integration/test_phase5_integration.py
"""Integration tests for Phase 5: Social Interaction & Audio."""

import pytest
from sociopsi.core.agent import SocioPsiAgent
from sociopsi.core.config import Config
from sociopsi.core.event_bus import EventBus
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def config():
    return Config({
        "commands": {"enabled": True},
        "audio": {"enabled": False},  # Disable for testing
        "archetypal_modulation": {"enabled": True}
    })


@pytest.fixture
def agent(config):
    return SocioPsiAgent(config)


def test_agent_has_phase5_systems(agent):
    """Agent initializes with all Phase 5 systems."""
    assert hasattr(agent, 'command_processor')
    assert hasattr(agent, 'query_handler')
    assert hasattr(agent, 'speech_input')
    assert hasattr(agent, 'audio_perception')
    assert hasattr(agent, 'archetypal_modulator')


@pytest.mark.asyncio
async def test_text_command_flow(agent):
    """Text command flows through full pipeline."""
    # Mock archetype responses
    for archetype in agent.archetypes.values():
        archetype.generate = AsyncMock(return_value="Query about drives")

    agent.ego.generate = AsyncMock(
        return_value='{"type": "query", "intent": "Check drives", "confidence": 0.9}'
    )

    # Capture response
    responses = []
    agent.event_bus.subscribe("command.response", lambda d: responses.append(d))

    # Publish command
    agent.event_bus.publish("command.received", {
        "text": "what are your drives?",
        "source": "text",
        "timestamp": 0.0
    })

    # Wait for processing
    await agent.command_processor.on_command({
        "text": "what are your drives?",
        "source": "text",
        "timestamp": 0.0
    })

    # Verify response
    assert len(responses) == 1
    assert "affiliation" in responses[0]["text"].lower() or "drive" in responses[0]["text"].lower()


@pytest.mark.asyncio
async def test_archetypal_modulation_on_sound(agent):
    """Ambient sound modulates archetype weights."""
    initial_self = agent.archetypal_modulator.current_weights["Self"]

    # Publish silence event
    agent.event_bus.publish("perception.audio.ambient", {
        "type": "silence",
        "volume": 0.0,
        "confidence": 0.95
    })

    # Self weight should increase
    assert agent.archetypal_modulator.current_weights["Self"] > initial_self


@pytest.mark.asyncio
async def test_psychological_state_affects_consultation(agent):
    """Low drives trigger fast consultation (threat state)."""
    # Set drives to low
    for drive in agent.drive_system.drives.values():
        drive.level = 0.2

    state = agent.command_processor._calculate_state()
    duration = agent.command_processor._get_consultation_duration(state)

    assert state == "threat"
    assert 0.5 <= duration <= 1.0


@pytest.mark.asyncio
async def test_high_harmony_triggers_calm_consultation(agent):
    """High drives and harmony trigger slow, contemplative consultation."""
    # Set drives to high
    for drive in agent.drive_system.drives.values():
        drive.level = 0.8

    agent.command_processor.last_harmony = 0.85

    state = agent.command_processor._calculate_state()
    duration = agent.command_processor._get_consultation_duration(state)

    assert state == "calm"
    assert 2.0 <= duration <= 4.0
```

### Step 2: Run integration tests

```bash
uv run pytest tests/integration/test_phase5_integration.py -v
```

Expected: 5 passed

### Step 3: Run full test suite

```bash
uv run pytest -v
```

Expected: All tests passing (should be 200+ total now)

### Step 4: Commit

```bash
git add tests/integration/test_phase5_integration.py
git commit -m "test: add Phase 5 integration tests

- Full command flow (text command → response)
- Archetypal modulation on ambient sound
- Psychological state affects consultation speed
- All integration tests passing"
```

---

## Task 16: Update Documentation

**Files:**
- Modify: `PROGRESS.md:300-400`
- Modify: `STATUS.md:1-50`
- Modify: `README.md:1-50`

### Step 1: Update PROGRESS.md with Phase 5 completion

Add Phase 5 section to PROGRESS.md:

```markdown
# PROGRESS.md
# Add after Phase 4 section

---

# Phase 5 Implementation Progress

## Completed Tasks (10/10)

✅ **Task 1: Text Command Input** (Commit: [hash])
- CommandInput widget in TUI
- Command history tracking
- Event publishing
- 3 tests passing

✅ **Task 2: Command Processor** (Commit: [hash])
- Psychological state calculation (threat/normal/calm)
- Archetypal command interpretation via LLM
- Ego classification synthesis
- Command routing (query/action/goal)
- 12 tests passing

✅ **Task 3: Query Handler** (Commit: [hash])
- Drive/thought/harmony/goal queries
- Formatted text responses
- 4 tests passing

✅ **Task 4: Audio Perception** (Commit: [hash])
- AdaptiveSampler (activity-based FPS)
- SoundClassifier (speech/noise/silence)
- Audio capture with sounddevice
- 6 tests passing

✅ **Task 5: Archetypal Modulation** (Commit: [hash])
- Acoustic environment → archetype weights
- Smooth weight transitions
- 5 tests passing

✅ **Task 6: Speech Recognition** (Commit: [hash])
- SpeechInput with faster-whisper
- Push-to-talk recording
- Lazy model loading
- 4 tests passing

✅ **Task 7: Agent Integration** (Commit: [hash])
- All Phase 5 systems initialized
- Audio perception in agent lifecycle
- Harmony tracking for command processor

✅ **Task 8: TUI Response Display** (Commit: [hash])
- Command response display
- Speech recording indicators
- Voice command transcriptions shown

✅ **Task 9: Configuration** (Commit: [hash])
- [commands], [audio], [archetypal_modulation] sections
- Documented all options

✅ **Task 10: Testing** (Commit: [hash])
- Integration tests for command flow
- All tests passing (200+ total)

**Total Tests Passing: 200+** ✓

## Phase 5 Complete! 🎉

All tasks successfully implemented. The agent now features:
- **Bidirectional Communication**: Text and voice commands
- **Archetypal Command Interpretation**: All archetypes weigh in on intent
- **Psychological State Responsiveness**: Consultation speed reflects threat vs calm
- **Embodied Acoustic Awareness**: Sound environment modulates consciousness
- **Query System**: Answer questions about internal state
- **Speech Recognition**: Local Whisper for voice input
- **Natural Language**: Free-form commands, not rigid syntax

### Statistics
- 20+ new files created
- ~3,500 lines of code added
- 200+ unit/integration tests (all passing)
- Type-safe with pyright validation
- Full event-driven integration

### Tagged Release
- Version: v0.5.0-phase5
- Branch: feature/phase5-social-interaction merged to master
```

### Step 2: Update STATUS.md

Update version and add Phase 5 to status:

```markdown
# STATUS.md
# Update header

**Current Version**: v0.5.0-phase5
**Status**: Social Interaction & Audio Perception Complete ✓
**Date**: 2026-02-04
**Tests**: 200+/200+ passing
```

Add Phase 5 to implemented systems section:

```markdown
### Phase 5: Social Interaction & Audio (v0.5.0)
✅ **Text Command Input** - TUI widget with history
✅ **Voice Commands** - Local Whisper speech recognition
✅ **Archetypal Interpretation** - Commands understood through multiple perspectives
✅ **Query System** - Answer state questions (drives/thoughts/harmony/goals)
✅ **Audio Perception** - Ambient sound monitoring with adaptive sampling
✅ **Archetypal Modulation** - Acoustic environment shapes consciousness
✅ **Psychological Responsiveness** - Consultation speed varies with state

**Tests**: 200+ passing
**Code**: 3,500 lines added (20+ files)
```

### Step 3: Update README.md

Update badges and feature list:

```markdown
# README.md
# Update badges

[![Tests](https://img.shields.io/badge/tests-200%2B-success)]()
[![Version](https://img.shields.io/badge/version-v0.5.0-blue)]()
```

Add to key features:

```markdown
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
```

### Step 4: Commit documentation

```bash
git add PROGRESS.md STATUS.md README.md
git commit -m "docs: update documentation for Phase 5 release

- PROGRESS.md with Phase 5 completion summary
- STATUS.md updated to v0.5.0-phase5
- README.md with new features and test counts
- All Phase 5 capabilities documented"
```

---

## Task 17: Final Verification & Tag Release

**Files:**
- None (verification only)

### Step 1: Run complete test suite

```bash
uv run pytest -v --tb=short
```

Expected: 200+ tests passing

### Step 2: Run type checking

```bash
uv run pyright src/
```

Expected: 0 errors

### Step 3: Run linting

```bash
uv run ruff check src/
```

Expected: No errors (or only minor warnings)

### Step 4: Test agent manually (if time permits)

```bash
# Only if you have microphone and Ollama running
uv run python main.py
```

Test:
- Type a command like "what are your drives?"
- Verify response appears
- Verify no crashes

### Step 5: Create final commit

```bash
git status  # Verify nothing uncommitted
```

If clean, proceed to merge and tag.

### Step 6: Switch to main repository and merge

```bash
cd /Users/kfowler/Projects/consciousness
git merge feature/phase5-social-interaction --no-ff -m "$(cat <<'EOF'
Merge Phase 5: Social Interaction & Audio Perception

Complete implementation of bidirectional communication and acoustic awareness:

**Core Features:**
- Text command input via TUI with history
- Voice command input via local Whisper (push-to-talk)
- Archetypal command interpretation (all archetypes weigh in)
- Psychological state-dependent consultation (threat: 0.5-1s, calm: 2-4s)
- Query system for state questions
- Ambient sound monitoring with adaptive sampling
- Archetypal activation modulation based on acoustic environment

**Key Subsystems:**
- CommandProcessor with full archetypal consultation flow
- QueryHandler for drive/thought/harmony/goal queries
- AudioPerception with speech/noise/silence classification
- ArchetypalModulator (sound shapes consciousness)
- SpeechInput with faster-whisper integration
- Enhanced TUI with command input and response display

**Testing:**
- 200+ unit and integration tests (all passing)
- Full command flow verified
- Type-safe with pyright validation
- Fully integrated into agent lifecycle

Closes Phase 5 implementation.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Step 7: Tag release

```bash
git tag -a v0.5.0-phase5 -m "$(cat <<'EOF'
Release v0.5.0: Phase 5 - Social Interaction & Audio Perception

Major milestone: Agent now engages in bidirectional communication and
exhibits embodied acoustic awareness.

## New Features

### Command System
- Text input via TUI with command history
- Voice input via local Whisper speech recognition (push-to-talk)
- Natural language understanding (free-form commands)
- Archetypal command interpretation (all archetypes weigh in)
- Ego classification synthesis (query/action/goal)
- Psychological state-dependent consultation speed

### Audio Perception
- Ambient sound monitoring with adaptive sampling
- Sound classification (speech/noise/silence)
- Zero-crossing rate for speech detection
- Activity-based FPS adjustment (1-10 FPS)

### Archetypal Modulation
- Acoustic environment modulates archetype weights
- Silence → Self/Anima boost (contemplation)
- Speech → Anima/Persona boost (social awareness)
- Loud noise → Shadow boost (survival mode)
- Smooth weight transitions via interpolation

### Query System
- Drive queries (current levels, thresholds)
- Thought queries (recent memories)
- Harmony queries (integration level, trends)
- Goal queries (active goals, priorities)
- Formatted text responses

## Statistics

- 3,500+ lines added across 20+ files
- 200+ unit and integration tests passing
- 20+ new subsystem files
- Full event bus integration
- Type-safe with pyright validation

## Architecture

Command flow:
Text/Voice input → archetypal consultation → Ego classification →
routing (query/action/goal) → execution → response

Ambient sound flow:
Audio capture → adaptive sampling → sound classification →
archetypal weight modulation → influences next consultation

## Configuration

New config sections:
- [commands]: consultation durations by psychological state
- [audio]: sample rate, Whisper model, push-to-talk key
- [archetypal_modulation]: weight boosts for each sound type

## Dependencies

New:
- faster-whisper: Local speech recognition
- sounddevice: Audio capture
- numpy: Signal processing

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Step 8: Verify tag and tests one final time

```bash
git log --oneline -5  # Verify merge and tag
uv run pytest -q  # Quick final test run
```

Expected: Clean history, all tests passing

### Step 9: Final status message

```bash
echo "Phase 5 complete! ✅"
echo "- Text and voice commands working"
echo "- Archetypal command interpretation operational"
echo "- Ambient sound monitoring active"
echo "- 200+ tests passing"
echo ""
echo "Agent is now fully interactive with embodied acoustic awareness!"
```

---

## Implementation Complete!

**Phase 5 is now fully implemented and tested.**

All 10 tasks completed:
1. ✅ Text Command Input
2. ✅ Command Processor & Archetypal Interpretation
3. ✅ Query Handler
4. ✅ Audio Perception System
5. ✅ Archetypal Modulation
6. ✅ Speech Recognition
7. ✅ Agent Integration
8. ✅ TUI Response Display
9. ✅ Configuration
10. ✅ Testing & Documentation

**The agent can now:**
- Accept text commands via TUI
- Accept voice commands via push-to-talk speech recognition
- Interpret commands through archetypal consultation
- Respond based on psychological state (threat = fast, calm = contemplative)
- Answer queries about its internal state
- Monitor ambient sound continuously
- Modulate archetypal activation based on acoustic environment
- Display responses and transcriptions in TUI

**Stats:**
- 200+ tests passing
- 3,500+ lines of code
- 20+ new files
- Full type safety
- Event-driven architecture

**Next Steps:**
User can now interact with the agent, ask questions, give commands, and observe how different acoustic environments shape its consciousness!
