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
separate: setup  ## Run the Fadr separator on all tracks in the manifest
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

.PHONY: evaluate-fadr
evaluate-fadr: setup  ## Evaluate only Fadr outputs
	$(PYTHON) scripts/evaluate.py --separator fadr

# ── Helpers ───────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: clean
clean:  ## Remove results/ and separation logs (keeps separated audio)
	rm -rf results/
	rm -f data/separation_log.csv

.PHONY: clean-all
clean-all: clean  ## Remove everything including separated audio and venv
	rm -rf data/separated/ data/musdb18/mixtures/ data/musdb18/references/ data/manifest.csv
	rm -rf $(VENV)
