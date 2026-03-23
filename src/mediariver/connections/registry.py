"""Connection type → filesystem builder registry."""

from __future__ import annotations

from typing import Any

from fs.base import FS

from mediariver.config.schema import ConnectionConfig
from mediariver.connections.local import build_local_fs
from mediariver.connections.s3 import build_s3_fs

_builders: dict[str, Any] = {
    "local": build_local_fs,
    "s3": build_s3_fs,
}


def build_connection(name: str, config: ConnectionConfig) -> FS:
    if config.type not in _builders:
        raise KeyError(f"Unknown connection type: '{config.type}'. Available: {list(_builders.keys())}")
    return _builders[config.type](name, config)


def resolve_connection_uri(
    uri: str,
    connections: dict[str, FS],
    default_connection: str = "local",
) -> tuple[FS, str]:
    """Parse connection://path URI and return (FS, relative_path)."""
    if "://" in uri:
        conn_name, path = uri.split("://", 1)
        if conn_name not in connections:
            raise KeyError(f"Connection '{conn_name}' not found in workflow connections")
        return connections[conn_name], path
    return connections[default_connection], uri
