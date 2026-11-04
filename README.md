# Net Revenue Retention Data Warehouse

dbt + DuckDB + SQL + Python. Synthetic SaaS dataset (shared schema
with the companion repo `account-health-expansion` — see
DATA_SCHEMA.md; same generator, seed 42, same account IDs).

## What this is
A governed warehouse that models raw billing, usage and support data
into tested staging and mart layers, with an incremental
account-month fact table and NRR / GRR / logo churn defined ONCE in
`dbt/models/marts/retention_metrics.sql`.

## Data (sample, not production volume)
- Accounts: 600
- Billing rows: 10,888 (2024-01 to 2025-12)
- Usage events (sampled): 132,952
- Support tickets: 3,694
- Seed: 42. Usage is sampled at mean 12 events per account-month to
  keep the repo under 20 MB. This repo does NOT contain 7M usage
  events. The generator (`src/generate_data.py`) can scale locally
  with `--usage-mean` / `--accounts`; do not upload a >20 MB file.

MRR magnitudes are synthetic (seats × plan price-per-seat) and are
not a real company's revenue.

## How to run
```bash
pip install -r requirements.txt
python src/generate_data.py --out data
python src/run_duckdb.py      # staging -> fact -> retention mart + 14 tests
python src/benchmark.py       # 5 queries, raw vs mart, 7 runs each
python src/make_charts.py
```
dbt itself was not installed in the build environment, so the DuckDB
runner (`src/run_duckdb.py`) strips dbt Jinja (`config`, `source`,
`ref`) and executes the same SQL logic. The dbt project files are
provided for a real dbt-duckdb run; the runner's test output is
DuckDB test output, not faked dbt output. The account-month fact is
configured as incremental in dbt (`unique_key=account_month_key`,
`delete+insert`); the runner rebuilds it as a table and documents
that difference.

## Results — actually computed on this run (see outputs/metrics.json)
- Retention months computed: 23 (2024-02 to 2025-12)
- Mean monthly NRR: **0.9884**
- Mean monthly GRR: **0.9637**
- Mean monthly logo churn rate: **0.0209** (monthly, not annual)
- Latest month (2025-12): NRR **0.9991**, GRR **0.9725**, monthly logo churn **0.0181**
- Definition: NRR = (starting − churned − contraction + expansion) / starting;
  GRR = (starting − churned − contraction) / starting;
  logo churn = churned accounts / starting accounts, per month.

## Tests — actually run
- **14 / 14 DuckDB tests passed** (see outputs/tests.json and
  dbt/models/schema.yml for the list: uniqueness, not-null, seats > 0,
  MRR ≥ 0, foreign-key checks, fact row count = billing row count,
  NRR in [0,2], GRR and logo churn in [0,1]).

## Benchmark — actually run (see outputs/benchmark.json)
Latest run on this data size (in-memory DuckDB):
- Total median runtime, 5 queries, 7 runs each:
  raw tables **165.215 ms**, mart **109.783 ms**
- Speedup: **1.505×**, reduction **33.55%**
- All 5 queries returned identical results raw vs mart (verified
  after normalising integer/float count types).
- Per-query medians vary by machine and load — an earlier run on the
  same data gave 32.016 ms raw / 19.157 ms mart. Rerun
  `src/benchmark.py` to reproduce on your machine; do not compare
  these millisecond figures to a different dataset size. The mart
  helps most on the usage-aggregation query (Q3); small in-memory
  queries show little or no gain, which is expected at this scale.

## Files
- `dbt/` — dbt_project.yml, staging models, marts, schema.yml
- `src/` — generate_data.py, run_duckdb.py, benchmark.py, make_charts.py
- `data/` — accounts.csv, billing.csv, usage_events.csv, support_tickets.csv
- `outputs/` — retention_metrics.csv, account_month_fact.csv, tests.json,
  benchmark.json, metrics.json, retention_over_time.png, benchmark.png
- `DATA_SCHEMA.md` — shared schema with account-health-expansion
- `MANIFEST.txt` — files to upload (excludes __pycache__ and large raw files)
