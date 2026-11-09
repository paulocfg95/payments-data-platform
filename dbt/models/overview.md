{% docs __overview__ %}

# payments-data-platform: data catalog

This is the data catalog of the **payments-data-platform** project, generated with `dbt docs`.
Source code: [github.com/paulocfg95/payments-data-platform](https://github.com/paulocfg95/payments-data-platform)

> **Synthetic data notice:** customers and transactions are **fake**, generated with Faker.
> No real personal data is used. Banco Central indicators are real public data.
> This catalog was built from a small sample (3 days) in CI.

## Layers

| Layer | Schema | What |
|---|---|---|
| raw | `raw` | Faithful copy of the bronze files (all columns `text`), loaded by Airflow |
| silver | `staging` | Clean, typed, deduplicated and pseudonymized (`stg_*` models) |
| gold | `marts` | Star schema ready for analysis |
| reference | `reference` | Small reference tables from dbt seeds |

## Star schema (gold)

- **`fact_transactions`**: one row per transaction. Keys to `dim_customer`, `dim_date`,
  `dim_payment_type` and `dim_channel`.
- **`fact_daily_indicators`**: one row per business day, with Selic, CDI and USD/BRL PTAX.
- **`agg_daily_payments`**: daily summary by payment type and channel, with the indicators of the day.

## LGPD

In the silver layer, CPF and email become salted SHA-256 hashes and the customer name is dropped.
The salt is never in the SQL code: it reaches PostgreSQL as a session setting. The test
`assert_no_personal_data_after_raw` fails if a column with personal data exists after raw.

## How to use this catalog

- Click a model on the left to see its description, columns, tests and SQL.
- Click the **lineage graph** button (bottom right) to see how data flows from `raw` to the gold tables.

{% enddocs %}
