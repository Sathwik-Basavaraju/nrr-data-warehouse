"""Benchmark 5 queries: raw tables vs governed mart, 7 runs each.

Each query is run 7 times in DuckDB; median runtime (ms) is reported.
Results are compared for exact equality (sorted rows) between raw
and mart versions. Writes outputs/benchmark.json.
Run after src/run_duckdb.py (mart tables must exist in the same run:
this script rebuilds them by importing run_duckdb's logic via a
fresh DuckDB connection and re-executing the models).
Run from the project root: python src/benchmark.py
"""
import hashlib
import json
import statistics
import time
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT / "src"))
from run_duckdb import clean_sql, SOURCE_MAP  # noqa: E402

QUERIES = {
    "q1_mrr_by_month": (
        "SELECT month, sum(mrr) AS total_mrr FROM raw_billing GROUP BY month ORDER BY month",
        "SELECT month, sum(mrr) AS total_mrr FROM account_month_fact GROUP BY month ORDER BY month",
    ),
    "q2_mrr_by_plan_month": (
        "SELECT month, plan, sum(mrr) AS total_mrr FROM raw_billing GROUP BY month, plan ORDER BY month, plan",
        "SELECT month, plan, sum(mrr) AS total_mrr FROM account_month_fact GROUP BY month, plan ORDER BY month, plan",
    ),
    "q3_usage_by_month": (
        "SELECT strftime(event_date, '%Y-%m') AS month, count(*) AS events FROM raw_usage GROUP BY month ORDER BY month",
        "SELECT month, sum(usage_events) AS events FROM account_month_fact GROUP BY month ORDER BY month",
    ),
    "q4_tickets_by_month": (
        "SELECT month, count(*) AS tickets FROM raw_tickets GROUP BY month ORDER BY month",
        "SELECT month, sum(tickets) AS tickets FROM account_month_fact GROUP BY month ORDER BY month",
    ),
    "q5_top10_latest_month": (
        "SELECT account_id, mrr FROM raw_billing WHERE month = (SELECT max(month) FROM raw_billing) ORDER BY mrr DESC LIMIT 10",
        "SELECT account_id, mrr FROM account_month_fact WHERE month = (SELECT max(month) FROM account_month_fact) ORDER BY mrr DESC LIMIT 10",
    ),
}


def _hash(df):
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()


def main():
    con = duckdb.connect()
    for raw, csv in [("raw_accounts", "accounts.csv"), ("raw_billing", "billing.csv"),
                     ("raw_usage", "usage_events.csv"), ("raw_tickets", "support_tickets.csv")]:
        con.execute(f"CREATE TABLE {raw} AS SELECT * FROM read_csv_auto('{ROOT}/data/{csv}')")
    for name, path in [
        ("stg_accounts", "dbt/models/staging/stg_accounts.sql"),
        ("stg_billing", "dbt/models/staging/stg_billing.sql"),
        ("stg_usage", "dbt/models/staging/stg_usage.sql"),
        ("stg_tickets", "dbt/models/staging/stg_tickets.sql"),
        ("account_month_fact", "dbt/models/marts/account_month_fact.sql"),
    ]:
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {clean_sql((ROOT / path).read_text())}")

    # data sizes
    sizes = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
             for t in ["raw_accounts", "raw_billing", "raw_usage", "raw_tickets", "account_month_fact"]}
    results = {}
    for qname, (raw_sql, mart_sql) in QUERIES.items():
        raw_df = con.execute(raw_sql).fetchdf()
        mart_df = con.execute(mart_sql).fetchdf()
        # normalise column types for comparison (floats)
        for df in (raw_df, mart_df):
            for c in df.columns:
                if df[c].dtype.kind == "f":
                    df[c] = df[c].round(2)
                    # DuckDB SUM can return float for an integer count;
                    # normalise integral floats to int for exact comparison
                    if (df[c] % 1 == 0).all():
                        df[c] = df[c].astype("int64")
        identical = raw_df.reset_index(drop=True).equals(mart_df.reset_index(drop=True))
        def time_it(sql):
            times = []
            for _ in range(7):
                t0 = time.perf_counter()
                con.execute(sql).fetchall()
                times.append((time.perf_counter() - t0) * 1000)
            return times
        raw_times, mart_times = time_it(raw_sql), time_it(mart_sql)
        raw_med, mart_med = statistics.median(raw_times), statistics.median(mart_times)
        results[qname] = {
            "raw_median_ms": round(raw_med, 3), "mart_median_ms": round(mart_med, 3),
            "speedup_x": round(raw_med / mart_med, 3) if mart_med else None,
            "identical_results": bool(identical),
            "rows": int(len(raw_df)),
        }
        print(qname, results[qname])
        assert identical, f"Benchmark {qname} results differ raw vs mart"
    total_raw = round(sum(v["raw_median_ms"] for v in results.values()), 3)
    total_mart = round(sum(v["mart_median_ms"] for v in results.values()), 3)
    out = {"runs_per_query": 7, "data_rows": sizes, "queries": results,
           "total_raw_median_ms": total_raw, "total_mart_median_ms": total_mart,
           "total_speedup_x": round(total_raw / total_mart, 3) if total_mart else None,
           "speedup_pct": round((1 - total_mart / total_raw) * 100, 2) if total_raw else None}
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "benchmark.json").write_text(json.dumps(out, indent=2))
    print(out)
    return out


if __name__ == "__main__":
    main()
