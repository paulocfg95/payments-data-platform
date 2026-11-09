"""Jobs: load one bronze file into raw, and check the row counts."""

from __future__ import annotations

from src.load.bronze import read_json
from src.load.raw import (
    RAW_SCHEMA,
    check_row_count,
    count_rows,
    load_rows,
    parse_bronze_key,
    to_raw_rows,
)


def load_bronze_file(s3_client, bucket: str, key: str, conn, schema: str = RAW_SCHEMA) -> int:
    """Read a bronze file and replace its partition in raw. Returns the row count.

    The raw tables must exist (see src.load.raw.ensure_raw_tables). In the DAGs
    this runs once, before the parallel loads.
    """
    bronze_file = parse_bronze_key(key)
    payload = read_json(s3_client, bucket, key)
    return load_rows(conn, bronze_file, to_raw_rows(bronze_file, payload), schema)


def check_bronze_vs_raw(s3_client, bucket: str, key: str, conn, schema: str = RAW_SCHEMA) -> int:
    """Compare the row count of a bronze file and of raw. Raises on mismatch."""
    bronze_file = parse_bronze_key(key)
    expected = len(read_json(s3_client, bucket, key))
    actual = count_rows(conn, bronze_file, schema)
    check_row_count(expected, actual, label=key)
    return actual
