"""Polling-based directory watcher."""

from __future__ import annotations

import re
from collections.abc import Callable

import blake3 as b3
import structlog
from fs.base import FS

from mediariver.config.schema import WatchConfig
from mediariver.watcher.filter import matches_extensions

log = structlog.get_logger()


def parse_interval(interval: str) -> float:
    """Parse a duration string (e.g., '30s', '5m') to seconds."""
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(s|m|h)?$", interval.strip())
    if not match:
        raise ValueError(f"Invalid interval: {interval}")
    value = float(match.group(1))
    unit = match.group(2) or "s"
    multipliers = {"s": 1, "m": 60, "h": 3600}
    return value * multipliers[unit]


def compute_file_hash(fs: FS, path: str) -> str:
    """Compute blake3 hash of a file on any filesystem."""
    hasher = b3.blake3()
    with fs.open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def poll_once(
    fs: FS,
    watch_config: WatchConfig,
    is_known: Callable[[str, str], bool],
    on_new_file: Callable[[str, str, int], None],
) -> int:
    """Poll a directory once and process new files."""
    new_count = 0
    try:
        entries = fs.listdir(watch_config.path)
    except Exception as e:
        log.error("poll_listdir_failed", path=watch_config.path, error=str(e))
        return 0

    for entry in entries:
        if not matches_extensions(entry, watch_config.extensions):
            continue

        full_path = f"{watch_config.path.rstrip('/')}/{entry}"

        if is_known(watch_config.connection, full_path):
            continue

        try:
            file_hash = compute_file_hash(fs, full_path)
            info = fs.getinfo(full_path, namespaces=["details"])
            file_size = info.size or 0
            on_new_file(full_path, file_hash, file_size)
            new_count += 1
        except Exception as e:
            log.error("poll_file_error", path=full_path, error=str(e))

    return new_count
