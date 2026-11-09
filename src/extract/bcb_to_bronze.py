"""Job: fetch one BCB SGS series for one day and save it to bronze."""

from __future__ import annotations

import logging
from datetime import date

from src.extract.bcb_client import SERIES, BCBClient
from src.load.bronze import build_bronze_key, write_json

logger = logging.getLogger(__name__)

SOURCE_NAME = "bcb_sgs"


def ingest_series_day(
    series_name: str,
    day: date,
    bcb_client: BCBClient,
    s3_client,
    bucket: str,
) -> str:
    """Fetch `series_name` for `day` and write the raw rows to bronze.

    The file is always written, even when the API has no data for the day
    (an empty list). This way a re-run replaces the file and we can see
    that the day was processed.

    Returns the object key that was written.
    """
    if series_name not in SERIES:
        raise ValueError(f"Unknown series {series_name!r}. Options: {sorted(SERIES)}")

    rows = bcb_client.fetch_series(SERIES[series_name], start=day, end=day)
    key = build_bronze_key(SOURCE_NAME, day, f"{series_name}.json")
    write_json(s3_client, bucket, key, rows)
    logger.info("Series %s on %s: %d rows saved to %s", series_name, day, len(rows), key)
    return key
