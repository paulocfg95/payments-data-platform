"""Tests for the bronze writer and the BCB -> bronze job, using a fake S3 (moto)."""

from datetime import date

import boto3
import pytest
from moto import mock_aws

from src.extract.bcb_to_bronze import ingest_series_day
from src.load.bronze import build_bronze_key, read_json, write_json

BUCKET = "test-datalake"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


class FakeBCBClient:
    """Returns fixed rows and remembers the calls."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def fetch_series(self, code, start, end):
        self.calls.append((code, start, end))
        return self.rows


def test_build_bronze_key():
    key = build_bronze_key("bcb_sgs", date(2026, 11, 5), "selic.json")
    assert key == "bronze/bcb_sgs/dt=2026-11-05/selic.json"


def test_write_then_read(s3):
    write_json(s3, BUCKET, "bronze/x/dt=2026-11-05/a.json", [{"a": 1}])
    assert read_json(s3, BUCKET, "bronze/x/dt=2026-11-05/a.json") == [{"a": 1}]


def test_second_write_replaces_file(s3):
    key = "bronze/x/dt=2026-11-05/a.json"
    write_json(s3, BUCKET, key, [{"a": 1}])
    write_json(s3, BUCKET, key, [{"a": 2}])

    objects = s3.list_objects_v2(Bucket=BUCKET)["Contents"]
    assert len(objects) == 1
    assert read_json(s3, BUCKET, key) == [{"a": 2}]


def test_ingest_series_day_writes_partition(s3):
    rows = [{"data": "05/11/2026", "valor": "0.050788"}]
    bcb = FakeBCBClient(rows)
    day = date(2026, 11, 5)

    key = ingest_series_day("selic", day, bcb, s3, BUCKET)

    assert key == "bronze/bcb_sgs/dt=2026-11-05/selic.json"
    assert bcb.calls == [(11, day, day)]
    assert read_json(s3, BUCKET, key) == rows


def test_ingest_series_day_is_idempotent(s3):
    day = date(2026, 11, 5)
    bcb = FakeBCBClient([{"data": "05/11/2026", "valor": "0.05"}])

    ingest_series_day("cdi", day, bcb, s3, BUCKET)
    ingest_series_day("cdi", day, bcb, s3, BUCKET)

    assert s3.list_objects_v2(Bucket=BUCKET)["KeyCount"] == 1


def test_ingest_series_day_writes_empty_day(s3):
    key = ingest_series_day("usd_brl_ptax", date(2026, 11, 8), FakeBCBClient([]), s3, BUCKET)
    assert read_json(s3, BUCKET, key) == []


def test_unknown_series_is_rejected(s3):
    with pytest.raises(ValueError):
        ingest_series_day("ipca", date(2026, 11, 5), FakeBCBClient([]), s3, BUCKET)
