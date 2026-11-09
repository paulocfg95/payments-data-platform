-- LGPD check: no column with plain personal data may exist after the raw layer.
-- Looks at every table in the silver (staging) and gold (marts) schemas and
-- returns the columns with a forbidden name.
-- The depends_on lines make dbt run this test after the last models are built.
-- depends_on: {{ ref('agg_daily_payments') }}
-- depends_on: {{ ref('fact_daily_indicators') }}
-- depends_on: {{ ref('stg_customers') }}

{{ config(severity = 'error') }}

select
    table_schema,
    table_name,
    column_name
from information_schema.columns
where table_schema in ('{{ generate_schema_name("staging", none) }}', '{{ generate_schema_name("marts", none) }}')
  and column_name in ('cpf', 'customer_cpf', 'email', 'name', 'customer_name')
