-- NRR, GRR and logo churn, defined ONCE here (governed mart).
-- For month t (with previous month t-1):
--   starting_mrr = sum of MRR in t-1 for accounts active in t-1
--   churned_mrr  = t-1 MRR of accounts active in t-1 but not in t
--   expansion_mrr = sum of positive MRR changes for retained accounts
--   contraction_mrr = sum of MRR decreases (as positive amounts) for retained accounts
--   NRR = (starting - churned - contraction + expansion) / starting
--   GRR = (starting - churned - contraction) / starting
--   logo_churn = churned_accounts / starting_accounts
with prev as (
    select account_id, month, month_date, mrr from {{ ref('account_month_fact') }}
),
pairs as (
    select
        p.month_date as prev_month_date,
        (p.month_date + interval 1 month) as month_date,
        p.account_id,
        p.mrr as prev_mrr,
        c.mrr as curr_mrr
    from prev p
    left join prev c
      on c.account_id = p.account_id
     and c.month_date = p.month_date + interval 1 month
)
select
    strftime(month_date, '%Y-%m') as month,
    count(*) as starting_accounts,
    sum(prev_mrr) as starting_mrr,
    sum(case when curr_mrr is null then 1 else 0 end) as churned_accounts,
    sum(case when curr_mrr is null then prev_mrr else 0 end) as churned_mrr,
    sum(case when curr_mrr is not null and curr_mrr > prev_mrr then curr_mrr - prev_mrr else 0 end) as expansion_mrr,
    sum(case when curr_mrr is not null and curr_mrr < prev_mrr then prev_mrr - curr_mrr else 0 end) as contraction_mrr,
    (sum(prev_mrr) - sum(case when curr_mrr is null then prev_mrr else 0 end)
      - sum(case when curr_mrr is not null and curr_mrr < prev_mrr then prev_mrr - curr_mrr else 0 end)
      + sum(case when curr_mrr is not null and curr_mrr > prev_mrr then curr_mrr - prev_mrr else 0 end))
      / nullif(sum(prev_mrr), 0) as nrr,
    (sum(prev_mrr) - sum(case when curr_mrr is null then prev_mrr else 0 end)
      - sum(case when curr_mrr is not null and curr_mrr < prev_mrr then prev_mrr - curr_mrr else 0 end))
      / nullif(sum(prev_mrr), 0) as grr,
    sum(case when curr_mrr is null then 1 else 0 end)::double / nullif(count(*), 0) as logo_churn_rate
from pairs
where month_date in (select month_date from prev)
group by month_date
order by month_date
