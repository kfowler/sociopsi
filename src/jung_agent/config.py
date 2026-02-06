"""Configuration for the Jung agent."""

import json
import logging
import logging.handlers
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Valid log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Type alias for module names
ModuleName = Literal["somatic", "archetypes", "imago", "individuation"]


def load_system_prompt(model: str) -> str:
    """Load system prompt from modelfile.

    Searches for the modelfile in these locations (in order):
    1. Current directory: {model}.modelfile
    2. Current directory: jung.modelfile
    3. Home directory: ~/.jung/{model}.modelfile

    Args:
        model: The model name to load the prompt for.

    Returns:
        The system prompt extracted from the SYSTEM block in the modelfile,
        or a minimal fallback prompt if no modelfile is found.
    """
    modelfile_paths = [
        Path.cwd() / f"{model}.modelfile",
        Path.cwd() / "jung.modelfile",
        Path.home() / ".jung" / f"{model}.modelfile",
    ]

    for path in modelfile_paths:
        if path.exists():
            content = path.read_text()
            # Extract SYSTEM block
            match = re.search(r'SYSTEM\s+"""(.*?)"""', content, re.DOTALL)
            if match:
                return match.group(1).strip()

    # Fallback minimal prompt
    return """You are a psyche. Respond ONLY with valid JSON:
{"stream":[{"component":"shadow|anima|persona|self","text":"..."}],"actions":[{"type":"action_name"}]}
No other text. Only JSON."""


