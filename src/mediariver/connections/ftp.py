"""FTP filesystem connection builder."""

from __future__ import annotations

from fs.ftpfs import FTPFS

from mediariver.config.schema import ConnectionConfig


def build_ftp_fs(name: str, config: ConnectionConfig) -> FTPFS:
    host = getattr(config, "host", "localhost")
    port = getattr(config, "port", 21)
    user = getattr(config, "user", "anonymous")
    passwd = getattr(config, "passwd", "")
    return FTPFS(host=host, port=port, user=user, passwd=passwd)
