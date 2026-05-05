# Fadr vs Moises.ai Stem Separation Benchmark — Plan

## Overview

This project benchmarks the stem separation quality of Fadr and Moises.ai using the `mir_eval` Python package. Separated stems are evaluated against ground-truth isolated tracks from the MUSDB18 dataset using BSS Eval metrics (SDR, SIR, SAR). The result is a reproducible pipeline and a structured comparison report.

---

## Software Lifecycle Phases

### Phase 1 — Requirements & Scope

**Goal:** Define what is being measured and what "done" looks like.

#### Stems evaluated
Both APIs separate audio into four stems that align with MUSDB18 ground truth:

| MUSDB18 stem | Fadr output  | Moises output |
|---|---|---|
| `vocals`     | Vocals       | vocals        |
| `drums`      | Drums        | drums         |
| `bass`       | Bass         | bass          |
| `other`      | Melodies     | other         |

#### Primary metric
- **SDR** (Source-to-Distortion Ratio, dB) — overall quality, reported per stem and as a macro average across tracks.

#### Secondary metrics (reported, not the primary signal)
- **SIR** — bleed from other stems (interference)
- **SAR** — algorithmic artifacts

#### Track sample
- Use the MUSDB18 **test split** (50 tracks). Running all 50 gives statistical confidence without excessive API costs. A fast-path option is the first 10 tracks.

#### Out of scope
- Re-mixing or mastering evaluation
- Latency / throughput benchmarks
- Non-stem Fadr outputs (MIDI, chords, key/tempo)

---

### Phase 2 — Environment Setup

#### Repository layout

```
fadr_mir_eval_benchmark/
├── PLAN.md
├── README.md
├── requirements.txt
├── .env.example               # API key placeholders (never commit real keys)
├── config.yaml                # Run settings (track count, stem list, sample rate)
├── data/
│   ├── musdb18/               # Ground-truth STEMS files (gitignored)
│   └── separated/
│       ├── fadr/              # <track_name>/<stem>.wav
│       └── moises/
├── src/
│   ├── data/
│   │   └── dataset.py         # MUSDB18 loader via musdb + stempeg
│   ├── storage/
│   │   └── uploader.py        # Presigned URL helper (S3 or similar)
│   ├── separators/
│   │   ├── base.py            # Abstract StemSeparator interface
│   │   ├── fadr.py            # Fadr REST client
│   │   └── moises.py          # Moises REST client
│   ├── evaluation/
│   │   └── metrics.py         # mir_eval.separation wrapper
│   └── report/
│       └── aggregate.py       # Per-track and macro stats, CSV/JSON export
├── scripts/
│   ├── separate.py            # Run both separators on the test set
│   └── evaluate.py            # Compute metrics and write results
├── results/                   # Output CSVs and summary JSON (gitignored)
└── Makefile                   # Top-level CLI entrypoints
```

#### Python dependencies (`requirements.txt`)

```
mir_eval>=0.7
musdb>=0.4
stempeg>=0.2
librosa>=0.10
numpy
scipy
pandas
requests
boto3          # or google-cloud-storage, depending on chosen cloud bucket
python-dotenv
pyyaml
```

#### Setup steps
1. Create and activate a virtual environment.
2. `pip install -r requirements.txt`
3. Install `ffmpeg` (required by `stempeg` to decode STEMS files).
4. Copy `.env.example` → `.env` and fill in `FADR_API_KEY`, `MOISES_API_KEY`, and cloud storage credentials.
5. Obtain MUSDB18: request access on Zenodo (usually approved same day) and place the archive under `data/musdb18/`. Alternatively use **MUSDB18-HQ** (uncompressed WAV, no decoding step).

#### Makefile

A `Makefile` at the repo root exposes the full pipeline as simple `make` targets. All targets activate the virtual environment automatically so callers never need to think about it.

