"""Job: generate one day of synthetic data and save it to bronze."""

from __future__ import annotations

import logging
from datetime import date

from src.generate.customers import generate_customers
from src.generate.transactions import generate_transactions
from src.load.bronze import build_bronze_key, write_json

logger = logging.getLogger(__name__)


def generate_day_to_bronze(day: date, s3_client, bucket: str) -> dict[str, str]:
    """Write the customer snapshot and the transactions of `day` to bronze.

    Both files go to the daily partition and are replaced on a re-run.
    Returns the written keys by source name.
    """
    customers = generate_customers()
    transactions = generate_transactions(day, customers)

    keys = {
        "customers": build_bronze_key("customers", day, "customers.json"),
        "transactions": build_bronze_key("transactions", day, "transactions.json"),
    }
    write_json(s3_client, bucket, keys["customers"], customers)
    write_json(s3_client, bucket, keys["transactions"], transactions)

    logger.info("Day %s: %d customers, %d transactions", day, len(customers), len(transactions))
    return keys
