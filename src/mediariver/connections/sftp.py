"""SFTP filesystem connection builder."""

from __future__ import annotations

from mediariver.config.schema import ConnectionConfig


def build_sftp_fs(name: str, config: ConnectionConfig):
    """Build an SFTP connection. Requires fs.sshfs package."""
    try:
        from fs.sshfs import SSHFS
    except ImportError:
        raise ImportError("SFTP support requires fs.sshfs: pip install 'mediariver[sftp]'")

    host = getattr(config, "host", "localhost")
    port = getattr(config, "port", 22)
    user = getattr(config, "user", "root")
    passwd = getattr(config, "passwd", None)
    return SSHFS(host=host, port=port, user=user, passwd=passwd)
