select
    account_id,
    month,
    cast(month || '-01' as date) as month_date,
    cast(seats as integer) as seats,
    cast(mrr as double) as mrr,
    plan
from {{ source('saas', 'billing') }}
