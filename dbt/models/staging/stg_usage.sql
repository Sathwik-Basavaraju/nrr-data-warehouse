select
    event_id,
    account_id,
    cast(event_date as date) as event_date,
    strftime(cast(event_date as date), '%Y-%m') as month,
    event_type,
    user_id,
    cast(duration_seconds as integer) as duration_seconds
from {{ source('saas', 'usage_events') }}
