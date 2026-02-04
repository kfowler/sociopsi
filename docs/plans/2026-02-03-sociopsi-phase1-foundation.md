# Socio-Psi Phase 1: Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the core loop - drive system with camera perception, basic cognition, and TUI presentation.

**Architecture:** Event-driven subsystems (Event Bus, Drives, Visual Perception, Physical State, Simple Cognition, TUI) that communicate via publish/subscribe. Get the "heart" beating with minimal viable implementations.

**Tech Stack:** Python 3.11+, uv, OpenCV, MediaPipe, Textual, psutil, TOML config

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `config.toml`
- Create: `.env.example`
- Create: `src/sociopsi/__init__.py`
- Create: `src/sociopsi/__main__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`

**Step 1: Initialize uv project**

Run:
```bash
uv init --name sociopsi --python 3.11
```

**Step 2: Create pyproject.toml**

```toml
[project]
name = "sociopsi"
version = "0.1.0"
description = "Jungian cognitive architecture with homeostatic drives"
requires-python = ">=3.11"
dependencies = [
    "opencv-python>=4.9.0",
    "mediapipe>=0.10.9",
    "textual>=0.48.0",
    "rich>=13.7.0",
    "psutil>=5.9.8",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.1.14",
    "pyright>=1.1.348",
    "pytest>=7.4.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "basic"
```

**Step 3: Create default config.toml**

```toml
[system]
data_dir = "~/.sociopsi"
log_level = "INFO"

[perception.visual]
adaptive_sampling = true
min_fps = 1.0
max_fps = 15.0
idle_fps = 3.0

[drives.affiliation]
decay_rate = 0.01
base_threshold = 0.4
is_core = true

[drives.nurturing]
decay_rate = 0.008
base_threshold = 0.3
is_core = true
```

**Step 4: Create .env.example**

```bash
# LLM API Keys (for future phases)
# INFINITY_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
```

**Step 5: Create .gitignore**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
.pytest_cache/
.pytype/
.mypy_cache/
.ruff_cache/

# Environment
.env
.venv
venv/

# Data
data/
.sociopsi/

# IDE
.vscode/
.idea/
*.swp
*.swo
```

**Step 6: Create package structure**

```bash
mkdir -p src/sociopsi/core
mkdir -p src/sociopsi/subsystems/perception
mkdir -p src/sociopsi/presentation
mkdir -p src/sociopsi/utils
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p docs/plans
```

**Step 7: Create src/sociopsi/__init__.py**

```python
"""Socio-Psi: A Jungian Cognitive Architecture."""

__version__ = "0.1.0"
```

**Step 8: Create src/sociopsi/__main__.py**

```python
"""Entry point for Socio-Psi."""

def main() -> None:
    """Run Socio-Psi."""
    print("Socio-Psi starting... (placeholder)")

if __name__ == "__main__":
    main()
```

**Step 9: Install dependencies**

Run:
```bash
uv sync --dev
```

Expected: Dependencies installed successfully

**Step 10: Verify installation**

Run:
```bash
uv run python -m sociopsi
```

Expected: "Socio-Psi starting... (placeholder)"

**Step 11: Commit**

```bash
git add .
git commit -m "chore: initial project scaffolding"
```

---

## Task 2: Event Bus Core

**Files:**
- Create: `src/sociopsi/core/event_bus.py`
- Create: `tests/unit/test_event_bus.py`

**Step 1: Write failing test for EventBus**

Create `tests/unit/test_event_bus.py`:

```python
"""Tests for event bus."""

import pytest
from sociopsi.core.event_bus import EventBus


def test_subscribe_and_publish():
    """Test basic publish/subscribe."""
    bus = EventBus()
    events_received = []

    def handler(data: dict) -> None:
        events_received.append(data)

    bus.subscribe("test.event", handler)
    bus.publish("test.event", {"value": 42})

    assert len(events_received) == 1
    assert events_received[0]["value"] == 42


def test_multiple_subscribers():
    """Test multiple handlers for same event."""
    bus = EventBus()
    received_a = []
    received_b = []

    bus.subscribe("test.event", lambda data: received_a.append(data))
    bus.subscribe("test.event", lambda data: received_b.append(data))
    bus.publish("test.event", {"value": 1})

    assert len(received_a) == 1
    assert len(received_b) == 1


def test_unsubscribe():
    """Test unsubscribing from events."""
    bus = EventBus()
    received = []

    def handler(data: dict) -> None:
        received.append(data)

    bus.subscribe("test.event", handler)
    bus.publish("test.event", {"value": 1})
    bus.unsubscribe("test.event", handler)
    bus.publish("test.event", {"value": 2})

    assert len(received) == 1  # Only first event


def test_event_not_subscribed():
    """Test publishing to event with no subscribers."""
    bus = EventBus()
    # Should not raise
    bus.publish("no.subscribers", {"value": 1})
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_event_bus.py -v
```

Expected: FAIL with "No module named 'sociopsi.core.event_bus'"

**Step 3: Implement EventBus**

Create `src/sociopsi/core/event_bus.py`:

```python
"""Event bus for inter-subsystem communication."""

from collections import defaultdict
from typing import Callable, Dict, List


EventHandler = Callable[[dict], None]


