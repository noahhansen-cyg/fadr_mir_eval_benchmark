"""Aggregate raw_metrics.csv into per-stem and macro summary tables."""

import json
from pathlib import Path

import pandas as pd

STEMS = ["vocals", "drums", "bass", "other"]
METRICS = ["sdr", "sir", "sar"]


def run(raw_path: str = "results/raw_metrics.csv") -> None:
    df = pd.read_csv(raw_path)

    # Drop rows that failed evaluation
    df = df[df["error"].isna() | (df["error"] == "")].copy()
    for m in METRICS:
        df[m] = pd.to_numeric(df[m], errors="coerce")
    df = df.dropna(subset=METRICS)

    if df.empty:
        print("No valid rows in raw_metrics.csv — nothing to report.")
        return

    # Per-stem median per separator
    per_stem = (
        df.groupby(["separator", "stem"])[METRICS]
        .median()
        .round(2)
    )

    # Macro average across stems
    macro = (
        per_stem.groupby("separator")[METRICS]
        .mean()
        .round(2)
        .rename(columns={m: f"avg_{m}" for m in METRICS})
    )

    # ── Print SDR table ───────────────────────────────────────────────────────
    print("\n=== Median SDR by stem (dB, higher is better) ===\n")
    sdr_pivot = per_stem["sdr"].unstack("stem").reindex(columns=STEMS)
    sdr_pivot["avg"] = macro["avg_sdr"]
    print(sdr_pivot.to_markdown())

    print("\n=== Median SIR by stem ===\n")
    print(per_stem["sir"].unstack("stem").reindex(columns=STEMS).to_markdown())

    print("\n=== Median SAR by stem ===\n")
    print(per_stem["sar"].unstack("stem").reindex(columns=STEMS).to_markdown())

    print("\n=== Macro averages ===\n")
    print(macro.to_markdown())

    # ── Save JSON ─────────────────────────────────────────────────────────────
    summary = {
        "per_stem_median": per_stem.reset_index().to_dict(orient="records"),
        "macro_mean_of_medians": macro.reset_index().to_dict(orient="records"),
    }
    summary_path = Path("results/summary.json")
    summary_path.parent.mkdir(exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved → {summary_path}")


if __name__ == "__main__":
    run()
