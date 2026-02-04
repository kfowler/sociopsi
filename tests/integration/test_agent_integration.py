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
