-- Silver: clean, typed and pseudonymized transactions.
-- 1. remove duplicated rows (same transaction_id)
-- 2. remove rows without customer or amount (cannot be analyzed)
-- 3. set types and replace the CPF with a salted hash (LGPD)

with source as (

    select * from {{ source('raw', 'transactions') }}

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by transaction_id
            order by loaded_at desc
        ) as row_num
    from source
    where transaction_id is not null

),

valid as (

    select *
    from deduplicated
    where
        row_num = 1
        and customer_cpf is not null
        and amount is not null

)

select
    transaction_id,
    {{ pseudonymize("regexp_replace(customer_cpf, '[^0-9]', '', 'g')") }} as customer_hash,
    transaction_at::timestamp as transaction_at,
    transaction_at::timestamp::date as transaction_date,
    payment_type,
    channel,
    amount::numeric(14, 2) as amount,
    fee::numeric(14, 2) as fee,
    status,
    dt,
    loaded_at
from valid
