"""Tests for agent configuration."""

from pathlib import Path

import pytest

import logging
import logging.handlers

from jung_agent.config import (
    AgentConfig,
    _apply_config_overrides,
    _load_config_file,
    load_system_prompt,
    setup_logging,
)


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that default configuration values are set correctly."""
        config = AgentConfig()

        assert config.model == "jung-mid"
        assert config.heartbeat_idle == 2.0
        assert config.heartbeat_active == 1.0
        assert config.heartbeat_stressed == 0.5
        assert config.heartbeat_critical == 0.25
        assert config.heartbeat_dormant == 30.0
        assert config.battery_critical == 10
        assert config.cpu_stressed == 80
        assert config.cpu_active == 50
        assert config.thermal_hot == 80
        assert config.voice_enabled is True
        assert config.voice_rate == 250
        assert config.log_stream is True

    def test_custom_values(self) -> None:
        """Test that custom configuration values are respected."""
        config = AgentConfig(
            model="jung-small",
            heartbeat_idle=10,
            voice_enabled=False,
            battery_critical=15,
        )

        assert config.model == "jung-small"
        assert config.heartbeat_idle == 10
        assert config.voice_enabled is False
        assert config.battery_critical == 15

    def test_data_directory_created(self, tmp_path: Path) -> None:
        """Test that data directory is created on init."""
        data_dir = tmp_path / "test_jung_data"
        config = AgentConfig(data_dir=data_dir, voice_enabled=False)

        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_default_paths(self) -> None:
        """Test that default paths are set correctly."""
        config = AgentConfig(voice_enabled=False)

        assert config.data_dir == Path.home() / ".jung"
        assert config.journal_file == Path.home() / ".jung" / "journal.jsonl"
        assert config.memory_file == Path.home() / ".jung" / "memory.json"
        assert config.world_file == Path.home() / ".jung" / "world.json"

    def test_modules_default(self) -> None:
        """Test that all modules are enabled by default."""
        config = AgentConfig(voice_enabled=False)

        expected_modules = ["somatic", "archetypes", "imago", "individuation"]
        assert config.modules == expected_modules


class TestLoadSystemPrompt:
    """Tests for system prompt loading."""

    def test_returns_fallback_when_no_modelfile(self, tmp_path: Path) -> None:
        """Test that fallback prompt is returned when no modelfile exists."""
        # Change to temp directory with no modelfiles
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            prompt = load_system_prompt("nonexistent-model")

            assert "JSON" in prompt
            assert "stream" in prompt
        finally:
            os.chdir(old_cwd)

    def test_loads_from_modelfile(self, tmp_path: Path) -> None:
        """Test loading system prompt from a modelfile."""
        import os

        # Create a test modelfile
        modelfile_content = '''FROM phi4
SYSTEM """This is a test system prompt."""
'''
        modelfile = tmp_path / "test-model.modelfile"
        modelfile.write_text(modelfile_content)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            prompt = load_system_prompt("test-model")

            assert prompt == "This is a test system prompt."
        finally:
            os.chdir(old_cwd)


class TestLoadConfigFile:
    """Tests for config file loading."""

    def test_returns_empty_dict_when_file_not_exists(self, tmp_path: Path) -> None:
        """Test that missing config file returns empty dict."""
        result = _load_config_file(tmp_path / "nonexistent.json")
        assert result == {}

    def test_loads_valid_json_config(self, tmp_path: Path) -> None:
        """Test loading a valid JSON config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"model": "jung-small", "heartbeat_idle": 10}')

        result = _load_config_file(config_file)

        assert result == {"model": "jung-small", "heartbeat_idle": 10}

    def test_returns_empty_dict_for_invalid_json(self, tmp_path: Path) -> None:
        """Test that invalid JSON returns empty dict."""
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {")

        result = _load_config_file(config_file)

        assert result == {}

    def test_returns_empty_dict_for_non_object_json(self, tmp_path: Path) -> None:
        """Test that non-object JSON (like array) returns empty dict."""
        config_file = tmp_path / "config.json"
        config_file.write_text('["array", "not", "object"]')

        result = _load_config_file(config_file)

        assert result == {}


class TestApplyConfigOverrides:
    """Tests for applying config overrides."""

    def test_applies_string_override(self) -> None:
        """Test applying a string config override."""
        config = AgentConfig(voice_enabled=False)
        _apply_config_overrides(config, {"model": "jung-small"})

        assert config.model == "jung-small"

    def test_applies_int_override(self) -> None:
        """Test applying an integer config override."""
        config = AgentConfig(voice_enabled=False)
        _apply_config_overrides(config, {"heartbeat_idle": 15})

        assert config.heartbeat_idle == 15

    def test_applies_bool_override(self) -> None:
        """Test applying a boolean config override."""
        config = AgentConfig(voice_enabled=False)
        _apply_config_overrides(config, {"log_stream": False})

        assert config.log_stream is False

    def test_applies_path_override_from_string(self, tmp_path: Path) -> None:
        """Test applying a path config override from string."""
        config = AgentConfig(voice_enabled=False)
        path_str = str(tmp_path / "custom_data")
        _apply_config_overrides(config, {"data_dir": path_str})

        assert config.data_dir == Path(path_str)

    def test_applies_list_override(self) -> None:
        """Test applying a list config override."""
        config = AgentConfig(voice_enabled=False)
        _apply_config_overrides(config, {"modules": ["somatic", "archetypes"]})

        assert config.modules == ["somatic", "archetypes"]

    def test_ignores_unknown_keys(self) -> None:
        """Test that unknown config keys are ignored."""
        config = AgentConfig(voice_enabled=False)
        original_model = config.model
        _apply_config_overrides(config, {"unknown_key": "value", "model": "jung"})

        # Model should be updated, unknown key should be ignored
        assert config.model == "jung"

    def test_rejects_wrong_type_for_int(self) -> None:
        """Test that wrong type for int field is rejected."""
        config = AgentConfig(voice_enabled=False)
        original_value = config.battery_critical
        _apply_config_overrides(config, {"battery_critical": "not an int"})

        assert config.battery_critical == original_value

    def test_rejects_wrong_type_for_float(self) -> None:
        """Test that wrong type for float field is rejected."""
        config = AgentConfig(voice_enabled=False)
        original_value = config.heartbeat_idle
        _apply_config_overrides(config, {"heartbeat_idle": "not a float"})

        assert config.heartbeat_idle == original_value

    def test_rejects_wrong_type_for_bool(self) -> None:
        """Test that wrong type for bool field is rejected."""
        config = AgentConfig(voice_enabled=False)
        original_value = config.log_stream
        _apply_config_overrides(config, {"log_stream": "not a bool"})

        assert config.log_stream == original_value

    def test_rejects_bool_for_int_field(self) -> None:
        """Test that boolean is rejected for int field (since bool is subclass of int)."""
        config = AgentConfig(voice_enabled=False)
        original_value = config.battery_critical
        _apply_config_overrides(config, {"battery_critical": True})

        assert config.battery_critical == original_value

    def test_rejects_bool_for_float_field(self) -> None:
        """Test that boolean is rejected for float field."""
        config = AgentConfig(voice_enabled=False)
        original_value = config.heartbeat_idle
        _apply_config_overrides(config, {"heartbeat_idle": True})

        assert config.heartbeat_idle == original_value


class TestSetupLogging:
    """Tests for logging configuration."""

    def test_sets_log_level_to_debug(self) -> None:
        """Test that DEBUG log level is applied."""
        config = AgentConfig(voice_enabled=False, log_level="DEBUG")
        setup_logging(config)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_sets_log_level_to_warning(self) -> None:
        """Test that WARNING log level is applied."""
        config = AgentConfig(voice_enabled=False, log_level="WARNING")
        setup_logging(config)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_defaults_to_info_for_invalid_level(self) -> None:
        """Test that invalid log level falls back to INFO."""
        config = AgentConfig(voice_enabled=False, log_level="INVALID")
        setup_logging(config)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_adds_console_handler(self) -> None:
        """Test that console handler is added."""
        config = AgentConfig(voice_enabled=False)
        setup_logging(config)

        root_logger = logging.getLogger()
        stream_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) >= 1

    def test_adds_file_handler_when_log_file_specified(self, tmp_path: Path) -> None:
        """Test that file handler is added when log_file is specified."""
        log_file = tmp_path / "test.log"
        config = AgentConfig(voice_enabled=False, log_file=log_file)
        setup_logging(config)

        root_logger = logging.getLogger()
        file_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) >= 1

        # Clean up
        for h in file_handlers:
            h.close()
            root_logger.removeHandler(h)
