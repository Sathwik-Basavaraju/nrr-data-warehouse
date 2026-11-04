"""DuckDB runner for the dbt models (dbt is not installed here).

Loads data/*.csv into raw tables, strips dbt Jinja (config, source,
ref) from the model SQL, executes staging -> account_month_fact ->
retention_metrics, then runs the 14 tests listed in
dbt/models/schema.yml and writes outputs/retention_metrics.csv,
outputs/account_month_fact.csv and outputs/tests.json.

Run from the project root:
    python src/run_duckdb.py
Requires: duckdb, pandas
"""
import json
import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE_MAP = {"accounts": "raw_accounts", "billing": "raw_billing",
              "usage_events": "raw_usage", "support_tickets": "raw_tickets"}
REF_MAP = {"stg_accounts": "stg_accounts", "stg_billing": "stg_billing",
           "stg_usage": "stg_usage", "stg_tickets": "stg_tickets",
           "account_month_fact": "account_month_fact"}


def clean_sql(text):
    text = re.sub(r"\{\{\s*config\(.*?\)\s*\}\}", "", text, flags=re.S)
    text = re.sub(r"\{\{\s*source\('[^']+',\s*'([^']+)'\)\s*\}\}",
                  lambda m: SOURCE_MAP[m.group(1)], text)
    text = re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}",
                  lambda m: REF_MAP[m.group(1)], text)
    return text


def run():
    con = duckdb.connect()
    for raw, csv in [("raw_accounts", "accounts.csv"), ("raw_billing", "billing.csv"),
                     ("raw_usage", "usage_events.csv"), ("raw_tickets", "support_tickets.csv")]:
        con.execute(f"CREATE TABLE {raw} AS SELECT * FROM read_csv_auto('{ROOT}/data/{csv}')")
    order = [
        ("stg_accounts", "dbt/models/staging/stg_accounts.sql"),
        ("stg_billing", "dbt/models/staging/stg_billing.sql"),
        ("stg_usage", "dbt/models/staging/stg_usage.sql"),
        ("stg_tickets", "dbt/models/staging/stg_tickets.sql"),
        ("account_month_fact", "dbt/models/marts/account_month_fact.sql"),
        ("retention_metrics", "dbt/models/marts/retention_metrics.sql"),
    ]
    for name, path in order:
        sql = clean_sql((ROOT / path).read_text())
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {sql}")
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"{name}: {n} rows")
    (ROOT / "outputs").mkdir(exist_ok=True)
    con.execute("COPY (SELECT * FROM retention_metrics ORDER BY month) TO "
                f"'{ROOT}/outputs/retention_metrics.csv' (HEADER, DELIMITER ',')")
    con.execute("COPY (SELECT * FROM account_month_fact ORDER BY month, account_id) TO "
                f"'{ROOT}/outputs/account_month_fact.csv' (HEADER, DELIMITER ',')")

    tests = [
        ("stg_accounts account_id unique",
         "SELECT count(*) FROM (SELECT account_id, count(*) c FROM stg_accounts GROUP BY 1 HAVING c > 1)"),
        ("stg_billing account+month unique",
         "SELECT count(*) FROM (SELECT account_id, month, count(*) c FROM stg_billing GROUP BY 1,2 HAVING c > 1)"),
        ("account_month_fact key unique",
         "SELECT count(*) FROM (SELECT account_month_key, count(*) c FROM account_month_fact GROUP BY 1 HAVING c > 1)"),
        ("account_month_fact account_id not null",
         "SELECT count(*) FROM account_month_fact WHERE account_id IS NULL"),
        ("account_month_fact month not null",
         "SELECT count(*) FROM account_month_fact WHERE month IS NULL"),
        ("account_month_fact mrr not null",
         "SELECT count(*) FROM account_month_fact WHERE mrr IS NULL"),
        ("account_month_fact seats > 0",
         "SELECT count(*) FROM account_month_fact WHERE seats <= 0"),
        ("account_month_fact mrr >= 0",
         "SELECT count(*) FROM account_month_fact WHERE mrr < 0"),
        ("stg_usage account_id in accounts",
         "SELECT count(*) FROM stg_usage u LEFT JOIN stg_accounts a ON a.account_id=u.account_id WHERE a.account_id IS NULL"),
        ("stg_tickets account_id in accounts",
         "SELECT count(*) FROM stg_tickets t LEFT JOIN stg_accounts a ON a.account_id=t.account_id WHERE a.account_id IS NULL"),
        ("stg_billing account_id in accounts",
         "SELECT count(*) FROM stg_billing b LEFT JOIN stg_accounts a ON a.account_id=b.account_id WHERE a.account_id IS NULL"),
        ("fact row count = billing row count",
         "SELECT abs((SELECT count(*) FROM account_month_fact) - (SELECT count(*) FROM stg_billing))"),
        ("retention nrr in [0,2]",
         "SELECT count(*) FROM retention_metrics WHERE nrr < 0 OR nrr > 2"),
        ("retention grr in [0,1] and logo_churn in [0,1]",
         "SELECT count(*) FROM retention_metrics WHERE grr < 0 OR grr > 1 OR logo_churn_rate < 0 OR logo_churn_rate > 1"),
    ]
    results = []
    for name, sql in tests:
        failures = con.execute(sql).fetchone()[0]
        results.append({"test": name, "failures": int(failures), "passed": int(failures) == 0})
        print(f"test {name}: failures={failures}")
    passed = sum(r["passed"] for r in results)
    (ROOT / "outputs" / "tests.json").write_text(json.dumps(
        {"tests_run": len(results), "tests_passed": passed, "tests": results}, indent=2))
    print(f"tests: {passed}/{len(results)} passed")
    assert passed == len(results), "Some DuckDB tests failed"
    return results


if __name__ == "__main__":
    run()
