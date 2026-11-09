"""Daily ingestion of Banco Central (SGS) indicators: API -> bronze -> raw.

One mapped task per series (selic, cdi, usd_brl_ptax):
1. ingest: fetch the values of the run's day and write
   bronze/bcb_sgs/dt=YYYY-MM-DD/<series>.json
2. load_raw: replace that day and series in raw.bcb_sgs
3. check_counts: bronze and raw must have the same row count.
   On success, the raw_bcb_sgs asset is marked as updated.

The day comes from the Airflow data interval, never from the wall clock,
so re-runs and backfills always process the same day and overwrite the
same file (idempotent).
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task
from airflow.timetables.interval import CronDataIntervalTimetable

from pipeline_assets import RAW_BCB_SGS
from raw_tasks import check_counts, create_raw_tables, load_raw
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
    description="Fetch BCB SGS daily indicators, save to bronze and load into raw",
    # Runs every day at 10:00 (Sao Paulo) for the previous day.
    schedule=CronDataIntervalTimetable("0 10 * * *", timezone=LOCAL_TZ),
    start_date=pendulum.datetime(2026, 10, 1, tz=LOCAL_TZ),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["bronze", "raw", "bcb"],
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

    keys = ingest.expand(series_name=sorted(SERIES))
    loaded = load_raw.expand(key=keys)
    create_raw_tables() >> loaded
    check_counts.override(outlets=[RAW_BCB_SGS]).expand(key=loaded)


ingest_bcb()
