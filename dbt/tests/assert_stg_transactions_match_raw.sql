-- Row count check between raw and silver.
-- Silver must have exactly one row per distinct valid transaction in raw
-- (valid = has transaction_id, customer and amount). Returns a row on mismatch.

with raw_valid as (

    select count(distinct transaction_id) as row_count
    from {{ source('raw', 'transactions') }}
    where
        transaction_id is not null
        and customer_cpf is not null
        and amount is not null

),

silver as (

    select count(*) as row_count
    from {{ ref('stg_transactions') }}

)

select
    raw_valid.row_count as raw_row_count,
    silver.row_count as silver_row_count
from raw_valid
cross join silver
where raw_valid.row_count <> silver.row_count
