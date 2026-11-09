"""Load bronze files into the raw schema of the PostgreSQL warehouse.

The bronze object key tells everything we need:
    bronze/<source>/dt=YYYY-MM-DD/<file>

Idempotency: for each file we DELETE the rows of the same partition
(day, and series for BCB) and INSERT the new rows, in one database
transaction. Loading the same file twice gives the same result.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from src.config import WarehouseConfig

logger = logging.getLogger(__name__)

RAW_SCHEMA = "raw"
DDL_FILE = Path(__file__).parent / "sql" / "raw_tables.sql"

BRONZE_KEY_PATTERN = re.compile(
    r"^bronze/(?P<source>[a-z0-9_]+)/dt=(?P<dt>\d{4}-\d{2}-\d{2})/(?P<file>[A-Za-z0-9_.-]+)$"
)
SCHEMA_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")

# Data columns of each raw table. The loader also fills dt and source_file;
# loaded_at has a database default.
TABLE_COLUMNS: dict[str, list[str]] = {
    "bcb_sgs": ["series_name", "reference_date", "value"],
    "transactions": [
        "transaction_id",
        "customer_cpf",
        "transaction_at",
        "payment_type",
        "channel",
        "amount",
        "fee",
        "status",
    ],
    "customers": ["cpf", "name", "email", "state", "city", "created_at", "segment"],
}


class RowCountMismatchError(Exception):
    """The number of rows in raw is different from the bronze file."""


@dataclass(frozen=True)
class BronzeFile:
    """Parts of a bronze object key."""

    key: str
    source: str
    dt: date
    file_name: str

    @property
    def table(self) -> str:
        """Each bronze source has a raw table with the same name."""
        return self.source

    @property
    def partition(self) -> dict[str, object]:
        """Columns that identify the rows of this file in the raw table."""
        if self.source == "bcb_sgs":
            return {"dt": self.dt, "series_name": self.file_name.removesuffix(".json")}
        return {"dt": self.dt}


def parse_bronze_key(key: str) -> BronzeFile:
    """Split a bronze key into source, day and file name."""
    match = BRONZE_KEY_PATTERN.match(key)
    if not match:
        raise ValueError(f"Not a valid bronze key: {key!r}")
    source = match["source"]
    if source not in TABLE_COLUMNS:
        raise ValueError(f"Unknown source {source!r}. Options: {sorted(TABLE_COLUMNS)}")
    return BronzeFile(
        key=key,
        source=source,
        dt=date.fromisoformat(match["dt"]),
        file_name=match["file"],
    )


def _to_text(value: object) -> str | None:
    return None if value is None else str(value)


def to_raw_rows(bronze_file: BronzeFile, payload: list[dict]) -> list[tuple]:
    """Convert bronze JSON rows into tuples in the raw table column order.

    Values become text and None stays NULL. BCB fields get English names:
    "data" -> reference_date, "valor" -> value. The values do not change.
    """
    if bronze_file.source == "bcb_sgs":
        series_name = bronze_file.partition["series_name"]
        return [(series_name, _to_text(r["data"]), _to_text(r["valor"])) for r in payload]

    columns = TABLE_COLUMNS[bronze_file.source]
    return [tuple(_to_text(r.get(c)) for c in columns) for r in payload]


def get_connection(config: WarehouseConfig | None = None):
    """Open a connection to the warehouse."""
    config = config or WarehouseConfig.from_env()
    return psycopg2.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        dbname=config.dbname,
    )


def _check_schema_name(schema: str) -> None:
    # The schema name goes into the DDL text, so only allow simple names.
    if not SCHEMA_NAME_PATTERN.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")


def ensure_raw_tables(conn, schema: str = RAW_SCHEMA) -> None:
    """Create the raw schema and tables if they do not exist."""
    _check_schema_name(schema)
    ddl = DDL_FILE.read_text(encoding="utf-8").replace("{schema}", schema)
    with conn, conn.cursor() as cur:
        cur.execute(ddl)


def _where(partition: dict[str, object]) -> tuple[sql.Composable, list]:
    conditions = [sql.SQL("{} = %s").format(sql.Identifier(col)) for col in partition]
    return sql.SQL(" AND ").join(conditions), list(partition.values())


def load_rows(
    conn,
    bronze_file: BronzeFile,
    rows: list[tuple],
    schema: str = RAW_SCHEMA,
) -> int:
    """Replace the partition of `bronze_file` in raw with `rows`.

    DELETE and INSERT run in one transaction: if anything fails, nothing changes.
    Returns the number of inserted rows.
    """
    table = sql.Identifier(schema, bronze_file.table)
    columns = TABLE_COLUMNS[bronze_file.table] + ["dt", "source_file"]
    where, params = _where(bronze_file.partition)
    values = [(*row, bronze_file.dt, bronze_file.key) for row in rows]

    with conn, conn.cursor() as cur:
        cur.execute(sql.SQL("DELETE FROM {} WHERE {}").format(table, where), params)
        deleted = cur.rowcount
        if values:
            insert = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
                table, sql.SQL(", ").join(map(sql.Identifier, columns))
            )
            execute_values(cur, insert.as_string(cur), values, page_size=1000)

    logger.info(
        "%s.%s %s: deleted %d rows, inserted %d rows",
        schema,
        bronze_file.table,
        bronze_file.partition,
        deleted,
        len(values),
    )
    return len(values)


def count_rows(conn, bronze_file: BronzeFile, schema: str = RAW_SCHEMA) -> int:
    """Count the rows of the partition of `bronze_file` in raw."""
    table = sql.Identifier(schema, bronze_file.table)
    where, params = _where(bronze_file.partition)
    with conn, conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT count(*) FROM {} WHERE {}").format(table, where), params)
        return cur.fetchone()[0]


def check_row_count(expected: int, actual: int, label: str) -> None:
    """Raise if bronze and raw have a different number of rows."""
    if expected != actual:
        raise RowCountMismatchError(f"{label}: bronze has {expected} rows, raw has {actual}")
    logger.info("%s: row count OK (%d)", label, actual)
