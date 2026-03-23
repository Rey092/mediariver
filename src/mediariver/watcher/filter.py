"""File extension and glob filtering."""

from __future__ import annotations

from pathlib import PurePosixPath


def matches_extensions(filename: str, extensions: list[str]) -> bool:
    if not extensions:
        return False
    suffix = PurePosixPath(filename).suffix.lower()
    return suffix in [ext.lower() for ext in extensions]
