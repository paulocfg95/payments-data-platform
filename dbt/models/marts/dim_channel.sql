-- Gold: channel dimension, from the channels seed.

select
    {{ dbt_utils.generate_surrogate_key(['channel']) }} as channel_sk,
    channel,
    description
from {{ ref('channels') }}
