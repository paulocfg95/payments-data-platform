"""Tests for the bronze -> raw load.

Unit tests run anywhere. Tests marked `integration` need the warehouse
from docker compose; they use the schema raw_test and drop it at the end.
"""

from datetime import date

import boto3
import pytest
from moto import mock_aws

from src.load.bronze import write_json
from src.load.bronze_to_raw import check_bronze_vs_raw, load_bronze_file
from src.load.raw import (
    RowCountMismatchError,
    check_row_count,
    count_rows,
    ensure_raw_tables,
    parse_bronze_key,
    to_raw_rows,
)

TEST_SCHEMA = "raw_test"
BUCKET = "test-datalake"

BCB_KEY = "bronze/bcb_sgs/dt=2026-11-05/selic.json"
TX_KEY = "bronze/transactions/dt=2026-11-05/transactions.json"

TRANSACTIONS = [
    {
        "transaction_id": "t-1",
        "customer_cpf": "123.456.789-09",
        "transaction_at": "2026-11-05T10:00:00",
        "payment_type": "pix",
        "channel": "app",
        "amount": 100.5,
        "fee": 0.0,
        "status": "approved",
    },
    {
        "transaction_id": "t-2",
        "customer_cpf": None,
        "transaction_at": "2026-11-05T11:00:00",
        "payment_type": "boleto",
        "channel": "web",
        "amount": None,
        "fee": 2.49,
        "status": "declined",
    },
]


# ---------- unit tests ----------


def test_parse_bronze_key_for_bcb():
    f = parse_bronze_key(BCB_KEY)
    assert f.source == "bcb_sgs"
    assert f.dt == date(2026, 11, 5)
    assert f.table == "bcb_sgs"
    assert f.partition == {"dt": date(2026, 11, 5), "series_name": "selic"}


def test_parse_bronze_key_for_transactions():
    f = parse_bronze_key(TX_KEY)
    assert f.partition == {"dt": date(2026, 11, 5)}


@pytest.mark.parametrize(
    "key",
    [
        "bronze/bcb_sgs/2026-11-05/selic.json",  # missing dt=
        "silver/bcb_sgs/dt=2026-11-05/selic.json",  # wrong layer
        "bronze/unknown/dt=2026-11-05/x.json",  # unknown source
        "bronze/bcb_sgs/dt=2026-11-05/../x.json",  # path tricks
    ],
)
def test_parse_bronze_key_rejects_bad_keys(key):
    with pytest.raises(ValueError):
        parse_bronze_key(key)


def test_bcb_rows_get_english_names_and_keep_values():
    rows = to_raw_rows(parse_bronze_key(BCB_KEY), [{"data": "05/11/2026", "valor": "0.050788"}])
    assert rows == [("selic", "05/11/2026", "0.050788")]


def test_transaction_rows_are_text_and_keep_nulls():
    rows = to_raw_rows(parse_bronze_key(TX_KEY), TRANSACTIONS)
    assert rows[0] == (
        "t-1",
        "123.456.789-09",
        "2026-11-05T10:00:00",
        "pix",
        "app",
        "100.5",
        "0.0",
        "approved",
    )
    assert rows[1][1] is None  # customer_cpf
    assert rows[1][5] is None  # amount


def test_check_row_count():
    check_row_count(3, 3, "ok")
    with pytest.raises(RowCountMismatchError):
        check_row_count(3, 2, "bad")


# ---------- integration tests (need docker compose) ----------


@pytest.fixture
def raw_schema(warehouse_conn):
    """Fresh test schema with the raw tables. Dropped after the test."""
    with warehouse_conn, warehouse_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
    ensure_raw_tables(warehouse_conn, TEST_SCHEMA)
    yield TEST_SCHEMA
    with warehouse_conn, warehouse_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def _select(conn, query):
    with conn, conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


