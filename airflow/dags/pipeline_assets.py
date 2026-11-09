"""Airflow Assets for the raw tables.

The load DAGs mark these assets as updated after the raw load and the
row count check pass. The dbt DAG (transform_dbt) is scheduled on them,
so dbt runs when new raw data arrives.
"""

from airflow.sdk import Asset

RAW_BCB_SGS = Asset(name="raw_bcb_sgs", uri="warehouse://raw/bcb_sgs")
RAW_TRANSACTIONS = Asset(name="raw_transactions", uri="warehouse://raw/transactions")
RAW_CUSTOMERS = Asset(name="raw_customers", uri="warehouse://raw/customers")
