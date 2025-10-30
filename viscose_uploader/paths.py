from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Holds the file-system locations used by the uploader."""

    base_dir: Path

    @property
    def config_file(self) -> Path:
        return self.base_dir / "config.json"

    @property
    def state_file(self) -> Path:
        return self.base_dir / "state.json"

    @property
    def token_file(self) -> Path:
        return self.base_dir / "google_token.json"

    def ensure(self) -> None:
        """Create the base directory if it does not exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default(cls) -> "AppPaths":
        home = Path.home()
        return cls(base_dir=home / ".viscose_uploader")
