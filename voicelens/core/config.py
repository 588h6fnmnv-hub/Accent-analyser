"""VoiceLens Configuration management."""

import json
from pathlib import Path
from typing import Any, Optional


class Config:
    """Manages VoiceLens configuration."""

    DEFAULT_CONFIG = {
        "model": "base",
        "language": "en",
        "sample_rate": 16000,
        "auto_save": True,
        "theme": "default",
    }

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path.home() / ".config" / "voicelens" / "config.json"

        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load()

    def _load(self) -> dict:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    return {**self.DEFAULT_CONFIG, **json.load(f)}
            except Exception:
                pass
        return self.DEFAULT_CONFIG.copy()

    def save(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._config[key] = value
        self.save()

    def update(self, values: dict) -> None:
        """Update multiple configuration values."""
        self._config.update(values)
        self.save()

    def reset(self) -> None:
        """Reset to defaults."""
        self._config = self.DEFAULT_CONFIG.copy()
        self.save()

    @property
    def all(self) -> dict:
        """Get all configuration."""
        return self._config.copy()