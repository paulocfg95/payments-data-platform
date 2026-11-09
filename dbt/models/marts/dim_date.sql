-- Gold: calendar dimension, one row per day from 2024 to 2027.
-- date_sk is the date as an integer (YYYYMMDD), a common choice for date keys.

with days as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2024-01-01' as date)",
        end_date="cast('2028-01-01' as date)"
    ) }}

)

select
    to_char(date_day, 'YYYYMMDD')::int as date_sk,
    date_day::date as date,
    extract(day from date_day)::int as day,
    extract(month from date_day)::int as month,
    extract(year from date_day)::int as year,
    extract(quarter from date_day)::int as quarter,
    extract(isodow from date_day)::int as day_of_week,
    trim(to_char(date_day, 'Day')) as day_name,
    extract(isodow from date_day) in (6, 7) as is_weekend
from days
