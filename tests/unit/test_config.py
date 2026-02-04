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