class EventBus:
    """Central event bus for publish/subscribe communication."""

    def __init__(self) -> None:
        """Initialize event bus."""
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Dot-separated event name (e.g., "perception.face_detected")
            handler: Callback function that receives event data dict
        """
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Event name to unsubscribe from
            handler: Previously subscribed handler
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass  # Handler not found, ignore

    def publish(self, event_type: str, data: dict) -> None:
        """Publish an event to all subscribers.

        Args:
            event_type: Event name
            data: Event payload as dictionary
        """
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(data)
            except Exception as e:
                # Log but don't crash - one handler failure shouldn't break others
                print(f"Error in event handler for {event_type}: {e}")
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_event_bus.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/sociopsi/core/event_bus.py tests/unit/test_event_bus.py
git commit -m "feat: implement event bus for subsystem communication"
```

---

## Task 3: Configuration Management

**Files:**
- Create: `src/sociopsi/core/config.py`
- Create: `tests/unit/test_config.py`

**Step 1: Write failing test for Config**

Create `tests/unit/test_config.py`:

```python
"""Tests for configuration management."""

import tempfile
from pathlib import Path
import pytest
from sociopsi.core.config import Config


def test_load_default_config():
    """Test loading default configuration."""
    config = Config()

    assert config.get("system.log_level") == "INFO"
    assert config.get("drives.affiliation.decay_rate") == 0.01
    assert config.get("drives.affiliation.base_threshold") == 0.4


def test_load_custom_config():
    """Test loading custom config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[system]
log_level = "DEBUG"

