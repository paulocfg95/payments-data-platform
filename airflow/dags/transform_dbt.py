"""Run dbt (silver and gold layers) when new raw data arrives.

Scheduled on Airflow Assets, not on a clock: the DAG runs after
ingest_bcb and generate_transactions have both updated their raw tables
(and passed the row count checks).

Steps:
1. dbt deps  - install dbt packages (dbt_utils)
2. dbt build - seeds, models and data tests, in dependency order.
   A failing test stops the models that depend on it.

The incremental models only process rows loaded after the last run,
so one dbt run can handle many days after a backfill.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from pipeline_assets import RAW_BCB_SGS, RAW_CUSTOMERS, RAW_TRANSACTIONS

# run_dbt.sh passes the pseudonymization salt to PostgreSQL from an
# environment variable, so it never shows in the task command or logs.
RUN_DBT = "bash /opt/airflow/dbt/run_dbt.sh"

default_args = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=30),
}


@dag(
    dag_id="transform_dbt",
    description="Build the silver and gold layers with dbt when raw data changes",
    # Runs when all three raw assets were updated since the last run.
    schedule=(RAW_BCB_SGS & RAW_CUSTOMERS & RAW_TRANSACTIONS),
    start_date=pendulum.datetime(2026, 10, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["dbt", "silver", "gold"],
)
def transform_dbt():
    dbt_deps = BashOperator(task_id="dbt_deps", bash_command=f"{RUN_DBT} deps")
    dbt_build = BashOperator(task_id="dbt_build", bash_command=f"{RUN_DBT} build")

    dbt_deps >> dbt_build


transform_dbt()
