select
    account_id,
    company_name,
    industry,
    region,
    plan,
    cast(signup_date as date) as signup_date,
    cast(initial_seats as integer) as initial_seats
from {{ source('saas', 'accounts') }}
