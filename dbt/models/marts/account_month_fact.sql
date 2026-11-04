{{ config(
    materialized='incremental',
    unique_key='account_month_key',
    incremental_strategy='delete+insert'
) }}
-- Governed account-month fact. In dbt-duckdb this is incremental on
-- account_month_key; the DuckDB runner (src/run_duckdb.py) executes
-- the same logic as a table rebuild and documents that difference.
select
    b.account_id || '-' || b.month as account_month_key,
    b.account_id,
    b.month,
    b.month_date,
    b.seats,
    b.mrr,
    b.plan,
    coalesce(u.usage_events, 0) as usage_events,
    coalesce(t.tickets, 0) as tickets
from {{ ref('stg_billing') }} b
left join (
    select account_id, month, count(*) as usage_events
    from {{ ref('stg_usage') }}
    group by account_id, month
) u on u.account_id = b.account_id and u.month = b.month
left join (
    select account_id, month, count(*) as tickets
    from {{ ref('stg_tickets') }}
    group by account_id, month
) t on t.account_id = b.account_id and t.month = b.month
