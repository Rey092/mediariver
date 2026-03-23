"""S3 filesystem connection builder."""

from __future__ import annotations

from fs_s3fs import S3FS

from mediariver.config.schema import ConnectionConfig


def build_s3_fs(name: str, config: ConnectionConfig) -> S3FS:
    bucket = getattr(config, "bucket", "")
    prefix = getattr(config, "prefix", "")
    endpoint_url = getattr(config, "endpoint_url", None)
    access_key = getattr(config, "aws_access_key_id", None)
    secret_key = getattr(config, "aws_secret_access_key", None)
    region = getattr(config, "region", None)

    return S3FS(
        bucket_name=bucket,
        dir_path=prefix,
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region=region,
    )
