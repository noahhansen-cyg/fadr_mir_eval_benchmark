"""Walk MUSDB18-HQ WAV files and write data/manifest.csv."""

import csv
from pathlib import Path

import yaml


def _load_config() -> dict:
    config_path = Path(__file__).parents[2] / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def export(config: dict = None) -> Path:
    cfg = config or _load_config()
    ds_cfg = cfg["dataset"]

    split_dir = Path(ds_cfg["path"]) / ds_cfg["split"]
    max_tracks = ds_cfg.get("max_tracks", 50)
    stems = cfg["stems"]

    track_dirs = sorted(p for p in split_dir.iterdir() if p.is_dir())[:max_tracks]

    manifest_path = Path("data/manifest.csv")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for track_dir in track_dirs:
        mixture = track_dir / "mixture.wav"
        stem_paths = {stem: track_dir / f"{stem}.wav" for stem in stems}

        missing = [str(p) for p in [mixture, *stem_paths.values()] if not p.exists()]
        if missing:
            print(f"WARNING: skipping {track_dir.name} — missing files: {missing}")
            continue

        rows.append({
            "track": track_dir.name,
            "mixture": str(mixture),
            **{stem: str(path) for stem, path in stem_paths.items()},
        })

    fieldnames = ["track", "mixture"] + stems
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Manifest written: {len(rows)} tracks → {manifest_path}")
    return manifest_path


if __name__ == "__main__":
    export()
