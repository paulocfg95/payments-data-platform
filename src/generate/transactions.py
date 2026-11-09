"""Synthetic payment transactions, deterministic by date.

All data here is FAKE. The random seed comes from the processing date
(YYYYMMDD), so generating the same day again returns exactly the same
transactions. This is what makes re-runs and backfills idempotent.

On purpose, a small share of rows has quality problems, so the data tests
and the silver layer have something to catch:
- duplicated rows (same transaction_id)
- null customer_cpf
- null amount
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, time, timedelta

MIN_TRANSACTIONS = 800
MAX_TRANSACTIONS = 1500

PAYMENT_TYPES = ["pix", "credit_card", "debit_card", "boleto"]
PAYMENT_TYPE_WEIGHTS = [0.50, 0.25, 0.15, 0.10]

CHANNELS = ["app", "web", "pos"]
CHANNEL_WEIGHTS = [0.60, 0.25, 0.15]

STATUSES = ["approved", "declined", "refunded"]
STATUS_WEIGHTS = [0.90, 0.08, 0.02]

# Fee rules per payment type: (percent of amount, fixed value in BRL)
FEE_RULES = {
    "pix": (0.0, 0.0),
    "debit_card": (0.015, 0.0),
    "credit_card": (0.035, 0.0),
    "boleto": (0.0, 2.49),
}

# Typical ticket per payment type, used as the median of a log-normal amount
MEDIAN_AMOUNT = {
    "pix": 80.0,
    "debit_card": 60.0,
    "credit_card": 150.0,
    "boleto": 300.0,
}

# Share of rows with quality problems
DUPLICATE_RATE = 0.01
NULL_CPF_RATE = 0.005
NULL_AMOUNT_RATE = 0.005


def seed_for_date(day: date) -> int:
    """Seed derived from the date, e.g. 2026-11-05 -> 20261105."""
    return int(day.strftime("%Y%m%d"))


def _pick_channel(rng: random.Random, payment_type: str) -> str:
    # Boleto is not paid on a card machine (pos).
    if payment_type == "boleto":
        return rng.choices(["app", "web"], weights=[0.5, 0.5])[0]
    return rng.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]


def _amount(rng: random.Random, payment_type: str) -> float:
    median = MEDIAN_AMOUNT[payment_type]
    value = rng.lognormvariate(0, 0.9) * median
    return round(max(value, 1.0), 2)


def _fee(payment_type: str, amount: float) -> float:
    percent, fixed = FEE_RULES[payment_type]
    return round(amount * percent + fixed, 2)


def generate_transactions(day: date, customers: list[dict]) -> list[dict]:
    """Return the fake transactions of one day for the given customers."""
    if not customers:
        raise ValueError("The customer list is empty")

    rng = random.Random(seed_for_date(day))
    count = rng.randint(MIN_TRANSACTIONS, MAX_TRANSACTIONS)
    day_start = datetime.combine(day, time.min)

    # Customers created after this day cannot pay yet.
    eligible = [c for c in customers if c["created_at"][:10] <= day.isoformat()]
    if not eligible:
        raise ValueError(f"No customer exists on {day}")

    rows = []
    for _ in range(count):
        customer = rng.choice(eligible)
        payment_type = rng.choices(PAYMENT_TYPES, weights=PAYMENT_TYPE_WEIGHTS)[0]
        amount = _amount(rng, payment_type)
        transaction_at = day_start + timedelta(seconds=rng.randrange(24 * 60 * 60))

        rows.append(
            {
                "transaction_id": str(uuid.UUID(int=rng.getrandbits(128), version=4)),
                "customer_cpf": customer["cpf"],
                "transaction_at": transaction_at.isoformat(timespec="seconds"),
                "payment_type": payment_type,
                "channel": _pick_channel(rng, payment_type),
                "amount": amount,
                "fee": _fee(payment_type, amount),
                "status": rng.choices(STATUSES, weights=STATUS_WEIGHTS)[0],
            }
        )

    rows.sort(key=lambda r: r["transaction_at"])
    return _add_quality_issues(rows, rng)


def _add_quality_issues(rows: list[dict], rng: random.Random) -> list[dict]:
    """Add nulls and duplicates in a small, deterministic share of rows."""
    result = []
    for row in rows:
        if rng.random() < NULL_CPF_RATE:
            row["customer_cpf"] = None
        if rng.random() < NULL_AMOUNT_RATE:
            row["amount"] = None
        result.append(row)
        if rng.random() < DUPLICATE_RATE:
            result.append(dict(row))
    return result
