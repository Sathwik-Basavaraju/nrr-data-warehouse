"""Charts for the NRR warehouse: retention over time + benchmark."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main():
    df = pd.read_csv(ROOT / "outputs" / "retention_metrics.csv", parse_dates=["month"])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["month"], df["nrr"], marker="o", label="NRR")
    ax.plot(df["month"], df["grr"], marker="o", label="GRR")
    ax.set_ylabel("Rate"); ax.set_title("NRR / GRR by month (governed mart)")
    ax.legend(); fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(ROOT / "outputs" / "retention_over_time.png", dpi=150); plt.close(fig)

    b = json.loads((ROOT / "outputs" / "benchmark.json").read_text())
    qs = list(b["queries"].keys())
    raw = [b["queries"][q]["raw_median_ms"] for q in qs]
    mart = [b["queries"][q]["mart_median_ms"] for q in qs]
    fig, ax = plt.subplots(figsize=(10, 4))
    x = range(len(qs)); w = 0.35
    ax.bar([i - w/2 for i in x], raw, w, label="Raw tables")
    ax.bar([i + w/2 for i in x], mart, w, label="Mart")
    ax.set_xticks(list(x)); ax.set_xticklabels(qs, rotation=20, ha="right")
    ax.set_ylabel("Median ms (7 runs)"); ax.set_title("Benchmark: raw vs mart")
    ax.legend(); fig.tight_layout(); fig.savefig(ROOT / "outputs" / "benchmark.png", dpi=150)
    print("charts written")


if __name__ == "__main__":
    main()
