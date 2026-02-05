"""Configuration for the Jung agent."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentConfig:
    """Configuration for the agent loop."""

    # Model settings
    model: str = "jung-small"

    # Enabled modules
    modules: list[str] = field(
        default_factory=lambda: ["somatic", "archetypes", "imago", "individuation"]
    )

    # Heartbeat settings (seconds)
    heartbeat_idle: int = 8
    heartbeat_active: int = 5
    heartbeat_stressed: int = 3
    heartbeat_critical: int = 2
    heartbeat_dormant: int = 60

    # Thresholds
    battery_critical: int = 10
    cpu_stressed: int = 80
    cpu_active: int = 50
    thermal_hot: int = 80  # Celsius

    # Paths
    data_dir: Path = field(default_factory=lambda: Path.home() / ".jung")
    journal_file: Path = field(default_factory=lambda: Path.home() / ".jung" / "journal.jsonl")
    memory_file: Path = field(default_factory=lambda: Path.home() / ".jung" / "memory.json")

    # Logging
    log_stream: bool = True  # Print stream to console
    log_file: Path | None = None

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

    def __post_init__(self) -> None:
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
