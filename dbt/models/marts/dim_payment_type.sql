-- Gold: payment type dimension, from the payment_types seed.

select
    {{ dbt_utils.generate_surrogate_key(['payment_type']) }} as payment_type_sk,
    payment_type,
    description
from {{ ref('payment_types') }}