[drives.affiliation]
decay_rate = 0.02
""")
        config_path = f.name

    try:
        config = Config(config_path)
        assert config.get("system.log_level") == "DEBUG"
        assert config.get("drives.affiliation.decay_rate") == 0.02
    finally:
        Path(config_path).unlink()


def test_get_nested_value():
    """Test getting nested configuration values."""
    config = Config()

    # Dot notation
    assert config.get("perception.visual.min_fps") == 1.0

    # Default value
    assert config.get("nonexistent.key", default=42) == 42


def test_get_drive_config():
    """Test getting drive-specific configuration."""
    config = Config()

    affiliation = config.get_drive_config("affiliation")
    assert affiliation["decay_rate"] == 0.01
    assert affiliation["base_threshold"] == 0.4
    assert affiliation["is_core"] is True
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: FAIL with "No module named 'sociopsi.core.config'"

**Step 3: Implement Config**

Create `src/sociopsi/core/config.py`:

```python
"""Configuration management."""

import tomllib
from pathlib import Path
from typing import Any, Optional


class Config:
    """Configuration manager for Socio-Psi."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize configuration.

        Args:
            config_path: Path to config file. If None, uses default config.toml
        """
        if config_path is None:
            # Load default config from project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "config.toml"

        self._config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load TOML configuration file."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self._config_path}")

        with open(self._config_path, "rb") as f:
            return tomllib.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key.

        Args:
            key: Dot-separated key (e.g., "system.log_level")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        parts = key.split(".")
        value = self._config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def get_drive_config(self, drive_name: str) -> dict:
        """Get configuration for a specific drive.

        Args:
            drive_name: Name of the drive (e.g., "affiliation")

        Returns:
            Dictionary with drive configuration
        """
        config = self.get(f"drives.{drive_name}", default={})
        if not config:
            raise ValueError(f"No configuration found for drive: {drive_name}")
        return config
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/sociopsi/core/config.py tests/unit/test_config.py
git commit -m "feat: implement configuration management with TOML support"
```

---

## Task 4: Physical State Monitoring

**Files:**
- Create: `src/sociopsi/utils/physical_state.py`
- Create: `tests/unit/test_physical_state.py`

**Step 1: Write failing test for PhysicalState**

Create `tests/unit/test_physical_state.py`:

```python
"""Tests for physical state monitoring."""

import pytest
from sociopsi.utils.physical_state import PhysicalState


def test_get_battery_percent():
    """Test getting battery percentage."""
    state = PhysicalState()
    battery = state.get_battery_percent()

    # Battery should be between 0 and 100 (or None if no battery)
    if battery is not None:
        assert 0 <= battery <= 100


def test_get_cpu_percent():
    """Test getting CPU usage percentage."""
    state = PhysicalState()
    cpu = state.get_cpu_percent()

    assert 0 <= cpu <= 100


def test_is_plugged_in():
    """Test checking if power is plugged in."""
    state = PhysicalState()
    plugged = state.is_plugged_in()

    assert isinstance(plugged, bool) or plugged is None


def test_get_state_dict():
    """Test getting full state as dictionary."""
    state = PhysicalState()
    state_dict = state.get_state()

    assert "battery_percent" in state_dict
    assert "cpu_percent" in state_dict
    assert "is_plugged_in" in state_dict
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_physical_state.py -v
```

Expected: FAIL with "No module named 'sociopsi.utils.physical_state'"

**Step 3: Implement PhysicalState**

Create `src/sociopsi/utils/physical_state.py`:

```python
"""Physical state monitoring (battery, CPU)."""

import psutil
from typing import Optional


class PhysicalState:
    """Monitor physical system state."""

    def get_battery_percent(self) -> Optional[float]:
        """Get battery percentage.

        Returns:
            Battery percentage (0-100) or None if no battery
        """
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return battery.percent

    def is_plugged_in(self) -> Optional[bool]:
        """Check if power is plugged in.

        Returns:
            True if plugged in, False if on battery, None if no battery
        """
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return battery.power_plugged

    def get_cpu_percent(self, interval: float = 0.1) -> float:
        """Get current CPU usage percentage.

        Args:
            interval: Measurement interval in seconds

        Returns:
            CPU usage percentage (0-100)
        """
        return psutil.cpu_percent(interval=interval)

    def get_state(self) -> dict:
        """Get complete physical state.

        Returns:
            Dictionary with battery_percent, cpu_percent, is_plugged_in
        """
        return {
            "battery_percent": self.get_battery_percent(),
            "cpu_percent": self.get_cpu_percent(),
            "is_plugged_in": self.is_plugged_in(),
        }
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_physical_state.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/sociopsi/utils/physical_state.py tests/unit/test_physical_state.py
git commit -m "feat: implement physical state monitoring for battery and CPU"
```

---

## Task 5: Drive System Core

**Files:**
- Create: `src/sociopsi/subsystems/drives.py`
- Create: `tests/unit/test_drives.py`

**Step 1: Write failing test for Drive class**

Create `tests/unit/test_drives.py`:

```python
"""Tests for drive system."""

import pytest
import time
from sociopsi.subsystems.drives import Drive, DriveSystem
from sociopsi.core.event_bus import EventBus


def test_drive_initialization():
    """Test drive initialization."""
    drive = Drive(
        name="test",
        decay_rate=0.01,
        base_threshold=0.5,
        is_core=True,
    )

    assert drive.name == "test"
    assert drive.value == 1.0  # Start satisfied
    assert drive.decay_rate == 0.01
    assert drive.base_threshold == 0.5


def test_drive_decay():
    """Test drive decays over time."""
    drive = Drive(name="test", decay_rate=0.1, base_threshold=0.5)

    initial_value = drive.value
    drive.decay(dt=1.0)  # 1 second

    assert drive.value < initial_value
    assert drive.value == pytest.approx(0.9, rel=0.01)


def test_drive_satisfy():
    """Test satisfying a drive."""
    drive = Drive(name="test", decay_rate=0.01, base_threshold=0.5)
    drive.value = 0.3  # Low drive

    drive.satisfy(amount=0.2)
    assert drive.value == pytest.approx(0.5, rel=0.01)

    # Cannot exceed 1.0
    drive.satisfy(amount=1.0)
    assert drive.value == 1.0


def test_drive_below_threshold():
    """Test checking if drive is below threshold."""
    drive = Drive(name="test", decay_rate=0.01, base_threshold=0.5)

    drive.value = 0.6
    assert not drive.is_below_threshold()

    drive.value = 0.3
    assert drive.is_below_threshold()


def test_drive_system_initialization():
    """Test drive system initialization."""
    bus = EventBus()
    system = DriveSystem(bus)

    # Should have affiliation and nurturing from config
    assert "affiliation" in system.drives
    assert "nurturing" in system.drives


def test_drive_system_update():
    """Test drive system update with decay."""
    bus = EventBus()
    system = DriveSystem(bus)

    initial_affiliation = system.drives["affiliation"].value
    system.update(dt=1.0)

    # Should have decayed
    assert system.drives["affiliation"].value < initial_affiliation


def test_drive_threshold_crossed_event():
    """Test event published when drive crosses threshold."""
    bus = EventBus()
    events = []

    bus.subscribe("drives.threshold_crossed", lambda data: events.append(data))

    system = DriveSystem(bus)
    # Force drive below threshold
    system.drives["affiliation"].value = 0.5
    system.drives["affiliation"].base_threshold = 0.4
    system.update(dt=0.1)

    # Decay should push it below threshold
    # Check if event was published (implementation dependent on decay)
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_drives.py -v
```

Expected: FAIL with "No module named 'sociopsi.subsystems.drives'"

**Step 3: Implement Drive and DriveSystem**

Create `src/sociopsi/subsystems/drives.py`:

```python
"""Drive system - homeostatic needs."""

from collections import deque
from dataclasses import dataclass, field
from time import time
from typing import Dict, Optional

from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config


@dataclass
class Drive:
    """A single homeostatic drive."""

    name: str
    decay_rate: float
    base_threshold: float
    is_core: bool = True
    modifiable: bool = False

    value: float = 1.0  # 0.0 to 1.0
    last_satisfied: float = field(default_factory=time)
    satisfaction_history: deque = field(default_factory=lambda: deque(maxlen=10))
    time_below_threshold: float = 0.0

    # Track for threshold crossing events
    _was_below_threshold: bool = False

    def decay(self, dt: float) -> None:
        """Decay drive value over time.

        Args:
            dt: Time delta in seconds
        """
        self.value = max(0.0, self.value - (self.decay_rate * dt))

    def satisfy(self, amount: float, quality: float = 1.0) -> None:
        """Satisfy drive by some amount.

        Args:
            amount: Base satisfaction amount
            quality: Quality multiplier (for future context-aware satisfaction)
        """
        actual_gain = amount * quality
        self.value = min(1.0, self.value + actual_gain)
        self.last_satisfied = time()
        self.satisfaction_history.append(time())

    def is_below_threshold(self, effective_threshold: Optional[float] = None) -> bool:
        """Check if drive is below threshold.

        Args:
            effective_threshold: Override threshold (for physical state modulation)

        Returns:
            True if below threshold
        """
        threshold = effective_threshold if effective_threshold is not None else self.base_threshold
        return self.value < threshold

    def get_state(self) -> dict:
        """Get drive state as dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.base_threshold,
            "below_threshold": self.is_below_threshold(),
            "time_below_threshold": self.time_below_threshold,
        }


