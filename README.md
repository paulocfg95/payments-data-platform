# payments-data-platform

> **Resumo (PT-BR):** Plataforma de dados de pagamentos para portfólio. Coleta indicadores reais do Banco Central (Selic, CDI e dólar PTAX) e, nas próximas fases, transações sintéticas. Os dados passam por um data lake (bronze), um PostgreSQL e modelos dbt em star schema, com orquestração no Airflow e testes automatizados.

## What this project does

A small but complete data platform for the payments domain. It collects public data from the
Banco Central do Brasil, stores the raw data in an object storage (bronze layer), and will load it
into a PostgreSQL warehouse and model it with dbt as a star schema. Everything runs locally with
`docker compose up`.

**Status:** Phase 1 done (infrastructure + BCB ingestion to bronze). Phase 2 in progress:
synthetic transaction generator and bronze → raw load done. See [Roadmap](#roadmap).

## Architecture

```
Banco Central SGS API ──> ingest_bcb ────────────┐
                                                  ├─> bronze (MinIO / S3) ─> raw (PostgreSQL)
Faker generator ───────> generate_transactions ───┘   JSON files by day       text tables by day
                                                                                    │
                                                                                    │ Airflow Assets
                                                                    (next)          v
                                                  dbt staging (silver) ─> dbt marts (gold, star schema)
```

Each ingestion DAG does three steps per file: **write to bronze → load into raw → check the
row count**. When the check passes, the DAG marks an Airflow Asset (`raw_bcb_sgs`,
`raw_customers`, `raw_transactions`) as updated. The dbt DAG will run when these assets change.

## Tech stack

| Tool | Why |
|---|---|
| Python 3.12 | Extraction code in small, testable modules |
| Apache Airflow 3.3 | Daily scheduling, retries, backfill |
| MinIO (local S3) | Bronze layer with the same API as Amazon S3. The code uses boto3, so switching to S3 only changes env vars |
| PostgreSQL 16 | Data warehouse (raw schema now, dbt models next) and Airflow metadata |
| psycopg2 | Fast batch inserts into PostgreSQL (`execute_values`) |
| pytest, responses, moto | Unit tests without network or real cloud |
| ruff | Python lint and format |
| Docker Compose | One command to start everything |

## Data sources

Banco Central do Brasil, SGS time series API (real public data):

| Series | SGS code | Meaning |
|---|---|---|
| `selic` | 11 | Selic rate, % per day |
| `cdi` | 12 | CDI rate, % per day |
| `usd_brl_ptax` | 1 | USD/BRL exchange rate (sell), daily |

URL: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json&dataInicial=dd/MM/yyyy&dataFinal=dd/MM/yyyy`

Synthetic payments (fake data, generated with Faker `pt_BR`):

| File | Content |
|---|---|
| `bronze/customers/dt=YYYY-MM-DD/customers.json` | Fixed registry of 500 customers (`cpf`, `name`, `email`, `state`, `city`, `created_at`, `segment`) |
| `bronze/transactions/dt=YYYY-MM-DD/transactions.json` | 800 to 1,500 transactions per day (`transaction_id`, `customer_cpf`, `transaction_at`, `payment_type`, `channel`, `amount`, `fee`, `status`) |

About 1% of the transactions are duplicated and about 0.5% have a null `customer_cpf` or
`amount`, on purpose. The silver layer cleans them and the data tests check the result.

## Raw layer (PostgreSQL)

| Table | Partition (what a re-run replaces) |
|---|---|
| `raw.bcb_sgs` | one day and one series |
| `raw.transactions` | one day |
| `raw.customers` | one day (full snapshot of the registry) |

Data columns are `text`, a faithful copy of the bronze file. Types are set later in dbt.
The BCB fields `data` and `valor` get English names (`reference_date`, `value`); the values
do not change. Every table also has `dt`, `source_file` (the bronze key) and `loaded_at`.

## Dimensional model

Planned for phase 2. The main fact table, `fact_transactions`, will have **one row per transaction**.
`fact_daily_indicators` will have **one row per day** with the BCB indicators.

## How to run locally

Requirements: Docker Desktop, and Python 3.12+ for the tests.

```bash
# 1. Create your local config (change the passwords)
cp .env.example .env

# 2. Start everything
docker compose up -d --build
```

| Service | URL |
|---|---|
| Airflow UI | http://localhost:8081 (no login, local only) |
| MinIO console | http://localhost:9001 (user and password from `.env`) |
| Warehouse | `localhost:5433`, database `warehouse` |

Ports can be changed in `.env` (`AIRFLOW_PORT`, `WAREHOUSE_PORT`).

| DAG | Schedule (São Paulo time) | Processes |
|---|---|---|
| `ingest_bcb` | every day at 10:00 | the previous day |
| `generate_transactions` | every day at 02:00 | the previous day |

To load past days (backfill):

```bash
docker compose exec airflow-scheduler \
  airflow backfill create --dag-id ingest_bcb --from-date 2026-11-02 --to-date 2026-11-07
```

This creates one run per day from 2026-11-02 to 2026-11-06. Airflow only creates a run when
the whole day is inside the range, so `--to-date` itself is not processed.
Add `--reprocess-behavior completed` to run again days that already ran.

Check the result in the warehouse:

```bash
docker compose exec warehouse psql -U warehouse -d warehouse \
  -c "SELECT dt, count(*) FROM raw.transactions GROUP BY dt ORDER BY dt;"
```

### Tests and lint

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt
ruff check .
pytest
```

Tests marked `integration` use the warehouse from Docker Compose (schema `raw_test`, dropped
after each test). If the warehouse is not running, they are skipped. To run only unit tests:
`pytest -m "not integration"`.

## Technical decisions

- **ELT.** Raw data is saved first, as it came from the source. Transformation happens later in dbt.
- **Idempotency.** The day to process comes from the Airflow data interval, never from the clock.
  Each run writes to a fixed key (`dt=<day>/<series>.json`), so a re-run replaces the file.
  In raw, the loader runs `DELETE` of the partition and `INSERT` of the new rows in one
  database transaction. A re-run gives the same rows, never duplicates.
- **Row count check.** After each load, the number of rows in raw must match the bronze file.
  If not, the task fails and the Asset is not updated, so dbt does not run on bad data.
- **Raw as text.** The raw layer does not convert types, so a bad value never breaks the load.
  Cleaning and typing are the job of the silver layer (dbt).
- **Deterministic generator.** The random seed is the processing date (`20261105`), so the
  same day always produces the same transactions. A golden test checks that the output is
  identical on every machine (laptop, Airflow container, CI).
- **Empty days.** On weekends and holidays (for example 2026-11-02) the API returns HTTP 404. The client treats this as
  "no data" and writes an empty list, so we can see the day was processed.
- **Failure handling.** HTTP timeouts, retries with exponential backoff on network errors,
  HTTP 429 and 5xx, response schema validation, and logs. Airflow also retries the task.
- **Testable code.** DAGs are thin. The logic lives in `src/` and is tested with pytest,
  with mocked HTTP and a fake S3.
- **No secrets in the repo.** All credentials come from `.env` (ignored by git).
- **MinIO image.** The official MinIO images are no longer published, so the project uses
  the Chainguard build, pinned by sha256 digest.

## Synthetic data notice

Customer and transaction data are **fictional**, generated with Faker.
No real personal data is used. BCB indicators are real public data.

## Roadmap

- **Phase 1 (done):** Docker Compose (Airflow, PostgreSQL, MinIO), BCB ingestion DAG, API client tests.
- **Phase 2:** synthetic transaction generator, bronze → raw load, dbt staging and star schema,
  data tests, pseudonymization of CPF and email (LGPD).
- **Phase 3:** GitHub Actions CI, optional Amazon S3 bronze, `dbt docs` catalog, diagram and screenshots.
- **Ideas:** SCD type 2 for customers, Spark, Databricks.

## Repository layout

```
airflow/dags/        Airflow DAGs
src/extract/         BCB API client and ingestion job
src/generate/        Synthetic customer and transaction generator
src/load/            Bronze writer (S3 / MinIO) and raw loader (PostgreSQL)
tests/               pytest
docker/airflow/      Airflow image
docker-compose.yml
```
