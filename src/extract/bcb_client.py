"""Client for the Banco Central do Brasil SGS time series API.

API docs: https://dadosabertos.bcb.gov.br (search for "SGS").
URL format:
    https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados
        ?formato=json&dataInicial=dd/MM/yyyy&dataFinal=dd/MM/yyyy

A successful response is a JSON list like:
    [{"data": "05/11/2026", "valor": "0.050788"}]

When a date range has no values (weekends, holidays), the API
returns HTTP 404. We treat that as an empty list.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

# Series used by the project. Name -> SGS code.
SERIES: dict[str, int] = {
    "selic": 11,  # Selic rate, % per day
    "cdi": 12,  # CDI rate, % per day
    "usd_brl_ptax": 1,  # USD/BRL exchange rate (sell), daily
}

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class BCBError(Exception):
    """Base error for the BCB client."""


class BCBRequestError(BCBError):
    """The request failed after all retries, or got a non-retryable error."""


class BCBSchemaError(BCBError):
    """The response does not have the expected format."""


def _format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def validate_payload(payload: object) -> list[dict]:
    """Check that the payload is a list of {"data": dd/MM/yyyy, "valor": number}.

    Returns the payload unchanged. Raises BCBSchemaError if it is invalid.
    """
    if not isinstance(payload, list):
        raise BCBSchemaError(f"Expected a list, got {type(payload).__name__}")

    for i, row in enumerate(payload):
        if not isinstance(row, dict) or set(row) != {"data", "valor"}:
            raise BCBSchemaError(f"Row {i} must have only 'data' and 'valor': {row!r}")
        try:
            datetime.strptime(row["data"], "%d/%m/%Y")
        except (TypeError, ValueError) as exc:
            raise BCBSchemaError(f"Row {i} has an invalid date: {row['data']!r}") from exc
        try:
            float(row["valor"])
        except (TypeError, ValueError) as exc:
            raise BCBSchemaError(f"Row {i} has an invalid value: {row['valor']!r}") from exc

    return payload


class BCBClient:
    """Small HTTP client for SGS series with timeout, retries and validation."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (5, 30),
        max_retries: int = 3,
        backoff_base: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.sleep = sleep

    def fetch_series(self, code: int, start: date, end: date) -> list[dict]:
        """Fetch the values of one SGS series between two dates (inclusive).

        Returns the raw rows from the API, already validated.
        Returns an empty list when there is no data for the range.
        """
        if start > end:
            raise ValueError(f"start ({start}) must be before or equal to end ({end})")

        url = BASE_URL.format(code=code)
        params = {
            "formato": "json",
            "dataInicial": _format_date(start),
            "dataFinal": _format_date(end),
        }

        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                logger.warning("SGS %s attempt %d/%d failed: %s", code, attempt, attempts, exc)
                self._wait_or_raise(attempt, attempts, f"network error: {exc}")
                continue

            if response.status_code == 404:
                logger.info("SGS %s has no data from %s to %s", code, start, end)
                return []

            if response.status_code in RETRY_STATUS_CODES:
                logger.warning(
                    "SGS %s attempt %d/%d got HTTP %d",
                    code,
                    attempt,
                    attempts,
                    response.status_code,
                )
                self._wait_or_raise(attempt, attempts, f"HTTP {response.status_code}")
                continue

            if not response.ok:
                raise BCBRequestError(
                    f"SGS {code} returned HTTP {response.status_code}: {response.text[:200]}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise BCBSchemaError(f"SGS {code} did not return valid JSON") from exc

            rows = validate_payload(payload)
            logger.info("SGS %s returned %d rows from %s to %s", code, len(rows), start, end)
            return rows

        # Not reachable: the loop always returns or raises.
        raise BCBRequestError(f"SGS {code} failed after {attempts} attempts")

    def _wait_or_raise(self, attempt: int, attempts: int, reason: str) -> None:
        if attempt >= attempts:
            raise BCBRequestError(f"Giving up after {attempts} attempts ({reason})")
        delay = self.backoff_base**attempt
        logger.info("Waiting %.1f seconds before the next attempt", delay)
        self.sleep(delay)
