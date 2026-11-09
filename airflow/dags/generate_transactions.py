"""Daily generation of synthetic payment data into the bronze layer.

All customers and transactions are FAKE (Faker). The generator uses the
run's data interval day as the random seed, so a re-run or a backfill
of the same day writes exactly the same files:
    bronze/customers/dt=YYYY-MM-DD/customers.json
    bronze/transactions/dt=YYYY-MM-DD/transactions.json
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task
from airflow.timetables.interval import CronDataIntervalTimetable

LOCAL_TZ = pendulum.timezone("America/Sao_Paulo")

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
}


@dag(
    dag_id="generate_transactions",
    description="Generate synthetic customers and transactions and save raw JSON to bronze",
    # Runs every day at 02:00 (Sao Paulo) for the previous day.
    schedule=CronDataIntervalTimetable("0 2 * * *", timezone=LOCAL_TZ),
    start_date=pendulum.datetime(2026, 10, 1, tz=LOCAL_TZ),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["bronze", "synthetic"],
)
def generate_transactions():
    @task
    def generate_to_bronze() -> dict[str, str]:
        from src.config import StorageConfig
        from src.generate.to_bronze import generate_day_to_bronze
        from src.load.bronze import get_s3_client

        context = get_current_context()
        day = context["data_interval_start"].in_timezone(LOCAL_TZ).date()

        config = StorageConfig.from_env()
        return generate_day_to_bronze(day, get_s3_client(config), config.bucket)

    generate_to_bronze()


generate_transactions()
