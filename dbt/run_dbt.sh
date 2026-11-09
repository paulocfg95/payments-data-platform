#!/usr/bin/env bash
# Run dbt with the pseudonymization salt as a PostgreSQL session setting.
#
# The salt goes to PostgreSQL through PGOPTIONS, and the SQL reads it with
# current_setting('app.pseudonymization_salt'). This way the salt never
# appears in compiled SQL, logs or dbt docs.
#
# Usage: bash run_dbt.sh <dbt command>   e.g. bash run_dbt.sh build
set -euo pipefail

: "${PSEUDONYMIZATION_SALT:?PSEUDONYMIZATION_SALT is not set. Check your .env file.}"
if [[ ! "${PSEUDONYMIZATION_SALT}" =~ ^[A-Za-z0-9_]{16,}$ ]]; then
  echo "PSEUDONYMIZATION_SALT must have at least 16 letters, numbers or _." >&2
  exit 1
fi
export PGOPTIONS="-c app.pseudonymization_salt=${PSEUDONYMIZATION_SALT}"

cd "$(dirname "$0")"
DBT_BIN="${DBT_BIN:-/home/airflow/dbt-venv/bin/dbt}"
exec "${DBT_BIN}" "$@"
