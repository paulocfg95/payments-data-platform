"""Fixed registry of synthetic customers.

All data here is FAKE, generated with Faker (pt_BR locale).
No real person is represented.

The registry always uses the same seed, so every run returns the same
customers. Transactions reference customers by CPF.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from faker import Faker

CUSTOMER_SEED = 42
CUSTOMER_COUNT = 500

# Every customer is created before the first day of transactions.
CREATED_FROM = datetime(2024, 1, 1)
CREATED_TO = datetime(2026, 9, 30, 23, 59, 59)

SEGMENTS = ["individual", "business"]
SEGMENT_WEIGHTS = [0.85, 0.15]


def generate_customers(count: int = CUSTOMER_COUNT, seed: int = CUSTOMER_SEED) -> list[dict]:
    """Return a list of fake customers. Same seed -> same customers."""
    fake = Faker("pt_BR")
    fake.seed_instance(seed)
    rng = random.Random(seed)

    # Dates come from our own random.Random, not from Faker: Faker's date
    # functions use randomness differently on different platforms, which
    # would break determinism between a laptop and the Airflow container.
    span_seconds = int((CREATED_TO - CREATED_FROM).total_seconds())

    customers = []
    for _ in range(count):
        created_at = CREATED_FROM + timedelta(seconds=rng.randrange(span_seconds))
        customers.append(
            {
                "cpf": fake.unique.cpf(),
                "name": fake.name(),
                "email": fake.unique.email(),
                "state": fake.estado_sigla(),
                "city": fake.city(),
                "created_at": created_at.isoformat(timespec="seconds"),
                "segment": rng.choices(SEGMENTS, weights=SEGMENT_WEIGHTS)[0],
            }
        )
    return customers