```makefile
VENV      := .venv
PYTHON    := $(VENV)/bin/python
PIP       := $(VENV)/bin/pip

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: $(VENV)/bin/activate  ## Create venv and install dependencies

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $@

# ── Pipeline ──────────────────────────────────────────────────────────────────

.PHONY: data
data: setup  ## Export MUSDB18 mixtures and reference stems to data/
	$(PYTHON) src/data/dataset.py

.PHONY: separate
separate: setup  ## Run both separators on the full track manifest
	$(PYTHON) scripts/separate.py

.PHONY: evaluate
evaluate: setup  ## Compute mir_eval metrics and write results/raw_metrics.csv
	$(PYTHON) scripts/evaluate.py

.PHONY: report
report: setup  ## Aggregate metrics and print the summary table
	$(PYTHON) -c "from src.report.aggregate import run; run()"

.PHONY: all
all: data separate evaluate report  ## Run the full benchmark end-to-end

# ── Partial runs ──────────────────────────────────────────────────────────────

.PHONY: separate-fadr
separate-fadr: setup  ## Run only the Fadr separator
	$(PYTHON) scripts/separate.py --separator fadr

.PHONY: separate-moises
separate-moises: setup  ## Run only the Moises separator
	$(PYTHON) scripts/separate.py --separator moises

.PHONY: evaluate-fadr
evaluate-fadr: setup  ## Evaluate only Fadr outputs
	$(PYTHON) scripts/evaluate.py --separator fadr

.PHONY: evaluate-moises
evaluate-moises: setup  ## Evaluate only Moises outputs
	$(PYTHON) scripts/evaluate.py --separator moises

# ── Helpers ───────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: clean
clean:  ## Remove results/ and separation logs (keeps separated audio)
	rm -rf results/
	rm -f data/separation_log.csv

.PHONY: clean-all
clean-all: clean  ## Remove everything including separated audio (re-separation required)
	rm -rf data/separated/ data/musdb18/mixtures/ data/musdb18/references/ data/manifest.csv
	rm -rf $(VENV)
```

**Common workflows:**

```sh
# First-time setup + full benchmark
make all

# Re-run only evaluation after changing metrics code
make evaluate report

# Benchmark just one separator
make separate-fadr evaluate-fadr report

# Wipe results and rerun from separated audio (no new API calls)
make clean evaluate report

# See all targets
make help
```

---

### Phase 3 — Data Preparation

**Goal:** Produce a canonical set of mixed audio files (inputs to the separators) and load the isolated stems (ground truth for evaluation).

#### Steps

1. **Load MUSDB18** via the `musdb` Python package, restricting to the test split.
2. **Export the mixture** (`track.audio`) as a WAV file per track into `data/musdb18/mixtures/`.
3. **Export the four reference stems** (`track.stems`) per track into `data/musdb18/references/<track_name>/`.
4. All audio is resampled to 44 100 Hz stereo (native MUSDB18 rate) to avoid any resampling artefact in evaluation.
5. Build a manifest CSV (`data/manifest.csv`) mapping each track name to its mixture path and four reference stem paths — this becomes the single source of truth for both separation and evaluation scripts.

---

### Phase 4 — API Integration

**Goal:** Implement thin, testable clients for each separator behind a shared interface.

#### Abstract interface (`src/separators/base.py`)

```python
class StemSeparator:
    def separate(self, mixture_path: str, output_dir: str) -> dict[str, str]:
        """
        Accepts a local path to a stereo mixture WAV.
        Returns a dict mapping stem name → local path of the separated WAV.
        e.g. {"vocals": "/data/separated/fadr/track01/vocals.wav", ...}
        """
        raise NotImplementedError
```

#### File hosting (`src/storage/uploader.py`)

Both APIs require a URL as input (no direct binary upload). The uploader:
- Takes a local file path.
- Uploads to a private S3 bucket (or GCS bucket).
- Returns a short-lived presigned GET URL.
- The same helper handles downloading result files from presigned URLs that the APIs return.

#### Fadr client (`src/separators/fadr.py`)

Fadr REST flow:
1. `POST /stem` with presigned upload URL → returns a `task_id`.
2. Poll `GET /stem/{task_id}` until `status == "done"`.
3. Download each stem WAV from the presigned download URLs in the response.
4. Save to `data/separated/fadr/<track_name>/<stem>.wav`.

Stems returned: `vocals`, `drums`, `bass`, `melodies` (mapped to `other`).

#### Moises client (`src/separators/moises.py`)

Moises REST flow (`https://api.music.ai/v1/`):
1. `GET /workflow` to confirm the 4-stem separation workflow ID.
2. `POST /job` with the workflow ID and the presigned input URL → returns a `job_id`.
3. Poll `GET /job/{job_id}` until `status == "succeeded"`.
4. Download each stem WAV from the result URLs.
5. Save to `data/separated/moises/<track_name>/<stem>.wav`.

#### Separation script (`scripts/separate.py`)

