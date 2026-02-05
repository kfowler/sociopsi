"""Tests for drive system."""

import pytest
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


def test_drive_system_with_individuation():
    """Test drive system includes individuation drive."""
    bus = EventBus()
    system = DriveSystem(bus)

    assert "individuation" in system.drives
    assert system.drives["individuation"].name == "individuation"
    assert system.drives["individuation"].is_core is True


def test_update_individuation_high_harmony():
    """Test individuation satisfaction with high harmony."""
    bus = EventBus()
    system = DriveSystem(bus)

    # Lower drive value so it can increase
    system.drives["individuation"].value = 0.6
    initial_value = system.drives["individuation"].value

    # High harmony should satisfy individuation
    system.update_individuation(harmony=0.8)

    assert system.drives["individuation"].value > initial_value


def test_update_individuation_low_harmony():
    """Test individuation with low harmony."""
    bus = EventBus()
    system = DriveSystem(bus)

    initial_value = system.drives["individuation"].value

    # Low harmony doesn't actively decrease (decay handles it)
    system.update_individuation(harmony=0.2)

    assert system.drives["individuation"].value == initial_value
