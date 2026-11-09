"""Tests for the synthetic customer and transaction generators."""

import hashlib
import json
from datetime import date

import pytest

from src.generate.customers import CUSTOMER_COUNT, generate_customers
from src.generate.transactions import (
    CHANNELS,
    MAX_TRANSACTIONS,
    MIN_TRANSACTIONS,
    PAYMENT_TYPES,
    STATUSES,
    generate_transactions,
    seed_for_date,
)

DAY = date(2026, 11, 5)

CUSTOMER_FIELDS = {"cpf", "name", "email", "state", "city", "created_at", "segment"}
TRANSACTION_FIELDS = {
    "transaction_id",
    "customer_cpf",
    "transaction_at",
    "payment_type",
    "channel",
    "amount",
    "fee",
    "status",
}


@pytest.fixture(scope="module")
def customers():
    return generate_customers()


@pytest.fixture(scope="module")
def transactions(customers):
    return generate_transactions(DAY, customers)


# ---------- customers ----------


def test_customers_are_deterministic(customers):
    assert generate_customers() == customers


def test_customers_schema_and_values(customers):
    assert len(customers) == CUSTOMER_COUNT
    for c in customers:
        assert set(c) == CUSTOMER_FIELDS
        assert c["segment"] in {"individual", "business"}
        assert len(c["state"]) == 2
        assert c["created_at"] < "2026-10-01"


def test_customer_cpf_and_email_are_unique(customers):
    assert len({c["cpf"] for c in customers}) == len(customers)
    assert len({c["email"] for c in customers}) == len(customers)


# ---------- transactions ----------


def test_seed_for_date():
    assert seed_for_date(DAY) == 20261105


def test_same_day_gives_same_transactions(customers, transactions):
    assert generate_transactions(DAY, customers) == transactions


def test_different_days_give_different_transactions(customers, transactions):
    other = generate_transactions(date(2026, 11, 6), customers)
    assert {t["transaction_id"] for t in other}.isdisjoint(
        {t["transaction_id"] for t in transactions}
    )


def test_transaction_schema_and_values(transactions):
    for t in transactions:
        assert set(t) == TRANSACTION_FIELDS
        assert t["payment_type"] in PAYMENT_TYPES
        assert t["channel"] in CHANNELS
        assert t["status"] in STATUSES
        assert t["transaction_at"].startswith("2026-11-05T")
        assert t["fee"] >= 0
        if t["amount"] is not None:
            assert t["amount"] >= 1.0


def test_volume_is_in_range(transactions):
    unique_ids = {t["transaction_id"] for t in transactions}
    assert MIN_TRANSACTIONS <= len(unique_ids) <= MAX_TRANSACTIONS


def test_boleto_is_never_paid_on_pos(transactions):
    assert not [t for t in transactions if t["payment_type"] == "boleto" and t["channel"] == "pos"]


def test_pix_has_no_fee(transactions):
    assert all(t["fee"] == 0 for t in transactions if t["payment_type"] == "pix")


def test_every_cpf_exists_in_customer_registry(customers, transactions):
    known = {c["cpf"] for c in customers}
    assert all(t["customer_cpf"] in known for t in transactions if t["customer_cpf"] is not None)


# ---------- quality issues (on purpose) ----------


def _rates(transactions_list):
    total = len(transactions_list)
    ids = [t["transaction_id"] for t in transactions_list]
    return {
        "duplicates": (total - len(set(ids))) / total,
        "null_cpf": sum(t["customer_cpf"] is None for t in transactions_list) / total,
        "null_amount": sum(t["amount"] is None for t in transactions_list) / total,
    }


def test_quality_issues_exist_in_small_share(customers):
    # Use a full week so the small rates are stable.
    week = []
    for d in range(1, 8):
        week += generate_transactions(date(2026, 11, d), customers)

    rates = _rates(week)
    assert 0 < rates["duplicates"] < 0.03
    assert 0 < rates["null_cpf"] < 0.02
    assert 0 < rates["null_amount"] < 0.02


def test_empty_customer_list_is_rejected():
    with pytest.raises(ValueError):
        generate_transactions(DAY, [])


# ---------- same output on every machine ----------


def _digest(data) -> str:
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()[:16]


def test_output_is_the_same_on_every_machine(customers):
    """Golden values. If this fails, the generator changed or a library
    behaves differently on this platform, and re-runs would not be idempotent.
    Update the values only when the generator is changed on purpose."""
    assert _digest(customers) == "282a575ac7ba4b7b"
    assert _digest(generate_transactions(date(2026, 11, 4), customers)) == "0103bedfac907b07"