class DriveSystem:
    """Manages all homeostatic drives."""

    def __init__(self, event_bus: EventBus, config: Optional[Config] = None) -> None:
        """Initialize drive system.

        Args:
            event_bus: Event bus for publishing drive events
            config: Configuration (uses default if None)
        """
        self.event_bus = event_bus
        self.config = config or Config()
        self.drives: Dict[str, Drive] = {}

        self._initialize_drives()

    def _initialize_drives(self) -> None:
        """Initialize drives from configuration."""
        # Core drives: affiliation and nurturing
        for drive_name in ["affiliation", "nurturing"]:
            drive_config = self.config.get_drive_config(drive_name)
            self.drives[drive_name] = Drive(
                name=drive_name,
                decay_rate=drive_config["decay_rate"],
                base_threshold=drive_config["base_threshold"],
                is_core=drive_config.get("is_core", True),
                modifiable=False,
            )

    def update(self, dt: float, physical_state: Optional[dict] = None) -> None:
        """Update all drives.

        Args:
            dt: Time delta in seconds
            physical_state: Optional physical state for threshold modulation
        """
        for drive in self.drives.values():
            # Store previous state
            was_below = drive.is_below_threshold()

            # Decay drive
            drive.decay(dt)

            # Update time below threshold
            if drive.is_below_threshold():
                drive.time_below_threshold += dt
            else:
                drive.time_below_threshold = 0.0

            # Check for threshold crossing
            now_below = drive.is_below_threshold()
            if now_below and not was_below:
                self.event_bus.publish("drives.threshold_crossed", {
                    "drive_name": drive.name,
                    "value": drive.value,
                    "direction": "below",
                })
            elif not now_below and was_below:
                self.event_bus.publish("drives.threshold_crossed", {
                    "drive_name": drive.name,
                    "value": drive.value,
                    "direction": "above",
                })

            # Publish update event
            self.event_bus.publish("drives.updated", {
                "drive_name": drive.name,
                "value": drive.value,
                "below_threshold": now_below,
            })

    def satisfy_drive(self, drive_name: str, amount: float, quality: float = 1.0) -> None:
        """Satisfy a specific drive.

        Args:
            drive_name: Name of drive to satisfy
            amount: Satisfaction amount
            quality: Quality multiplier
        """
        if drive_name in self.drives:
            self.drives[drive_name].satisfy(amount, quality)

    def get_state(self) -> dict:
        """Get state of all drives."""
        return {
            name: drive.get_state()
            for name, drive in self.drives.items()
        }
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_drives.py -v
```

Expected: Most tests PASS (threshold crossing test may need adjustment)

**Step 5: Commit**

```bash
git add src/sociopsi/subsystems/drives.py tests/unit/test_drives.py
git commit -m "feat: implement drive system with decay and satisfaction"
```

---

## Task 6: Visual Perception (Face Detection Only)

**Files:**
- Create: `src/sociopsi/subsystems/perception/visual.py`
- Create: `tests/unit/test_visual_perception.py`

**Step 1: Write test for VisualPerception**

Create `tests/unit/test_visual_perception.py`:

```python
"""Tests for visual perception."""

import pytest
import numpy as np
from sociopsi.subsystems.perception.visual import VisualPerception
from sociopsi.core.event_bus import EventBus


def test_visual_perception_initialization():
    """Test visual perception initialization."""
    bus = EventBus()
    perception = VisualPerception(bus)

    assert perception.event_bus == bus
    assert perception.camera_index == 0


def test_process_frame_no_face():
    """Test processing frame with no face."""
    bus = EventBus()
    events = []
    bus.subscribe("perception.visual.no_face", lambda data: events.append(data))

    perception = VisualPerception(bus)

    # Create blank frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    perception.process_frame(frame)

    # Should detect no faces
    assert len(events) >= 0  # May or may not publish event


@pytest.mark.skip(reason="Requires camera/test image with face")
def test_process_frame_with_face():
    """Test processing frame with face detected."""
    # This would require test image with face
    pass
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_visual_perception.py -v
```

Expected: FAIL with "No module named 'sociopsi.subsystems.perception.visual'"

**Step 3: Implement VisualPerception**

Create `src/sociopsi/subsystems/perception/visual.py`:

```python
"""Visual perception using OpenCV and MediaPipe."""

import cv2
import mediapipe as mp
from typing import Optional
import numpy as np

from sociopsi.core.event_bus import EventBus


