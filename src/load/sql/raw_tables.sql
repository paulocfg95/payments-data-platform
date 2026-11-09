-- Raw layer: a faithful copy of the bronze files.
-- Data columns are text on purpose. Types are set later, in dbt (ELT).
-- Every table has:
--   dt           the processing day (bronze partition)
--   source_file  the bronze object key the row came from
--   loaded_at    when the row was loaded
-- {schema} is replaced by the loader (raw, or a test schema).

CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {schema}.bcb_sgs (
    series_name     text not null,
    reference_date  text,
    value           text,
    dt              date not null,
    source_file     text not null,
    loaded_at       timestamptz not null default now()
);

CREATE TABLE IF NOT EXISTS {schema}.transactions (
    transaction_id  text,
    customer_cpf    text,
    transaction_at  text,
    payment_type    text,
    channel         text,
    amount          text,
    fee             text,
    status          text,
    dt              date not null,
    source_file     text not null,
    loaded_at       timestamptz not null default now()
);

CREATE TABLE IF NOT EXISTS {schema}.customers (
    cpf             text,
    name            text,
    email           text,
    state           text,
    city            text,
    created_at      text,
    segment         text,
    dt              date not null,
    source_file     text not null,
    loaded_at       timestamptz not null default now()
);

CREATE INDEX IF NOT EXISTS bcb_sgs_dt_idx ON {schema}.bcb_sgs (dt);
CREATE INDEX IF NOT EXISTS transactions_dt_idx ON {schema}.transactions (dt);
CREATE INDEX IF NOT EXISTS customers_dt_idx ON {schema}.customers (dt);
