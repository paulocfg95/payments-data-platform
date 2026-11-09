-- Gold: daily BCB indicators, one column per series. Grain: one row per day
-- with at least one indicator (business days).
--
-- Incremental: finds the days with new data in silver and rebuilds those
-- days from all series, so a day is complete even when the series arrive
-- in different runs.

{{
    config(
        materialized='incremental',
        unique_key='date_sk',
        incremental_strategy='delete+insert'
    )
}}

with indicators as (

    select * from {{ ref('stg_bcb__indicators') }}

){% if is_incremental() %},

changed_days as (

    select distinct indicator_date
    from indicators
    where loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{ this }})

){% endif %}

select
    to_char(indicator_date, 'YYYYMMDD')::int as date_sk,
    max(value) filter (where series_name = 'selic') as selic_rate,
    max(value) filter (where series_name = 'cdi') as cdi_rate,
    max(value) filter (where series_name = 'usd_brl_ptax') as usd_brl_ptax,
    max(loaded_at) as loaded_at
from indicators
{% if is_incremental() %}
where indicator_date in (select indicator_date from changed_days)
{% endif %}
group by indicator_date
