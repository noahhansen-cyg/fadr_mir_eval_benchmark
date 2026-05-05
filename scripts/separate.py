"""Run stem separation on all tracks in data/manifest.csv."""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.separators.fadr import FadrSeparator

SEPARATORS = {"fadr": FadrSeparator}
STEMS = ["vocals", "drums", "bass", "other"]


def _all_stems_present(output_dir: Path) -> bool:
    return all((output_dir / f"{s}.wav").exists() for s in STEMS)


def main():
    parser = argparse.ArgumentParser(description="Separate MUSDB18 tracks via API")
    parser.add_argument("--separator", default="fadr", choices=list(SEPARATORS.keys()))
    parser.add_argument("--manifest", default="data/manifest.csv")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        sys.exit(f"Manifest not found: {manifest_path}  (run `make data` first)")

    with open(manifest_path) as f:
        tracks = list(csv.DictReader(f))

    sep = SEPARATORS[args.separator]()

    log_path = Path("data/separation_log.csv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_exists = log_path.exists()

    with open(log_path, "a", newline="") as logf:
        log_writer = csv.DictWriter(
            logf, fieldnames=["separator", "track", "status", "error"]
        )
        if not log_exists:
            log_writer.writeheader()

        for i, row in enumerate(tracks, 1):
            track = row["track"]
            output_dir = Path("data/separated") / args.separator / track

            if _all_stems_present(output_dir):
                print(f"[{i}/{len(tracks)}] skip  {track}")
                continue

            print(f"[{i}/{len(tracks)}] {args.separator}  {track}")
            try:
                sep.separate(row["mixture"], str(output_dir))
                log_writer.writerow(
                    {"separator": args.separator, "track": track, "status": "ok", "error": ""}
                )
                print(f"  done → {output_dir}")
            except Exception as exc:
                log_writer.writerow(
                    {"separator": args.separator, "track": track, "status": "failed", "error": str(exc)}
                )
                print(f"  FAILED: {exc}")

            logf.flush()


if __name__ == "__main__":
    main()
