"""Load a small, fixed sample dataset into raw, without S3 and without the BCB API.

Used by CI (dbt build) and by the dbt docs workflow, where we want fast and
repeatable runs that do not depend on external services.

It uses the same code as the real pipeline: the synthetic generator, the raw
loader and the row count check. Only the bronze step (S3) is skipped; it has
its own tests with a fake S3.

Run it with:
    python -m src.load.sample_data
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from src.extract.bcb_to_bronze import SOURCE_NAME as BCB_SOURCE
from src.generate.customers import generate_customers
from src.generate.transactions import generate_transactions
from src.load.bronze import build_bronze_key
from src.load.raw import (
    RAW_SCHEMA,
    check_row_count,
    count_rows,
    ensure_raw_tables,
    get_connection,
    load_rows,
    parse_bronze_key,
    to_raw_rows,
)

logger = logging.getLogger(__name__)

BCB_SAMPLE_FILE = Path(__file__).parent / "sample" / "bcb_sample.json"


def _bcb_sample() -> dict[str, dict[str, list[dict]]]:
    data = json.loads(BCB_SAMPLE_FILE.read_text(encoding="utf-8"))
    return {day: series for day, series in data.items() if not day.startswith("_")}


def sample_days() -> list[date]:
    """The days in the sample (the days of the BCB sample file)."""
    return [date.fromisoformat(day) for day in sorted(_bcb_sample())]


def sample_files() -> list[tuple[str, list[dict]]]:
    """Return (bronze key, payload) pairs, as if they were read from bronze."""
    files = []
    customers = generate_customers()
    for day_text, series in sorted(_bcb_sample().items()):
        day = date.fromisoformat(day_text)
        for series_name, rows in sorted(series.items()):
            files.append((build_bronze_key(BCB_SOURCE, day, f"{series_name}.json"), rows))
        files.append((build_bronze_key("customers", day, "customers.json"), customers))
        files.append(
            (
                build_bronze_key("transactions", day, "transactions.json"),
                generate_transactions(day, customers),
            )
        )
    return files


def load_sample_data(conn, schema: str = RAW_SCHEMA) -> dict[str, int]:
    """Load the sample into raw and check the counts. Returns rows per table.

    Idempotent, like the real load: running it twice gives the same rows.
    """
    ensure_raw_tables(conn, schema)
    totals: dict[str, int] = {}
    for key, payload in sample_files():
        bronze_file = parse_bronze_key(key)
        loaded = load_rows(conn, bronze_file, to_raw_rows(bronze_file, payload), schema)
        check_row_count(len(payload), count_rows(conn, bronze_file, schema), label=key)
        totals[bronze_file.table] = totals.get(bronze_file.table, 0) + loaded
    return totals


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    conn = get_connection()
    try:
        totals = load_sample_data(conn)
    finally:
        conn.close()
    for table, rows in sorted(totals.items()):
        print(f"raw.{table}: {rows} rows")


if __name__ == "__main__":
    main()
