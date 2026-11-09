-- Silver: BCB indicators with proper types. One row per series per day.

with source as (

    select * from {{ source('raw', 'bcb_sgs') }}

),

typed as (

    select
        series_name,
        to_date(reference_date, 'DD/MM/YYYY') as indicator_date,
        value::numeric as value,
        loaded_at,
        row_number() over (
            partition by series_name, reference_date
            order by loaded_at desc
        ) as row_num
    from source

)

select
    series_name,
    indicator_date,
    value,
    loaded_at
from typed
where row_num = 1