- Reads `data/manifest.csv`.
- For each track (skip if output already exists — idempotent).
- Calls both clients, saving outputs under `data/separated/`.
- Logs API errors without crashing the full run; marks failed tracks in a `separation_log.csv`.

---

### Phase 5 — Evaluation Pipeline

**Goal:** Compute BSS Eval metrics for every (separator, track, stem) combination.

#### mir_eval wrapper (`src/evaluation/metrics.py`)

```python
import mir_eval
import librosa

def evaluate_stem(reference_path: str, estimated_path: str) -> dict:
    ref, sr = librosa.load(reference_path, sr=None, mono=False)
    est, _  = librosa.load(estimated_path, sr=sr, mono=False)
    # mir_eval expects shape (n_sources, n_samples); wrap single stems in a 1-element array
    sdr, sir, sar, _ = mir_eval.separation.bss_eval_sources(
        ref[None, :], est[None, :]
    )
    return {"sdr": float(sdr[0]), "sir": float(sir[0]), "sar": float(sar[0])}
```

Key decisions:
- Use `bss_eval_sources` (not `bss_eval_images`) — source-level evaluation is the standard for this task.
- Evaluate in stereo: pass both channels as a 2-sample-wide source matrix only if the API preserves stereo; otherwise fall back to mono.
- Length mismatch: trim or zero-pad the estimate to match the reference before evaluation (APIs may add/remove a few frames).

#### Evaluation script (`scripts/evaluate.py`)

- Reads `data/manifest.csv` and the separation outputs.
- For each (separator, track, stem): call `evaluate_stem`, catch failures.
- Appends each row to `results/raw_metrics.csv` with columns:
  `separator, track, stem, sdr, sir, sar`
- After all rows are written, call the aggregation module.

---

### Phase 6 — Results Analysis & Reporting

**Goal:** Produce a human-readable comparison.

#### Aggregation (`src/report/aggregate.py`)

From `results/raw_metrics.csv`:
1. Compute **per-stem median SDR** across all tracks, per separator.
2. Compute **macro-average median SDR** (mean of the four per-stem medians), per separator.
3. Compute the same for SIR and SAR.
4. Write `results/summary.json` and print a markdown table.

#### Sample output table

```
| Separator | Vocals SDR | Drums SDR | Bass SDR | Other SDR | Avg SDR |
|-----------|-----------|-----------|----------|-----------|---------|
| Fadr      |      X.X  |      X.X  |     X.X  |      X.X  |    X.X  |
| Moises    |      X.X  |      X.X  |     X.X  |      X.X  |    X.X  |
```

(All values in dB; higher is better.)

#### Stretch goal
Generate per-track SDR box plots using `matplotlib` saved to `results/plots/` for a richer view of consistency across tracks.

---

### Phase 7 — Documentation

**Goal:** Make the project reproducible by anyone with API access.

- **README.md**: setup steps, environment variables required, how to run `separate.py` and `evaluate.py`, how to interpret results.
- **.env.example**: all required environment variable names with placeholder values.
- **config.yaml**: documented settings (track count, stem names, target sample rate, polling interval, timeout).
- Inline docstrings on all public functions in `src/`.

---

## Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| MUSDB18 access takes >1 day | Request access early; use the DagsHub mirror or MUSDB18-HQ as fallback |
| API rate limits / cost overruns | Process tracks one at a time; add configurable `max_tracks` cap |
| Stem name mismatch between APIs | Explicit mapping dict per client, normalized at save time |
| Audio length drift from API encoding | Trim/pad before evaluation; log and report the max drift |
| Cloud storage cost | Use a small private bucket; clean up after results are downloaded |

---

## Milestone Checklist

- [x] Phase 1: Scope locked (`config.yaml` + `.env.example` created) — API keys and MUSDB18 access still needed (see below)
- [x] Phase 2: Repo structure created, deps installable, `.env` configured
- [x] Phase 3: Manifest CSV generated — 50 MUSDB18-HQ tracks, paths to existing WAVs (no re-export needed)
- [x] Phase 4: Fadr client working end-to-end — 46/50 tracks separated (4 lost to transient API 502s)
- [x] Phase 5: Metrics computed — 193 rows in results/raw_metrics.csv (windowed BSS eval, 1s windows)
- [x] Phase 6: Summary table generated — results/summary.json + markdown tables via `make report`
- [x] Phase 7: README complete; repo reproducible from a clean checkout
