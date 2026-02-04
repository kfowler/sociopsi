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
