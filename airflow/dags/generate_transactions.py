"""Daily generation of synthetic payment data: generator -> bronze -> raw.

All customers and transactions are FAKE (Faker). The generator uses the
run's data interval day as the random seed, so a re-run or a backfill
of the same day writes exactly the same files:
    bronze/customers/dt=YYYY-MM-DD/customers.json
    bronze/transactions/dt=YYYY-MM-DD/transactions.json

Then each file is loaded into raw (raw.customers, raw.transactions) and the
row counts are checked against bronze. On success, the raw_customers and
raw_transactions assets are marked as updated.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task
from airflow.timetables.interval import CronDataIntervalTimetable

from pipeline_assets import RAW_CUSTOMERS, RAW_TRANSACTIONS
from raw_tasks import check_counts, create_raw_tables, load_raw

LOCAL_TZ = pendulum.timezone("America/Sao_Paulo")

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
}


@dag(
    dag_id="generate_transactions",
    description="Generate synthetic customers and transactions, save to bronze, load into raw",
    # Runs every day at 02:00 (Sao Paulo) for the previous day.
    schedule=CronDataIntervalTimetable("0 2 * * *", timezone=LOCAL_TZ),
    start_date=pendulum.datetime(2026, 10, 1, tz=LOCAL_TZ),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["bronze", "raw", "synthetic"],
)
def generate_transactions():
    # multiple_outputs: each dict key becomes its own XCom, used below.
    @task(multiple_outputs=True)
    def generate_to_bronze() -> dict[str, str]:
        from src.config import StorageConfig
        from src.generate.to_bronze import generate_day_to_bronze
        from src.load.bronze import get_s3_client

        context = get_current_context()
        day = context["data_interval_start"].in_timezone(LOCAL_TZ).date()

        config = StorageConfig.from_env()
        return generate_day_to_bronze(day, get_s3_client(config), config.bucket)

    keys = generate_to_bronze()
    tables_ready = create_raw_tables()

    # One branch per file, so each table has its own load, check and asset.
    for source, asset in [("customers", RAW_CUSTOMERS), ("transactions", RAW_TRANSACTIONS)]:
        loaded = load_raw.override(task_id=f"load_raw_{source}")(keys[source])
        tables_ready >> loaded
        check_counts.override(task_id=f"check_counts_{source}", outlets=[asset])(loaded)


generate_transactions()