def setup_logging(config: AgentConfig) -> None:
    """Configure logging based on agent config.

    Sets up logging to console and optionally to a rotating file.
    Should be called once at application startup after config is loaded.

    Args:
        config: The agent configuration with logging settings.
    """
    # Parse log level
    level_str = config.log_level.upper()
    level = LOG_LEVELS.get(level_str, logging.INFO)
    if level_str not in LOG_LEVELS:
        logger.warning(f"Unknown log level '{config.log_level}', using INFO")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Log format
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # File handler (optional, rotating)
    if config.log_file:
        try:
            # Ensure parent directory exists
            config.log_file.parent.mkdir(parents=True, exist_ok=True)

            # Use rotating file handler (10MB max, keep 5 backups)
            file_handler = logging.handlers.RotatingFileHandler(
                config.log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            logger.info(f"Logging to file: {config.log_file}")
        except OSError as e:
            logger.error(f"Failed to set up file logging to {config.log_file}: {e}")

    logger.debug(f"Logging configured at level {level_str}")


def _load_config_file(config_path: Path) -> dict[str, Any]:
    """Load configuration from a JSON file.

    Args:
        config_path: Path to the config.json file.

    Returns:
        Dictionary of configuration values, or empty dict if file doesn't exist
        or is invalid.
    """
    if not config_path.exists():
        return {}

    try:
        content = config_path.read_text()
        data = json.loads(content)
        if not isinstance(data, dict):
            logger.warning(f"Config file {config_path} is not a JSON object, ignoring")
            return {}
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in config file {config_path}: {e}")
        return {}
    except OSError as e:
        logger.warning(f"Error reading config file {config_path}: {e}")
        return {}


def _apply_config_overrides(config: AgentConfig, overrides: dict[str, Any]) -> None:
    """Apply configuration overrides from a config file.

    Args:
        config: The AgentConfig instance to modify.
        overrides: Dictionary of field names to values.
    """
    # Get valid field names
    valid_fields = {f.name: f for f in fields(config)}

    for key, value in overrides.items():
        if key not in valid_fields:
            logger.warning(f"Unknown config key '{key}', ignoring")
            continue

        field_info = valid_fields[key]
        field_type = field_info.type

        # Convert Path strings to Path objects
        if field_type == Path or field_type == "Path":
            if isinstance(value, str):
                value = Path(value).expanduser()
            elif not isinstance(value, Path):
                logger.warning(f"Config key '{key}' expects a path, got {type(value).__name__}")
                continue
        elif field_type == "Path | None":
            if value is not None:
                if isinstance(value, str):
                    value = Path(value).expanduser()
                elif not isinstance(value, Path):
                    logger.warning(
                        f"Config key '{key}' expects a path or null, got {type(value).__name__}"
                    )
                    continue

        # Type check for basic types
        if field_type is int or field_type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                logger.warning(f"Config key '{key}' expects int, got {type(value).__name__}")
                continue
        elif field_type is float or field_type == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                logger.warning(f"Config key '{key}' expects float, got {type(value).__name__}")
                continue
            value = float(value)  # Convert int to float
        elif field_type is bool or field_type == "bool":
            if not isinstance(value, bool):
                logger.warning(f"Config key '{key}' expects bool, got {type(value).__name__}")
                continue
        elif field_type is str or field_type == "str":
            if not isinstance(value, str):
                logger.warning(f"Config key '{key}' expects str, got {type(value).__name__}")
                continue
        elif field_type == "list[str]":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                logger.warning(f"Config key '{key}' expects list of strings")
                continue

        setattr(config, key, value)
        logger.debug(f"Applied config override: {key}={value}")


def _check_voice_available(voice_name: str) -> str:
    """Check if a voice is available and return fallback if not.

    Args:
        voice_name: The requested voice name (e.g., "Zoe (Premium)").

    Returns:
        The requested voice name if available, or the best available
        English voice as a fallback.
    """
    try:
        import AVFoundation  # type: ignore[import-untyped]

        voices = AVFoundation.AVSpeechSynthesisVoice.speechVoices()  # type: ignore[attr-defined]

        # Check if requested voice exists
        for v in voices:
            if v.name() == voice_name:
                return voice_name

        # Fallback: find best available English voice
        best_name = voice_name  # Keep original as default
        best_quality = -1

        for v in voices:
            if v.language().startswith("en") and v.quality() > best_quality:
                best_quality = v.quality()
                best_name = v.name()

        if best_name != voice_name:
            logger.warning(f"Voice '{voice_name}' not found, using '{best_name}'")

        return best_name
    except ImportError:
        return voice_name  # Can't check, keep original


@dataclass
class AgentConfig:
    """Configuration for the Jung agent.

    This dataclass holds all configuration options for the agent, including
    model settings, heartbeat timing, thresholds, file paths, and voice settings.

    Attributes:
        llm_provider: LLM backend for the psyche action-selection query.
            "ollama" uses the local Ollama model; "anthropic" uses the
            Anthropic API (requires ANTHROPIC_API_KEY env var).
            Archetype voices, ego, and creative actions always use Ollama.
            Default: "ollama".

        llm_anthropic_model: Anthropic model ID when llm_provider="anthropic".
            Default: "claude-haiku-4-5-20251001".

        model: Ollama model name. Used for archetype voices, ego mediation,
            creative actions, vision (llava), and psyche query when
            llm_provider="ollama". Default: "jung-mid".

        modules: List of enabled psyche modules. Valid values:
            "somatic", "archetypes", "imago", "individuation".
            Default: all modules enabled.

        heartbeat_idle: Seconds between cycles when idle. Range: 0.25-300.
            Default: 2.0.

        heartbeat_active: Seconds between cycles when CPU is active. Range: 0.25-60.
            Default: 1.0.

        heartbeat_stressed: Seconds between cycles when CPU is stressed. Range: 0.25-30.
            Default: 0.5.

        heartbeat_critical: Seconds between cycles in critical state. Range: 0.25-10.
            Default: 0.25.

        heartbeat_dormant: Seconds between cycles when lid is closed. Range: 1-600.
            Default: 30.

        battery_critical: Battery percentage threshold for critical mode. Range: 5-30.
            Default: 10.

        cpu_stressed: CPU percentage threshold for stressed mode. Range: 50-95.
            Default: 80.

        cpu_active: CPU percentage threshold for active mode. Range: 20-70.
            Default: 50.

        thermal_hot: Temperature in Celsius for thermal concern. Range: 60-100.
            Default: 80.

        data_dir: Base directory for agent data files.
            Default: ~/.jung/

        journal_file: Path to the journal JSONL file.
            Default: ~/.jung/journal.jsonl

        memory_file: Path to the memory JSON file.
            Default: ~/.jung/memory.json

        world_file: Path to the world model JSON file.
            Default: ~/.jung/world.json

        log_stream: Whether to print stream output to console.
            Default: True.

        log_file: Optional path to write logs. None disables file logging.
            Default: None.

        log_level: Logging level. Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL.
            Default: INFO.

        voice_enabled: Whether text-to-speech is enabled.
            Default: True.

        voice_rate: Speech rate in words per minute for stream. Range: 100-400.
            Default: 250.

        voice_anima: macOS voice name for anima component (soul-bridge, feeling).
            Default: "Zoe (Premium)".

        voice_shadow: macOS voice name for shadow component (repressed, denied).
            Default: "Serena (Premium)".

        voice_persona: macOS voice name for persona component (social mask).
            Default: "Matilda (Premium)".

        voice_self: macOS voice name for self component (numinous totality).
            Default: "Ava (Premium)".

        voice_default: macOS voice name when components blend.
            Default: "Zoe (Premium)".

        voice_actions: macOS voice name for action announcements.
            Default: "Evan (Enhanced)".

        voice_actions_rate: Speech rate for action announcements. Range: 100-300.
            Default: 190.

        ear_enabled: Whether continuous speech recognition is enabled.
            Default: True.

        ear_locale: Locale for speech recognition (BCP-47).
            Default: "en-US".

        ear_on_device: Force on-device recognition (no network).
            Default: True.
    """

    # LLM provider for psyche query: "ollama" or "anthropic" (requires ANTHROPIC_API_KEY)
    llm_provider: str = "ollama"
    llm_anthropic_model: str = "claude-haiku-4-5-20251001"
    llm_log_prompts: bool = False

    # Ollama model name (used when llm_provider="ollama", and always for vision/llava)
    model: str = "jung-mid"

    # Enabled modules
    modules: list[str] = field(
        default_factory=lambda: ["somatic", "archetypes", "imago", "individuation"]
    )

    # Heartbeat settings (seconds)
    heartbeat_idle: float = 2.0
    heartbeat_active: float = 1.0
    heartbeat_stressed: float = 0.5
    heartbeat_critical: float = 0.25
    heartbeat_dormant: float = 30.0

    # Thresholds
    battery_critical: int = 10
    cpu_stressed: int = 80
    cpu_active: int = 50
    thermal_hot: int = 80  # Celsius

    # Paths
    data_dir: Path = field(default_factory=lambda: Path.home() / ".jung")
    journal_file: Path = field(default_factory=lambda: Path.home() / ".jung" / "journal.jsonl")
    memory_file: Path = field(default_factory=lambda: Path.home() / ".jung" / "memory.json")
    world_file: Path = field(default_factory=lambda: Path.home() / ".jung" / "world.json")

    # Logging
    log_stream: bool = True  # Print stream to console
    log_file: Path | None = None
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Voice settings
    voice_enabled: bool = True
    voice_rate: int = 250  # Speech rate for stream (words per minute)

    # Voice per psyche component
    voice_anima: str = "Zoe (Premium)"  # Soul-bridge, feeling, intuition
    voice_shadow: str = "Serena (Premium)"  # Repressed, denied, dangerous
    voice_persona: str = "Matilda (Premium)"  # Social mask
    voice_self: str = "Ava (Premium)"  # Numinous totality (rare)
    voice_default: str = "Zoe (Premium)"  # When components blend

    # Intentions/actions voice
    voice_actions: str = "Evan (Enhanced)"
    voice_actions_rate: int = 190  # Slower, deliberate announcements

    # Ear (continuous speech recognition)
    ear_enabled: bool = True
    ear_locale: str = "en-US"
    ear_on_device: bool = True

    def __post_init__(self) -> None:
        """Initialize config: load config file, create data directory, validate voices."""
        # Load config file from ~/.jung/config.json
        config_file = Path.home() / ".jung" / "config.json"
        overrides = _load_config_file(config_file)
        if overrides:
            logger.info(f"Loaded config from {config_file}")
            _apply_config_overrides(self, overrides)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Validate voice availability if voice is enabled
        if self.voice_enabled:
            self.voice_anima = _check_voice_available(self.voice_anima)
            self.voice_shadow = _check_voice_available(self.voice_shadow)
            self.voice_persona = _check_voice_available(self.voice_persona)
            self.voice_self = _check_voice_available(self.voice_self)
            self.voice_default = _check_voice_available(self.voice_default)
            self.voice_actions = _check_voice_available(self.voice_actions)
