"""Project settings read from environment variables.

Secrets are never hard-coded. AWS credentials are read by boto3 from the
standard variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class StorageConfig:
    """Where the bronze layer lives."""

    bucket: str
    endpoint_url: str | None  # MinIO URL locally; None means real AWS S3
    region: str

    @classmethod
    def from_env(cls) -> StorageConfig:
        return cls(
            bucket=os.environ.get("BRONZE_BUCKET", "datalake"),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
            region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