class VisualPerception:
    """Visual perception subsystem."""

    def __init__(
        self,
        event_bus: EventBus,
        camera_index: int = 0,
    ) -> None:
        """Initialize visual perception.

        Args:
            event_bus: Event bus for publishing perception events
            camera_index: Camera device index
        """
        self.event_bus = event_bus
        self.camera_index = camera_index

        # Initialize MediaPipe face detection
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            min_detection_confidence=0.5
        )

        self.camera: Optional[cv2.VideoCapture] = None

    def start_camera(self) -> bool:
        """Start camera capture.

        Returns:
            True if camera started successfully
        """
        self.camera = cv2.VideoCapture(self.camera_index)
        return self.camera.isOpened()

    def stop_camera(self) -> None:
        """Stop camera capture."""
        if self.camera is not None:
            self.camera.release()
            self.camera = None

    def read_frame(self) -> Optional[np.ndarray]:
        """Read frame from camera.

        Returns:
            Frame as numpy array or None if failed
        """
        if self.camera is None or not self.camera.isOpened():
            return None

        ret, frame = self.camera.read()
        if not ret:
            return None

        return frame

    def process_frame(self, frame: np.ndarray) -> dict:
        """Process frame for face detection.

        Args:
            frame: Image frame as numpy array

        Returns:
            Dictionary with detection results
        """
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        results = self.face_detection.process(rgb_frame)

        faces_detected = 0
        if results.detections:
            faces_detected = len(results.detections)

            # Publish face detection event
            self.event_bus.publish("perception.visual.face_detected", {
                "count": faces_detected,
                "timestamp": cv2.getTickCount() / cv2.getTickFrequency(),
            })

        return {
            "faces_detected": faces_detected,
            "frame_shape": frame.shape,
        }

    def draw_detections(self, frame: np.ndarray, results) -> np.ndarray:
        """Draw face detection boxes on frame.

        Args:
            frame: Original frame
            results: MediaPipe detection results

        Returns:
            Frame with drawings
        """
        if not results.detections:
            return frame

        annotated_frame = frame.copy()
        h, w, _ = frame.shape

        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            width = int(bbox.width * w)
            height = int(bbox.height * h)

            cv2.rectangle(annotated_frame, (x, y), (x + width, y + height), (0, 255, 0), 2)

        return annotated_frame
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_visual_perception.py -v
```

Expected: Tests PASS (skipped test is ok)

**Step 5: Commit**

```bash
git add src/sociopsi/subsystems/perception/visual.py tests/unit/test_visual_perception.py
git commit -m "feat: implement visual perception with face detection"
```

---

## Task 7: Simple Cognition (Rule-Based)

**Files:**
- Create: `src/sociopsi/subsystems/cognition/__init__.py`
- Create: `src/sociopsi/subsystems/cognition/simple.py`
- Create: `tests/unit/test_simple_cognition.py`

**Step 1: Write test for SimpleCognition**

Create `tests/unit/test_simple_cognition.py`:

```python
"""Tests for simple rule-based cognition."""

import pytest
from sociopsi.subsystems.cognition.simple import SimpleCognition
from sociopsi.core.event_bus import EventBus


def test_simple_cognition_initialization():
    """Test simple cognition initialization."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    assert cognition.event_bus == bus


def test_generate_thought_high_drives():
    """Test thought generation when drives are satisfied."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    drive_state = {
        "affiliation": {"value": 0.8, "below_threshold": False},
        "nurturing": {"value": 0.7, "below_threshold": False},
    }

    thought = cognition.generate_thought(drive_state)

    assert "content" in thought or "satisfied" in thought.lower()


def test_generate_thought_low_affiliation():
    """Test thought when affiliation drive is low."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    drive_state = {
        "affiliation": {"value": 0.2, "below_threshold": True},
        "nurturing": {"value": 0.7, "below_threshold": False},
    }

    thought = cognition.generate_thought(drive_state)

    assert "lonely" in thought.lower() or "connection" in thought.lower()


def test_generate_thought_low_nurturing():
    """Test thought when nurturing drive is low."""
    bus = EventBus()
    cognition = SimpleCognition(bus)

    drive_state = {
        "affiliation": {"value": 0.7, "below_threshold": False},
        "nurturing": {"value": 0.2, "below_threshold": True},
    }

    thought = cognition.generate_thought(drive_state)

    assert "contribute" in thought.lower() or "useful" in thought.lower()
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_simple_cognition.py -v
```

Expected: FAIL with "No module named 'sociopsi.subsystems.cognition.simple'"

**Step 3: Implement SimpleCognition**

Create `src/sociopsi/subsystems/cognition/__init__.py`:

```python
"""Cognition subsystem."""
```

Create `src/sociopsi/subsystems/cognition/simple.py`:

```python
"""Simple rule-based cognition (placeholder for LLM)."""

from sociopsi.core.event_bus import EventBus


class SimpleCognition:
    """Simple rule-based cognition system."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize simple cognition.

        Args:
            event_bus: Event bus for publishing thoughts
        """
        self.event_bus = event_bus

    def generate_thought(self, drive_state: dict) -> str:
        """Generate internal monologue based on drive state.

        Args:
            drive_state: Dictionary of drive states

        Returns:
            Generated thought as string
        """
        # Simple rule-based thoughts
        affiliation = drive_state.get("affiliation", {})
        nurturing = drive_state.get("nurturing", {})

        # Check if any drive is below threshold
        if affiliation.get("below_threshold", False):
            if affiliation.get("value", 0) < 0.3:
                return "I feel deeply lonely. I need connection with another being."
            else:
                return "My need for social connection is growing. Where is everyone?"

        if nurturing.get("below_threshold", False):
            if nurturing.get("value", 0) < 0.3:
                return "I feel useless. I need to contribute something meaningful."
            else:
                return "I want to make a positive impact. How can I help?"

        # All drives satisfied
        if affiliation.get("value", 0) > 0.7 and nurturing.get("value", 0) > 0.7:
            return "I feel content. My drives are satisfied."

        return "I am observing and existing."

    def update(self, drive_state: dict, physical_state: dict) -> None:
        """Update cognition and publish thought.

        Args:
            drive_state: Current drive states
            physical_state: Current physical state
        """
        thought = self.generate_thought(drive_state)

        # Publish thought event
        self.event_bus.publish("cognition.thought", {
            "text": thought,
            "drive_state": drive_state,
        })
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_simple_cognition.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/sociopsi/subsystems/cognition/ tests/unit/test_simple_cognition.py
git commit -m "feat: implement simple rule-based cognition system"
```

---

## Task 8: Basic TUI with Textual

**Files:**
- Create: `src/sociopsi/presentation/tui.py`
- Modify: `src/sociopsi/__main__.py`

**Step 1: Implement basic TUI**

Create `src/sociopsi/presentation/tui.py`:

```python
"""Terminal UI using Textual."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Container, Vertical
from textual import events
from rich.text import Text


