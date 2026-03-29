"""Polling-based directory watcher."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import NamedTuple

import blake3 as b3
import structlog
from fs.base import FS

from mediariver.config.schema import WatchConfig
from mediariver.watcher.filter import matches_extensions

log = structlog.get_logger()


class FileMeta(NamedTuple):
    """Lightweight file metadata for change detection (no download needed)."""

    size: int
    etag: str  # S3 ETag or local mtime as string


def parse_interval(interval: str) -> float:
    """Parse a duration string (e.g., '30s', '5m') to seconds."""
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(s|m|h)?$", interval.strip())
    if not match:
        raise ValueError(f"Invalid interval: {interval}")
    value = float(match.group(1))
    unit = match.group(2) or "s"
    multipliers = {"s": 1, "m": 60, "h": 3600}
    return value * multipliers[unit]


def _is_s3fs(fs: FS) -> bool:
    """Check if a filesystem is an S3FS instance."""
    return type(fs).__name__ == "S3FS"


def _s3_get_meta(fs: FS, path: str) -> FileMeta:
    """Get file size and ETag via boto3 HeadObject (no download)."""
    key = fs._path_to_key(path)
    obj = fs.s3.Object(fs._bucket_name, key)
    obj.load()
    return FileMeta(size=obj.content_length, etag=obj.e_tag or "")


def _local_get_meta(fs: FS, path: str) -> FileMeta:
    """Get file size and mtime from local filesystem."""
    info = fs.getinfo(path, namespaces=["details"])
    size = info.size or 0
    mtime = info.modified
    return FileMeta(size=size, etag=str(mtime.timestamp()) if mtime else "")


def get_file_meta(fs: FS, path: str) -> FileMeta:
    """Get lightweight metadata for change detection."""
    if _is_s3fs(fs):
        return _s3_get_meta(fs, path)
    return _local_get_meta(fs, path)


def _s3_read_file(fs: FS, path: str) -> bytes:
    """Read file content via boto3, bypassing fs-s3fs's broken open."""
    key = fs._path_to_key(path)
    obj = fs.s3.Object(fs._bucket_name, key)
    return obj.get()["Body"].read()


def compute_file_hash(fs: FS, path: str) -> str:
    """Compute blake3 hash of a file on any filesystem."""
    hasher = b3.blake3()
    if _is_s3fs(fs):
        data = _s3_read_file(fs, path)
        hasher.update(data)
    else:
        with fs.open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
    return hasher.hexdigest()


def _walk_s3_safe(fs: FS, path: str):
    """Recursively walk an S3 filesystem, tolerating virtual directories.

    fs-s3fs's built-in walk uses scandir -> getinfo which does HeadObject
    on each entry.  MinIO (and S3) return 404 for virtual "directories"
    that have no explicit object, causing ResourceNotFound.  This helper
    uses listdir to probe whether an entry is a directory (if listdir
    succeeds, it's a directory; otherwise it's a file).
    """
    try:
        entries = fs.listdir(path)
    except Exception as e:
        log.warning("walk_listdir_failed", path=path, error=str(e))
        return

    files: list[str] = []
    dirs: list[str] = []

    for name in entries:
        entry_path = f"{path.rstrip('/')}/{name}"
        try:
            fs.listdir(entry_path)
            dirs.append(name)
        except Exception:
            files.append(name)

    yield path, dirs, files

    for d in dirs:
        child = f"{path.rstrip('/')}/{d}"
        yield from _walk_s3_safe(fs, child)


def poll_once(
    fs: FS,
    watch_config: WatchConfig,
    is_known: Callable[[str, str, int, str], bool],
    on_new_file: Callable[[str, str, int, str], None],
) -> int:
    """Poll a directory once and process new/changed files.

    Walks subdirectories recursively so nested structures
    (e.g. S3 prefix ``manga/chapters/{id}/{ch}/001.png``) are discovered.

    Change detection uses lightweight metadata (size + ETag/mtime) to
    detect modified files without downloading them. BLAKE3 hash is only
    computed when a file is picked up for processing.
    """
    new_count = 0
    watch_path = watch_config.path.rstrip("/") or "/"
    use_s3_walk = _is_s3fs(fs)
    walker = _walk_s3_safe(fs, watch_path) if use_s3_walk else fs.walk.walk(watch_path)

    try:
        for dir_path, _dirs, files in walker:
            file_names = files if use_s3_walk else [f.name for f in files]
            for entry in file_names:
                if not matches_extensions(entry, watch_config.extensions):
                    continue

                full_path = f"{dir_path.rstrip('/')}/{entry}"

                try:
                    meta = get_file_meta(fs, full_path)
                except Exception as e:
                    log.warning("poll_meta_error", path=full_path, error=str(e))
                    continue

                if is_known(watch_config.connection, full_path, meta.size, meta.etag):
                    log.debug("poll_skip_known", entry=entry, path=full_path)
                    continue

                try:
                    file_hash = compute_file_hash(fs, full_path)
                    on_new_file(full_path, file_hash, meta.size, meta.etag)
                    new_count += 1
                except Exception as e:
                    log.error("poll_file_error", path=full_path, error=str(e))
    except Exception as e:
        log.error("poll_walk_failed", path=watch_path, error=str(e))
        return 0

    log.debug("poll_complete_walk", path=watch_path, new_files=new_count)
    return new_count
