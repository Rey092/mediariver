"""Local filesystem connection builder."""

from __future__ import annotations

from pathlib import Path

from fs.osfs import OSFS

from mediariver.config.schema import ConnectionConfig


def build_local_fs(name: str, config: ConnectionConfig) -> OSFS:
    root_path = getattr(config, "root_path", "/")
    Path(root_path).mkdir(parents=True, exist_ok=True)
    return OSFS(root_path)
