-- Gold: daily BCB indicators, one column per series. Grain: one row per day
-- with at least one indicator (business days).
--
-- Incremental: finds the days with new data in silver and rebuilds those
-- days from all series, so a day is complete even when the series arrive
-- in different runs. On the first run, every day is built.

{{
    config(
        materialized='incremental',
        unique_key='date_sk',
        incremental_strategy='delete+insert'
    )
}}

with indicators as (

    select * from {{ ref('stg_bcb__indicators') }}

),

changed_days as (

    select distinct indicators.indicator_date
    from indicators
    {% if is_incremental() %}
        where indicators.loaded_at > (
            select coalesce(max(previous.loaded_at), '1900-01-01')
            from {{ this }} as previous
        )
    {% endif %}

)

select
    to_char(indicators.indicator_date, 'YYYYMMDD')::int as date_sk,
    max(indicators.value) filter (where indicators.series_name = 'selic') as selic_rate,
    max(indicators.value) filter (where indicators.series_name = 'cdi') as cdi_rate,
    max(indicators.value) filter (
        where indicators.series_name = 'usd_brl_ptax'
    ) as usd_brl_ptax,
    max(indicators.loaded_at) as loaded_at
from indicators
where indicators.indicator_date in (select changed_days.indicator_date from changed_days)
group by indicators.indicator_date
