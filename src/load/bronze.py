"""Write raw data to the bronze layer (MinIO locally, Amazon S3 in the cloud).

Bronze keys follow this pattern:
    bronze/<source>/dt=YYYY-MM-DD/<file>

Writing the same key again replaces the file. This makes a re-run of
the same day idempotent: no duplicates, just the latest copy.
"""

from __future__ import annotations

import json
import logging
from datetime import date

import boto3

from src.config import StorageConfig

logger = logging.getLogger(__name__)


def build_bronze_key(source: str, partition_date: date, file_name: str) -> str:
    """Return the object key for one file in a daily bronze partition."""
    return f"bronze/{source}/dt={partition_date.isoformat()}/{file_name}"


def get_s3_client(config: StorageConfig | None = None):
    """Create a boto3 S3 client. Uses MinIO when an endpoint URL is set."""
    config = config or StorageConfig.from_env()
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        region_name=config.region,
    )


def write_json(client, bucket: str, key: str, payload: object) -> None:
    """Write a JSON payload to the bucket, replacing any existing object."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    logger.info("Wrote s3://%s/%s (%d bytes)", bucket, key, len(body))


def read_json(client, bucket: str, key: str) -> object:
    """Read a JSON object from the bucket."""
    response = client.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read())
