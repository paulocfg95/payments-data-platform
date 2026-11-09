-- Gold: customer dimension (pseudonymized, no personal data in clear text).
-- The surrogate key is a hash of customer_hash, so it is stable between runs.

select
    {{ dbt_utils.generate_surrogate_key(['customer_hash']) }} as customer_sk,
    customer_hash,
    state,
    city,
    segment,
    created_at
from {{ ref('stg_customers') }}
