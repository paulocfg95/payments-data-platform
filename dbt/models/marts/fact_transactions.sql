-- Gold: transaction fact. Grain: one row per transaction.
--
-- Incremental: each run only processes transactions loaded into raw after
-- the last run (loaded_at). When Airflow re-runs a day, those rows get a new
-- loaded_at, so they are processed again and replaced (unique_key).
-- Dimension joins are LEFT JOINs: a missing dimension row gives a null key,
-- which the not_null and relationships tests catch, instead of losing rows.

{{
    config(
        materialized='incremental',
        unique_key='transaction_id',
        incremental_strategy='delete+insert'
    )
}}

with transactions as (

    select *
    from {{ ref('stg_transactions') }}
    {% if is_incremental() %}
    where loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{ this }})
    {% endif %}

)

select
    t.transaction_id,
    c.customer_sk,
    to_char(t.transaction_date, 'YYYYMMDD')::int as date_sk,
    p.payment_type_sk,
    ch.channel_sk,
    t.transaction_at,
    t.amount,
    t.fee,
    t.status,
    t.status = 'approved' as is_approved,
    t.loaded_at
from transactions as t
left join {{ ref('dim_customer') }} as c
    on t.customer_hash = c.customer_hash
left join {{ ref('dim_payment_type') }} as p
    on t.payment_type = p.payment_type
left join {{ ref('dim_channel') }} as ch
    on t.channel = ch.channel