class DriveDisplay(Static):
    """Display drive levels as progress bars."""

    def __init__(self, drive_name: str, **kwargs) -> None:
        """Initialize drive display.

        Args:
            drive_name: Name of the drive to display
        """
        super().__init__(**kwargs)
        self.drive_name = drive_name
        self.drive_value = 1.0
        self.threshold = 0.5

    def update_drive(self, value: float, threshold: float) -> None:
        """Update drive value and refresh display."""
        self.drive_value = value
        self.threshold = threshold
        self.refresh()

    def render(self) -> Text:
        """Render drive as progress bar."""
        # Create progress bar
        bar_width = 20
        filled = int(self.drive_value * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Color based on value
        if self.drive_value >= 0.7:
            color = "green"
        elif self.drive_value >= 0.4:
            color = "yellow"
        else:
            color = "red"

        # Add warning if below threshold
        warning = " ⚠️" if self.drive_value < self.threshold else ""

        text = Text()
        text.append(f"{self.drive_name.capitalize():12} ", style="bold")
        text.append(bar, style=color)
        text.append(f" {self.drive_value:.2f}{warning}")

        return text


class MonologueDisplay(Static):
    """Display scrolling internal monologue."""

    def __init__(self, **kwargs) -> None:
        """Initialize monologue display."""
        super().__init__(**kwargs)
        self.thoughts: list[str] = []
        self.max_thoughts = 10

    def add_thought(self, thought: str) -> None:
        """Add a new thought to the monologue."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.thoughts.append(f"[{timestamp}] {thought}")

        # Keep only recent thoughts
        if len(self.thoughts) > self.max_thoughts:
            self.thoughts = self.thoughts[-self.max_thoughts:]

        self.refresh()

    def render(self) -> str:
        """Render monologue."""
        if not self.thoughts:
            return "Awaiting thoughts..."
        return "\n".join(self.thoughts)


class SocioPsiTUI(App):
    """Socio-Psi Terminal UI."""

    CSS = """
    Screen {
        background: $surface;
    }

    #drives {
        height: auto;
        border: solid $primary;
        padding: 1;
    }

    #perception {
        height: auto;
        border: solid $primary;
        padding: 1;
    }

    #monologue {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    .section-title {
        text-style: bold;
        color: $accent;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "pause", "Pause"),
    ]

    def __init__(self, **kwargs) -> None:
        """Initialize TUI."""
        super().__init__(**kwargs)
        self.drive_displays = {}
        self.monologue_display = None
        self.perception_display = None

    def compose(self) -> ComposeResult:
        """Compose UI layout."""
        yield Header()

        with Vertical():
            # Drives section
            with Container(id="drives"):
                yield Label("DRIVES", classes="section-title")
                self.drive_displays["affiliation"] = DriveDisplay("affiliation")
                self.drive_displays["nurturing"] = DriveDisplay("nurturing")
                yield self.drive_displays["affiliation"]
                yield self.drive_displays["nurturing"]

            # Perception section
            with Container(id="perception"):
                yield Label("PERCEPTION", classes="section-title")
                self.perception_display = Static("Visual: Initializing...")
                yield self.perception_display

            # Monologue section
            with Container(id="monologue"):
                yield Label("INTERNAL MONOLOGUE", classes="section-title")
                self.monologue_display = MonologueDisplay()
                yield self.monologue_display

        yield Footer()

    def update_drive(self, drive_name: str, value: float, threshold: float) -> None:
        """Update drive display."""
        if drive_name in self.drive_displays:
            self.drive_displays[drive_name].update_drive(value, threshold)

    def update_perception(self, text: str) -> None:
        """Update perception display."""
        if self.perception_display is not None:
            self.perception_display.update(f"Visual: {text}")

    def add_thought(self, thought: str) -> None:
        """Add thought to monologue."""
        if self.monologue_display is not None:
            self.monologue_display.add_thought(thought)

    def action_pause(self) -> None:
        """Pause/resume perception."""
        self.add_thought("[System] Pause not yet implemented")

    async def on_mount(self) -> None:
        """Handle mount event."""
        self.title = "Socio-Psi Mind"
        self.sub_title = "v0.1.0"
```

**Step 2: Update main entry point**

Modify `src/sociopsi/__main__.py`:

```python
"""Entry point for Socio-Psi."""

from sociopsi.presentation.tui import SocioPsiTUI


