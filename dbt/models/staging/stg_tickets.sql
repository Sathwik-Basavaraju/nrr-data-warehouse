select
    ticket_id,
    account_id,
    month,
    cast(created_date as date) as created_date,
    category,
    priority,
    cast(resolution_days as integer) as resolution_days
from {{ source('saas', 'support_tickets') }}
