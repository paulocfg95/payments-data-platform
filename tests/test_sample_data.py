"""Tests for the sample data loader used by CI and the dbt docs workflow."""

from datetime import date

import pytest

from src.load.raw import parse_bronze_key
from src.load.sample_data import load_sample_data, sample_days, sample_files

TEST_SCHEMA = "raw_sample_test"


def test_sample_days_are_business_days():
    days = sample_days()
    assert days == [date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)]
    assert all(d.isoweekday() <= 5 for d in days)


def test_sample_files_have_valid_bronze_keys():
    files = sample_files()
    # Per day: 3 BCB series + customers + transactions.
    assert len(files) == 3 * 5
    sources = {parse_bronze_key(key).source for key, _ in files}
    assert sources == {"bcb_sgs", "customers", "transactions"}


@pytest.fixture
def sample_schema(warehouse_conn):
    with warehouse_conn, warehouse_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
    yield TEST_SCHEMA
    with warehouse_conn, warehouse_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")


@pytest.mark.integration
def test_load_sample_data_is_idempotent(warehouse_conn, sample_schema):
    first = load_sample_data(warehouse_conn, sample_schema)
    second = load_sample_data(warehouse_conn, sample_schema)

    assert first == second
    assert first["bcb_sgs"] == 9
    assert first["customers"] == 3 * 500
    with warehouse_conn, warehouse_conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {sample_schema}.transactions")
        assert cur.fetchone()[0] == first["transactions"]
