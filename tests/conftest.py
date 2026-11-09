"""Shared pytest setup.

Integration tests need the warehouse from docker compose. Its settings come
from env vars; if a .env file exists, missing vars are read from it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ENV_FILE = Path(__file__).parent.parent / ".env"


def _load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


_load_env_file()


@pytest.fixture(scope="session")
def warehouse_conn():
    """Connection to the warehouse. Skips the test if it is not running."""
    import psycopg2

    from src.load.raw import get_connection

    try:
        conn = get_connection()
    except (psycopg2.OperationalError, RuntimeError) as exc:
        pytest.skip(f"Warehouse not available: {exc}")
    yield conn
    conn.close()