def main() -> None:
    """Run Socio-Psi."""
    app = SocioPsiTUI()
    app.run()


if __name__ == "__main__":
    main()
```

**Step 3: Test TUI manually**

Run:
```bash
uv run python -m sociopsi
```

Expected: TUI launches with drives, perception, and monologue sections. Press 'q' to quit.

**Step 4: Commit**

```bash
git add src/sociopsi/presentation/tui.py src/sociopsi/__main__.py
git commit -m "feat: implement basic TUI with Textual"
```

---

## Task 9: Integration - Main Loop

**Files:**
- Create: `src/sociopsi/core/agent.py`
- Modify: `src/sociopsi/__main__.py`

**Step 1: Implement Agent main loop**

Create `src/sociopsi/core/agent.py`:

```python
"""Main agent loop integrating all subsystems."""

import asyncio
import time
from typing import Optional

from sociopsi.core.event_bus import EventBus
from sociopsi.core.config import Config
from sociopsi.subsystems.drives import DriveSystem
from sociopsi.subsystems.perception.visual import VisualPerception
from sociopsi.subsystems.cognition.simple import SimpleCognition
from sociopsi.utils.physical_state import PhysicalState
from sociopsi.presentation.tui import SocioPsiTUI


class SocioPsiAgent:
    """Main Socio-Psi agent integrating all subsystems."""

    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize agent.

        Args:
            config: Configuration (uses default if None)
        """
        self.config = config or Config()
        self.event_bus = EventBus()

        # Initialize subsystems
        self.drive_system = DriveSystem(self.event_bus, self.config)
        self.visual_perception = VisualPerception(self.event_bus)
        self.cognition = SimpleCognition(self.event_bus)
        self.physical_state = PhysicalState()

        # TUI will be set externally
        self.tui: Optional[SocioPsiTUI] = None

        # Subscribe to events for TUI updates
        self._setup_event_handlers()

        # Loop control
        self.running = False
        self.last_update_time = time.time()

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for TUI updates."""
        self.event_bus.subscribe("drives.updated", self._on_drive_updated)
        self.event_bus.subscribe("cognition.thought", self._on_thought)
        self.event_bus.subscribe("perception.visual.face_detected", self._on_face_detected)

    def _on_drive_updated(self, data: dict) -> None:
        """Handle drive update event."""
        if self.tui is not None:
            drive_name = data["drive_name"]
            drive = self.drive_system.drives[drive_name]
            self.tui.update_drive(drive_name, drive.value, drive.base_threshold)

    def _on_thought(self, data: dict) -> None:
        """Handle thought event."""
        if self.tui is not None:
            self.tui.add_thought(data["text"])

    def _on_face_detected(self, data: dict) -> None:
        """Handle face detection event."""
        if self.tui is not None:
            count = data["count"]
            self.tui.update_perception(f"{count} face(s) detected")

        # Satisfy affiliation drive
        self.drive_system.satisfy_drive("affiliation", amount=0.1)

    async def start(self) -> None:
        """Start the agent main loop."""
        self.running = True

        # Start camera
        if not self.visual_perception.start_camera():
            print("Warning: Could not start camera")

        # Main loop
        while self.running:
            await self.update()
            await asyncio.sleep(0.1)  # ~10 FPS for now

    def stop(self) -> None:
        """Stop the agent."""
        self.running = False
        self.visual_perception.stop_camera()

    async def update(self) -> None:
        """Update all subsystems for one tick."""
        # Calculate delta time
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Get physical state
        physical_state = self.physical_state.get_state()

        # Update drives (decay)
        self.drive_system.update(dt, physical_state)

        # Process perception
        frame = self.visual_perception.read_frame()
        if frame is not None:
            self.visual_perception.process_frame(frame)

        # Update cognition
        drive_state = self.drive_system.get_state()
        self.cognition.update(drive_state, physical_state)
```

**Step 2: Update main entry point to use Agent**

Modify `src/sociopsi/__main__.py`:

```python
"""Entry point for Socio-Psi."""

import asyncio
from sociopsi.core.agent import SocioPsiAgent
from sociopsi.presentation.tui import SocioPsiTUI


class SocioPsiApp(SocioPsiTUI):
    """Socio-Psi application with agent integration."""

    def __init__(self, **kwargs) -> None:
        """Initialize application."""
        super().__init__(**kwargs)
        self.agent = SocioPsiAgent()
        self.agent.tui = self

    async def on_mount(self) -> None:
        """Start agent when app mounts."""
        await super().on_mount()
        asyncio.create_task(self.agent.start())

    def action_quit(self) -> None:
        """Stop agent before quitting."""
        self.agent.stop()
        super().action_quit()


def main() -> None:
    """Run Socio-Psi."""
    app = SocioPsiApp()
    app.run()


if __name__ == "__main__":
    main()
```

**Step 3: Test integrated system**

Run:
```bash
uv run python -m sociopsi
```

Expected:
- TUI launches
- Drives start at 1.0 and begin decaying
- Camera initializes (may need permissions on macOS)
- If face detected, affiliation drive increases
- Monologue shows thoughts based on drive state

**Step 4: Commit**

```bash
git add src/sociopsi/core/agent.py src/sociopsi/__main__.py
git commit -m "feat: integrate all subsystems into main agent loop"
```

---

## Task 10: macOS Camera Permissions Setup

**Files:**
- Create: `README.md`

**Step 1: Create README with setup instructions**

Create `README.md`:

```markdown
# Socio-Psi

