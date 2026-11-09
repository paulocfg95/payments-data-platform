"""Tests for the BCB SGS client. All HTTP calls are mocked (no network)."""

from datetime import date

import pytest
import requests
import responses
from responses import matchers

from src.extract.bcb_client import (
    BASE_URL,
    BCBClient,
    BCBRequestError,
    BCBSchemaError,
    validate_payload,
)

SELIC_URL = BASE_URL.format(code=11)
DAY = date(2026, 11, 5)


@pytest.fixture
def sleeps():
    """Collect wait times instead of really sleeping."""
    return []


@pytest.fixture
def client(sleeps):
    return BCBClient(max_retries=3, backoff_base=2.0, sleep=sleeps.append)


@responses.activate
def test_fetch_series_returns_rows_and_sends_date_params(client):
    responses.get(
        SELIC_URL,
        json=[{"data": "05/11/2026", "valor": "0.050788"}],
        match=[
            matchers.query_param_matcher(
                {"formato": "json", "dataInicial": "05/11/2026", "dataFinal": "05/11/2026"}
            )
        ],
    )

    rows = client.fetch_series(11, DAY, DAY)

    assert rows == [{"data": "05/11/2026", "valor": "0.050788"}]


@responses.activate
def test_404_means_no_data(client):
    responses.get(SELIC_URL, status=404, json={"erro": {"detail": "Value(s) not found"}})

    assert client.fetch_series(11, DAY, DAY) == []


@responses.activate
def test_retries_on_server_error_then_succeeds(client, sleeps):
    responses.get(SELIC_URL, status=500)
    responses.get(SELIC_URL, status=503)
    responses.get(SELIC_URL, json=[{"data": "05/11/2026", "valor": "0.05"}])

    rows = client.fetch_series(11, DAY, DAY)

    assert len(rows) == 1
    assert sleeps == [2.0, 4.0]  # exponential backoff


@responses.activate
def test_gives_up_after_max_retries(client, sleeps):
    for _ in range(4):
        responses.get(SELIC_URL, status=500)

    with pytest.raises(BCBRequestError, match="4 attempts"):
        client.fetch_series(11, DAY, DAY)

    assert len(responses.calls) == 4
    assert sleeps == [2.0, 4.0, 8.0]


@responses.activate
def test_retries_on_timeout(client, sleeps):
    responses.get(SELIC_URL, body=requests.Timeout("read timeout"))
    responses.get(SELIC_URL, json=[])

    assert client.fetch_series(11, DAY, DAY) == []
    assert sleeps == [2.0]


@responses.activate
def test_client_error_is_not_retried(client):
    responses.get(SELIC_URL, status=400, body="bad request")

    with pytest.raises(BCBRequestError, match="HTTP 400"):
        client.fetch_series(11, DAY, DAY)

    assert len(responses.calls) == 1


@responses.activate
def test_invalid_json_raises_schema_error(client):
    responses.get(SELIC_URL, body="<html>maintenance</html>")

    with pytest.raises(BCBSchemaError):
        client.fetch_series(11, DAY, DAY)


def test_start_after_end_is_rejected(client):
    with pytest.raises(ValueError):
        client.fetch_series(11, date(2026, 11, 6), date(2026, 11, 5))


@pytest.mark.parametrize(
    "payload",
    [
        {"data": "05/11/2026", "valor": "1"},  # not a list
        [{"data": "05/11/2026"}],  # missing field
        [{"data": "2026-11-05", "valor": "1"}],  # wrong date format
        [{"data": "05/11/2026", "valor": "abc"}],  # value is not a number
        [{"data": "05/11/2026", "valor": "1", "extra": 1}],  # unexpected field
    ],
)
def test_validate_payload_rejects_bad_schema(payload):
    with pytest.raises(BCBSchemaError):
        validate_payload(payload)


def test_validate_payload_accepts_empty_list():
    assert validate_payload([]) == []
