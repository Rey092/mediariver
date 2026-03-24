"""Desktop app configuration — reads/writes ~/.mediariver/config.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_CONFIG_DIR = Path.home() / ".mediariver"
DEFAULT_CONFIG_PATH = _CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    workflows_dir: str = "./workflows"
    database_url: str | None = None
    log_level: str = "info"
    port: int = 9876
    env: dict[str, str] = field(default_factory=dict)
    first_run: bool = True


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Load config from JSON file, returning defaults if missing."""
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text())
        return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save config to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2))