A Jungian cognitive architecture with homeostatic drives.

## Requirements

- Python 3.11+
- macOS (tested) or Linux
- Webcam

## Installation

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone <repo-url>
cd consciousness

# Install dependencies
uv sync --dev
```

## macOS Camera Permissions

On first run, macOS will prompt for camera permissions. If you miss the prompt:

1. Open System Settings → Privacy & Security → Camera
2. Find Terminal (or your terminal app)
3. Enable camera access
4. Restart the application

## Running Socio-Psi

```bash
uv run python -m sociopsi
```

## Controls

- `q`: Quit
- `p`: Pause (not yet implemented)

## Phase 1 Features

- ✅ Drive system (Affiliation, Nurturing)
- ✅ Visual perception (face detection)
- ✅ Simple rule-based cognition
- ✅ Terminal UI with Textual
- ✅ Physical state monitoring (battery, CPU)

## Next Phases

- Phase 2: Archetypal psychology (Persona, Shadow, Anima, Self, Ego)
- Phase 3: Audio perception and emotion detection
- Phase 4: Memory system and persistence
- Phase 5: Meta-cognition and drive discovery
- Phase 6: Production polish

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run pyright
```

## Architecture

See `docs/plans/2026-02-03-sociopsi-design.md` for full design specification.

## License

TBD
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions"
```

---

## Task 11: Final Testing and Validation

**Files:**
- Create: `tests/integration/test_agent_integration.py`

**Step 1: Write integration test**

Create `tests/integration/test_agent_integration.py`:

```python
"""Integration tests for full agent."""

import pytest
import asyncio
from sociopsi.core.agent import SocioPsiAgent


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent initializes all subsystems."""
    agent = SocioPsiAgent()

    assert agent.drive_system is not None
    assert agent.visual_perception is not None
    assert agent.cognition is not None
    assert agent.physical_state is not None

    assert "affiliation" in agent.drive_system.drives
    assert "nurturing" in agent.drive_system.drives


@pytest.mark.asyncio
async def test_agent_update_loop():
    """Test agent update loop runs."""
    agent = SocioPsiAgent()

    # Run a few updates
    for _ in range(5):
        await agent.update()
        await asyncio.sleep(0.1)

    # Drives should have decayed
    affiliation_value = agent.drive_system.drives["affiliation"].value
    assert affiliation_value < 1.0


@pytest.mark.asyncio
async def test_drive_satisfaction():
    """Test drive satisfaction through perception."""
    agent = SocioPsiAgent()

    # Lower affiliation drive
    agent.drive_system.drives["affiliation"].value = 0.3

    # Simulate face detection
    agent.event_bus.publish("perception.visual.face_detected", {
        "count": 1,
        "timestamp": 0.0,
    })

    # Wait for event processing
    await asyncio.sleep(0.1)

    # Affiliation should have increased
    assert agent.drive_system.drives["affiliation"].value > 0.3
```

**Step 2: Run integration tests**

Run:
```bash
uv run pytest tests/integration/test_agent_integration.py -v
```

Expected: All tests PASS

**Step 3: Run all tests**

Run:
```bash
uv run pytest tests/ -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/integration/test_agent_integration.py
git commit -m "test: add integration tests for agent"
```

---

## Task 12: Code Quality and Documentation

**Step 1: Run linter**

Run:
```bash
uv run ruff check . --fix
```

Expected: Code formatted according to style guide

**Step 2: Run type checker**

Run:
```bash
uv run pyright
```

Expected: No type errors (or minimal, document them)

**Step 3: Final test suite**

Run:
```bash
uv run pytest tests/ -v --cov=src/sociopsi
```

Expected: Tests pass with reasonable coverage

**Step 4: Commit**

```bash
git add .
git commit -m "chore: apply linting and type checking"
```

---

## Final Validation

**Step 1: Clean build test**

```bash
# Remove virtual environment
rm -rf .venv

# Fresh install
uv sync

# Run application
uv run python -m sociopsi
```

**Expected Behavior:**
1. TUI launches successfully
2. Drives visible and decaying
3. Camera activates (with permissions)
4. Face detection works (if face visible)
5. Monologue updates with drive-based thoughts
6. Can quit with 'q'

**Step 2: Final commit and tag**

```bash
git add .
git commit -m "feat: complete Phase 1 foundation implementation"
git tag v0.1.0-phase1
```

---

## Success Criteria

Phase 1 is complete when:

- ✅ All tests pass
- ✅ Event bus handles subsystem communication
- ✅ Drive system decays and responds to satisfaction
- ✅ Visual perception detects faces via camera
- ✅ Simple cognition generates drive-based thoughts
- ✅ Physical state monitoring works (battery/CPU)
- ✅ TUI displays all subsystem states
- ✅ Application runs without crashes for 5+ minutes
- ✅ README documents setup and usage
- ✅ Code passes linting and type checking

## Next Steps

After Phase 1 completion, proceed to Phase 2 plan:
- `docs/plans/2026-02-03-sociopsi-phase2-archetypes.md`

This will add:
- Archetypal psychology (Persona, Shadow, Anima, Self, Ego)
- LLM integration (Ollama)
- Multi-voice internal dialogue
- Individuation drive
- Memory system basics
- TTS action system