@pytest.mark.integration
def test_load_transactions_and_check_counts(warehouse_conn, raw_schema, s3):
    write_json(s3, BUCKET, TX_KEY, TRANSACTIONS)

    loaded = load_bronze_file(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema)

    assert loaded == 2
    assert check_bronze_vs_raw(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema) == 2
    rows = _select(
        warehouse_conn,
        f"SELECT transaction_id, amount, dt, source_file FROM {raw_schema}.transactions "
        "ORDER BY transaction_id",
    )
    assert rows == [
        ("t-1", "100.5", date(2026, 11, 5), TX_KEY),
        ("t-2", None, date(2026, 11, 5), TX_KEY),
    ]


@pytest.mark.integration
def test_loading_the_same_day_twice_does_not_duplicate(warehouse_conn, raw_schema, s3):
    write_json(s3, BUCKET, TX_KEY, TRANSACTIONS)

    load_bronze_file(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema)
    load_bronze_file(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema)

    assert _select(warehouse_conn, f"SELECT count(*) FROM {raw_schema}.transactions") == [(2,)]


@pytest.mark.integration
def test_reload_replaces_only_its_own_partition(warehouse_conn, raw_schema, s3):
    other_day = "bronze/transactions/dt=2026-11-06/transactions.json"
    write_json(s3, BUCKET, TX_KEY, TRANSACTIONS)
    write_json(s3, BUCKET, other_day, TRANSACTIONS[:1])
    load_bronze_file(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema)
    load_bronze_file(s3, BUCKET, other_day, warehouse_conn, raw_schema)

    # The day 05 file changes: now it has only one row.
    write_json(s3, BUCKET, TX_KEY, TRANSACTIONS[1:])
    load_bronze_file(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema)

    counts = _select(
        warehouse_conn,
        f"SELECT dt, count(*) FROM {raw_schema}.transactions GROUP BY dt ORDER BY dt",
    )
    assert counts == [(date(2026, 11, 5), 1), (date(2026, 11, 6), 1)]


@pytest.mark.integration
def test_bcb_series_are_separate_partitions(warehouse_conn, raw_schema, s3):
    cdi_key = "bronze/bcb_sgs/dt=2026-11-05/cdi.json"
    write_json(s3, BUCKET, BCB_KEY, [{"data": "05/11/2026", "valor": "0.050788"}])
    write_json(s3, BUCKET, cdi_key, [{"data": "05/11/2026", "valor": "0.050788"}])

    load_bronze_file(s3, BUCKET, BCB_KEY, warehouse_conn, raw_schema)
    load_bronze_file(s3, BUCKET, cdi_key, warehouse_conn, raw_schema)
    load_bronze_file(s3, BUCKET, BCB_KEY, warehouse_conn, raw_schema)  # re-run selic

    rows = _select(
        warehouse_conn,
        f"SELECT series_name, reference_date, value FROM {raw_schema}.bcb_sgs ORDER BY series_name",
    )
    assert rows == [("cdi", "05/11/2026", "0.050788"), ("selic", "05/11/2026", "0.050788")]


@pytest.mark.integration
def test_empty_day_loads_zero_rows(warehouse_conn, raw_schema, s3):
    key = "bronze/bcb_sgs/dt=2026-11-08/selic.json"
    write_json(s3, BUCKET, key, [])

    assert load_bronze_file(s3, BUCKET, key, warehouse_conn, raw_schema) == 0
    assert check_bronze_vs_raw(s3, BUCKET, key, warehouse_conn, raw_schema) == 0


@pytest.mark.integration
def test_count_check_fails_when_raw_is_different(warehouse_conn, raw_schema, s3):
    write_json(s3, BUCKET, TX_KEY, TRANSACTIONS)
    load_bronze_file(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema)

    # Someone deletes a row in raw by mistake.
    with warehouse_conn, warehouse_conn.cursor() as cur:
        cur.execute(f"DELETE FROM {raw_schema}.transactions WHERE transaction_id = 't-1'")

    assert count_rows(warehouse_conn, parse_bronze_key(TX_KEY), raw_schema) == 1
    with pytest.raises(RowCountMismatchError):
        check_bronze_vs_raw(s3, BUCKET, TX_KEY, warehouse_conn, raw_schema)
