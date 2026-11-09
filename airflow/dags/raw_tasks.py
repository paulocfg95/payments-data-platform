"""Airflow tasks shared by the DAGs that load bronze files into raw.

Each task is a thin wrapper: the logic lives in src/load and is unit tested.
"""

from __future__ import annotations

from airflow.sdk import task


@task
def create_raw_tables() -> None:
    """Create the raw schema and tables once, before the parallel loads."""
    from src.load.raw import ensure_raw_tables, get_connection

    conn = get_connection()
    try:
        ensure_raw_tables(conn)
    finally:
        conn.close()


@task
def load_raw(key: str) -> str:
    """Replace the raw partition of one bronze file. Returns the same key."""
    from src.config import StorageConfig
    from src.load.bronze import get_s3_client
    from src.load.bronze_to_raw import load_bronze_file
    from src.load.raw import get_connection

    config = StorageConfig.from_env()
    conn = get_connection()
    try:
        load_bronze_file(get_s3_client(config), config.bucket, key, conn)
    finally:
        conn.close()
    return key


@task
def check_counts(key: str) -> int:
    """Fail if the raw partition and the bronze file have different row counts."""
    from src.config import StorageConfig
    from src.load.bronze import get_s3_client
    from src.load.bronze_to_raw import check_bronze_vs_raw
    from src.load.raw import get_connection

    config = StorageConfig.from_env()
    conn = get_connection()
    try:
        return check_bronze_vs_raw(get_s3_client(config), config.bucket, key, conn)
    finally:
        conn.close()
