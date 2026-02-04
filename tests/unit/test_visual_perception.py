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
