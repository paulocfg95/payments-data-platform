-- Silver: latest snapshot of the customer registry, pseudonymized (LGPD).
-- CPF and email become salted hashes. The name is not selected on purpose
-- (data minimization): it does not move past the raw layer.

with latest_snapshot as (

    select *
    from {{ source('raw', 'customers') }}
    where dt = (select max(dt) from {{ source('raw', 'customers') }})

)

select
    {{ pseudonymize("regexp_replace(cpf, '[^0-9]', '', 'g')") }} as customer_hash,
    {{ pseudonymize("lower(trim(email))") }} as email_hash,
    upper(trim(state)) as state,
    trim(city) as city,
    created_at::timestamp as created_at,
    segment,
    dt as snapshot_date,
    loaded_at
from latest_snapshot
where cpf is not null
