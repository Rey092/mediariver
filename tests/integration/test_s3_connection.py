"""Integration tests for S3 connection via MinIO.

Requires MinIO running at MINIO_ENDPOINT with MINIO_ACCESS_KEY/MINIO_SECRET_KEY.
Run with: pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

import os

import pytest

from mediariver.config.schema import ConnectionConfig
from mediariver.connections.registry import build_connection, resolve_connection_uri

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
S3_TEST_BUCKET = os.environ.get("S3_TEST_BUCKET", "test-bucket")


def _ensure_bucket() -> None:
    """Create the test bucket if it doesn't exist."""
    from minio import Minio

    client = Minio(
        MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_ENDPOINT.startswith("https"),
    )
    if not client.bucket_exists(S3_TEST_BUCKET):
        client.make_bucket(S3_TEST_BUCKET)


@pytest.fixture(scope="module", autouse=True)
def setup_minio():
    """Ensure MinIO is reachable and test bucket exists."""
    try:
        _ensure_bucket()
    except Exception as e:
        pytest.skip(f"MinIO not available: {e}")


@pytest.fixture
def s3_fs():
    """Build an S3 FS connection to the test bucket."""
    config = ConnectionConfig(
        type="s3",
        bucket=S3_TEST_BUCKET,
        prefix="integration-test/",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )
    fs = build_connection("test-s3", config)
    yield fs
    # Cleanup: remove test files
    try:
        for path in fs.listdir("/"):
            if fs.isfile(path):
                fs.remove(path)
    except Exception:
        pass
    fs.close()


@pytest.fixture
def local_fs(tmp_path):
    """Build a local FS connection."""
    config = ConnectionConfig(type="local", root_path=str(tmp_path))
    fs = build_connection("test-local", config)
    yield fs, tmp_path
    fs.close()


@pytest.mark.integration
class TestS3Connection:
    def test_write_and_read(self, s3_fs):
        """Write a file to S3, read it back."""
        s3_fs.writetext("hello.txt", "hello from mediariver")
        content = s3_fs.readtext("hello.txt")
        assert content == "hello from mediariver"

    def test_listdir(self, s3_fs):
        """List files after writing."""
        s3_fs.writetext("file1.txt", "a")
        s3_fs.writetext("file2.txt", "b")
        entries = s3_fs.listdir("/")
        assert "file1.txt" in entries
        assert "file2.txt" in entries

    def test_remove(self, s3_fs):
        """Write then remove a file."""
        s3_fs.writetext("temp.txt", "temporary")
        assert s3_fs.exists("temp.txt")
        s3_fs.remove("temp.txt")
        assert not s3_fs.exists("temp.txt")

    def test_getinfo(self, s3_fs):
        """Get file info including size."""
        s3_fs.writetext("info_test.txt", "12345")
        info = s3_fs.getinfo("info_test.txt", namespaces=["details"])
        assert info.size == 5


@pytest.mark.integration
class TestCrossConnectionCopy:
    def test_local_to_s3(self, s3_fs, local_fs):
        """Copy a file from local FS to S3."""
        from fs.copy import copy_file

        fs_local, tmp_path = local_fs
        (tmp_path / "upload.txt").write_text("upload content")

        copy_file(fs_local, "upload.txt", s3_fs, "uploaded.txt")
        assert s3_fs.exists("uploaded.txt")
        assert s3_fs.readtext("uploaded.txt") == "upload content"

    def test_s3_to_local(self, s3_fs, local_fs):
        """Copy a file from S3 to local FS."""
        from fs.copy import copy_file

        fs_local, tmp_path = local_fs
        s3_fs.writetext("download.txt", "download content")

        copy_file(s3_fs, "download.txt", fs_local, "downloaded.txt")
        assert (tmp_path / "downloaded.txt").read_text() == "download content"

    def test_resolve_connection_uri(self, s3_fs, local_fs):
        """Test connection URI resolution with real connections."""
        fs_local, _ = local_fs
        connections = {"local": fs_local, "s3": s3_fs}

        fs, path = resolve_connection_uri("s3://test/file.txt", connections)
        assert fs is s3_fs
        assert path == "test/file.txt"

        fs, path = resolve_connection_uri("local://data.bin", connections)
        assert fs is fs_local
        assert path == "data.bin"
