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
    heartbeat_idle: int = 60
    heartbeat_active: int = 20
    heartbeat_stressed: int = 10
    heartbeat_critical: int = 5
    heartbeat_dormant: int = 180

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

    def __post_init__(self) -> None:
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
