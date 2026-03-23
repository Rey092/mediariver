"""Tests for connection registry and builders."""

import pytest
from fs.memoryfs import MemoryFS

from mediariver.config.schema import ConnectionConfig
from mediariver.connections.registry import build_connection, resolve_connection_uri


class TestBuildConnection:
    def test_build_local(self, tmp_path):
        config = ConnectionConfig(type="local", root_path=str(tmp_path))
        fs = build_connection("local_conn", config)
        assert hasattr(fs, "listdir")
        assert hasattr(fs, "open")
        fs.close()

    def test_build_unknown_type(self):
        config = ConnectionConfig(type="unknown_backend")
        with pytest.raises(KeyError, match="unknown_backend"):
            build_connection("bad", config)

    def test_local_creates_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "sub" / "dir"
        config = ConnectionConfig(type="local", root_path=str(new_dir))
        fs = build_connection("test", config)
        assert new_dir.exists()
        fs.close()


class TestResolveConnectionUri:
    def test_connection_prefix(self):
        connections = {"output": MemoryFS(), "local": MemoryFS()}
        fs, path = resolve_connection_uri("output://videos/file.mp4", connections)
        assert fs is connections["output"]
        assert path == "videos/file.mp4"

    def test_bare_path_uses_default(self):
        connections = {"local": MemoryFS()}
        fs, path = resolve_connection_uri("/tmp/file.mp4", connections)
        assert fs is connections["local"]
        assert path == "/tmp/file.mp4"

    def test_unknown_connection_raises(self):
        connections = {"local": MemoryFS()}
        with pytest.raises(KeyError, match="nonexistent"):
            resolve_connection_uri("nonexistent://file.mp4", connections)


class TestFtpConnection:
    def test_build_ftp_registered(self):
        """FTP type is recognized by the registry."""
        # We can't actually connect, but verify the type is registered
        from mediariver.connections.registry import _builders

        assert "ftp" in _builders


class TestSftpConnection:
    def test_build_sftp_registered(self):
        """SFTP type is recognized by the registry."""
        from mediariver.connections.registry import _builders

        assert "sftp" in _builders
