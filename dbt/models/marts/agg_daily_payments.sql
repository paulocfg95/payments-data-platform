-- Gold: daily payment summary, ready for dashboards.
-- Grain: one row per day, payment type and channel.
-- Joined with the BCB indicators of the same day (null on weekends and holidays).

with transactions as (

    select * from {{ ref('fact_transactions') }}

)

select
    t.date_sk,
    d.date,
    p.payment_type,
    ch.channel,
    count(*) as transaction_count,
    count(*) filter (where t.is_approved) as approved_count,
    round(avg(t.is_approved::int), 4) as approval_rate,
    coalesce(sum(t.amount) filter (where t.is_approved), 0) as approved_amount,
    coalesce(sum(t.fee) filter (where t.is_approved), 0) as fee_revenue,
    i.selic_rate,
    i.cdi_rate,
    i.usd_brl_ptax
from transactions as t
inner join {{ ref('dim_date') }} as d
    on t.date_sk = d.date_sk
inner join {{ ref('dim_payment_type') }} as p
    on t.payment_type_sk = p.payment_type_sk
inner join {{ ref('dim_channel') }} as ch
    on t.channel_sk = ch.channel_sk
left join {{ ref('fact_daily_indicators') }} as i
    on t.date_sk = i.date_sk
group by
    t.date_sk,
    d.date,
    p.payment_type,
    ch.channel,
    i.selic_rate,
    i.cdi_rate,
    i.usd_brl_ptax
