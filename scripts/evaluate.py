"""Compute mir_eval BSS Eval metrics for all separated stems."""

import argparse
import csv
import sys
import warnings
from multiprocessing import Pool, cpu_count
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.metrics import evaluate_track, STEMS

SEPARATORS = ["fadr"]


def _process_track(args) -> list:
    """Worker: evaluate one (separator, track) pair. Returns list of CSV row dicts."""
    sep_name, track, reference_paths, estimated_paths = args
    rows = []

    if not estimated_paths:
        return rows

    try:
        results = evaluate_track(reference_paths, estimated_paths)
        for stem, metrics in results.items():
            rows.append({
                "separator": sep_name,
                "track": track,
                "stem": stem,
                "error": "",
                **metrics,
            })
    except Exception as exc:
        for stem in estimated_paths:
            rows.append({
                "separator": sep_name,
                "track": track,
                "stem": stem,
                "sdr": "", "sir": "", "sar": "",
                "error": str(exc),
            })

    return rows


def main():
    parser = argparse.ArgumentParser(description="Evaluate separated stems via mir_eval")
    parser.add_argument("--separator", default=None, choices=SEPARATORS)
    parser.add_argument("--manifest", default="data/manifest.csv")
    parser.add_argument("--workers", type=int, default=max(1, cpu_count() - 2),
                        help="Parallel worker processes (default: n_cpus - 2)")
    args = parser.parse_args()

    separators = [args.separator] if args.separator else SEPARATORS

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        sys.exit(f"Manifest not found: {manifest_path}  (run `make data` first)")

    with open(manifest_path) as f:
        tracks = list(csv.DictReader(f))

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / "raw_metrics.csv"

    work_items = []
    for sep_name in separators:
        for row in tracks:
            track = row["track"]
            sep_dir = Path("data/separated") / sep_name / track
            reference_paths = {stem: row[stem] for stem in STEMS}
            estimated_paths = {
                stem: str(sep_dir / f"{stem}.wav")
                for stem in STEMS
                if (sep_dir / f"{stem}.wav").exists()
            }
            work_items.append((sep_name, track, reference_paths, estimated_paths))

    total = len(work_items)
    print(f"Evaluating {total} tracks with {args.workers} workers...")

    fieldnames = ["separator", "track", "stem", "sdr", "sir", "sar", "error"]
    completed = 0

    with open(out_path, "w", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()

        with Pool(processes=args.workers) as pool:
            for rows in pool.imap_unordered(_process_track, work_items):
                completed += 1
                if rows:
                    track = rows[0]["track"]
                    sep = rows[0]["separator"]
                    stem_summary = "  ".join(
                        f"{r['stem']} SDR={r['sdr']:+.1f}" if r["sdr"] != "" else f"{r['stem']} ERR"
                        for r in rows
                    )
                    print(f"[{completed}/{total}] {sep}/{track}\n  {stem_summary}")
                    writer.writerows(rows)
                else:
                    print(f"[{completed}/{total}] skip (no stems)")
                out_f.flush()

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
