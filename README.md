# Fadr Stem Separation Benchmark

Evaluates Fadr's AI stem separator against the MUSDB18-HQ ground-truth dataset using BSS Eval metrics (SDR, SIR, SAR) via `mir_eval`.

## Results

Evaluated on 46 of 50 MUSDB18 test tracks (4 lost to transient Fadr API errors).  
Metric: **median** over 1-second non-overlapping windows, across all evaluated tracks.

| Stem    | SDR (dB) | SIR (dB) | SAR (dB) |
|---------|:--------:|:--------:|:--------:|
| Vocals  | 9.91     | 15.26    | 11.94    |
| Drums   | 11.15    | 18.52    | 12.23    |
| Bass    | 11.72    | 18.02    | 13.13    |
| Other   | 6.09     | 10.68    | 9.01     |
| **Avg** | **9.72** | **15.62**| **11.58**|

Higher is better. Full per-track results are in [`results/raw_metrics.csv`](results/raw_metrics.csv) and [`results/summary.json`](results/summary.json).

## Prerequisites

- Python 3.9+
- `ffmpeg` in PATH (required by `stempeg`)
- MUSDB18-HQ dataset (WAV version)
- A Fadr API key (Plus subscription required)
- AWS S3 bucket with IAM credentials (Fadr requires a URL for audio input)

## Setup

```sh
# 1. Clone and enter the repo
git clone <repo-url>
cd fadr_mir_eval_benchmark

# 2. Copy the env template and fill in your credentials
cp .env.example .env
#    FADR_API_KEY      — from fadr.com/dashboard → API tab
#    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / STORAGE_BUCKET — S3 bucket

# 3. Place the MUSDB18-HQ dataset
#    Download from: https://zenodo.org/records/3338373
#    Unpack so the structure is:
#      data/musdb18/test/<track name>/mixture.wav
#      data/musdb18/test/<track name>/vocals.wav
#      data/musdb18/test/<track name>/drums.wav
#      data/musdb18/test/<track name>/bass.wav
#      data/musdb18/test/<track name>/other.wav

# 4. Install dependencies
make setup
```

## Running the benchmark

```sh
# Full pipeline (data → separate → evaluate → report)
make all

# Or step by step:
make data        # build data/manifest.csv from MUSDB18-HQ
make separate    # upload each mixture to Fadr and download separated stems
make evaluate    # compute BSS Eval metrics (runs in parallel, ~8 min on 14 cores)
make report      # print summary tables and write results/summary.json
```

See all available targets:

```sh
make help
```

## Configuration

Edit [`config.yaml`](config.yaml) to change:

| Setting | Default | Description |
|---|---|---|
| `dataset.split` | `test` | `test` (50 tracks) or `train` (100 tracks) |
| `dataset.max_tracks` | `50` | Cap for faster dry-runs (e.g. `5`) |
| `separators.fadr.poll_interval_s` | `5` | Seconds between task status polls |
| `separators.fadr.timeout_s` | `600` | Max wait per track before marking failed |

## Project layout

```
├── config.yaml              # All tuneable settings
├── .env.example             # Credential placeholders (copy to .env)
├── Makefile                 # Pipeline entrypoints
├── requirements.txt
├── data/
│   ├── musdb18/             # MUSDB18-HQ WAV files (gitignored)
│   ├── manifest.csv         # Track → WAV path index (gitignored)
│   └── separated/fadr/      # Fadr output stems (gitignored)
├── src/
│   ├── data/dataset.py      # Walks MUSDB18-HQ, writes manifest.csv
│   ├── storage/uploader.py  # S3 presigned URL upload/download helpers
│   ├── separators/
│   │   ├── base.py          # Abstract StemSeparator interface
│   │   └── fadr.py          # Fadr REST client (upload → separate → download)
│   ├── evaluation/metrics.py # Windowed BSS eval via mir_eval
│   └── report/aggregate.py  # Median aggregation + markdown/JSON output
├── scripts/
│   ├── separate.py          # Runs separation; idempotent (skips completed tracks)
│   └── evaluate.py          # Parallel evaluation across tracks
└── results/
    ├── raw_metrics.csv      # Per-(track, stem) SDR/SIR/SAR rows
    └── summary.json         # Aggregated medians
```

## Evaluation methodology

- **Metric**: BSS Eval (`bss_eval_sources` from `mir_eval`)
- **Window**: 1-second non-overlapping windows (standard MUSDB18 protocol)
- **Aggregation**: median SDR/SIR/SAR per stem across all windows and tracks
- **Multi-source**: all 4 stems evaluated simultaneously per window, giving meaningful SIR values (interference from other estimated stems)
- **Silent windows** (reference energy < 1e-7) are skipped

## Cost

Fadr charges **$0.05 per minute of audio**. At ~3.5 min average track length:

- 50 tracks ≈ **$8.75** for a full test-set run
- Use `dataset.max_tracks: 5` in `config.yaml` for a ~$0.90 dry-run
