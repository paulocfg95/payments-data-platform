"""Daily ingestion of Banco Central (SGS) indicators into the bronze layer.

One mapped task per series (selic, cdi, usd_brl_ptax). Each task fetches
the values for the run's data interval day and writes:
    bronze/bcb_sgs/dt=YYYY-MM-DD/<series>.json

The day comes from the Airflow data interval, never from the wall clock,
so re-runs and backfills always process the same day and overwrite the
same file (idempotent).
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task
from airflow.timetables.interval import CronDataIntervalTimetable

from src.extract.bcb_client import SERIES

LOCAL_TZ = pendulum.timezone("America/Sao_Paulo")

default_args = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "execution_timeout": timedelta(minutes=10),
}


@dag(
    dag_id="ingest_bcb",
    description="Fetch BCB SGS daily indicators and save raw JSON to bronze",
    # Runs every day at 10:00 (Sao Paulo) for the previous day.
    schedule=CronDataIntervalTimetable("0 10 * * *", timezone=LOCAL_TZ),
    start_date=pendulum.datetime(2026, 10, 1, tz=LOCAL_TZ),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["bronze", "bcb"],
)
def ingest_bcb():
    @task
    def ingest(series_name: str) -> str:
        # Imports inside the task keep DAG parsing fast.
        from src.config import StorageConfig
        from src.extract.bcb_client import BCBClient
        from src.extract.bcb_to_bronze import ingest_series_day
        from src.load.bronze import get_s3_client

        context = get_current_context()
        day = context["data_interval_start"].in_timezone(LOCAL_TZ).date()

        config = StorageConfig.from_env()
        return ingest_series_day(
            series_name=series_name,
            day=day,
            bcb_client=BCBClient(),
            s3_client=get_s3_client(config),
            bucket=config.bucket,
        )

    ingest.expand(series_name=sorted(SERIES))


ingest_bcb()
