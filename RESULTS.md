# Benchmark Results — Fadr Stem Separation

Evaluated on **46 of 50 MUSDB18 test tracks** (4 lost to transient Fadr API errors).  
4 stems per track: **vocals, drums, bass, other**.  
Metric: **median BSS Eval** over 1-second non-overlapping windows.

---

## What the metrics mean

Three numbers are reported for each stem:

| Metric | Full name | What it measures |
|---|---|---|
| **SDR** | Source-to-Distortion Ratio | Overall quality — how close the estimated stem is to the reference, accounting for all error sources. The headline number. |
| **SIR** | Source-to-Interference Ratio | How much of the *other* stems bleeds into this stem's output. High SIR = clean separation, little cross-contamination. |
| **SAR** | Source-to-Artifacts Ratio | How many processing artifacts (noise, reverb smear, digital glitches) the algorithm introduced. High SAR = clean output. |

All three are measured in **decibels (dB)**. Higher is always better. A rough interpretation guide:

| SDR range | Quality |
|---|---|
| > 12 dB | Excellent — stems are largely clean and usable |
| 8–12 dB | Good — minor audible artifacts or residual bleed |
| 4–8 dB | Fair — noticeable but workable degradation |
| < 4 dB | Poor — significant bleed or artifacts |
| < 0 dB | The estimate is worse than silence (the original signal was nearly absent or heavily contaminated) |

The relationship **SIR > SDR** tells you that bleed from other stems is *not* the main quality limiter — artifacts are. The gap `SIR − SDR` quantifies how much headroom there is before interference becomes the bottleneck.

---

## Summary results

| Stem    | SDR (dB) | SIR (dB) | SAR (dB) | SIR − SDR gap |
|---------|:--------:|:--------:|:--------:|:-------------:|
| Vocals  | 9.91     | 15.26    | 11.94    | +5.7          |
| Drums   | 11.15    | 18.52    | 12.23    | +7.4          |
| Bass    | 11.72    | 18.02    | 13.13    | +7.1          |
| Other   | 6.09     | 10.68    | 9.01     | +4.5          |
| **Avg** | **9.72** | **15.62**| **11.58**| **+6.2**      |

---

## Stem-by-stem breakdown

### Bass — 11.72 dB SDR (best)

Bass is Fadr's strongest stem. A median of 11.72 dB with a tight SIR − SDR gap of 7 dB means the separator is producing clean, well-isolated low-end with minimal bleed from kick drum or low-mid instruments. The SAR of 13.1 indicates the output is largely artifact-free.

The bass stem also has the widest dynamic range across tracks (min −8.78 dB, max +24.79 dB), which reflects how much the underlying recording affects separability — a prominently mixed bass with a clear spectral footprint is easy; a heavily layered arrangement is not.

### Drums — 11.15 dB SDR

Drums perform similarly to bass, which is expected — rhythm section stems share similar spectral and temporal characteristics that modern deep-learning separators handle well. The highest SIR of all four stems (18.52 dB) indicates very little bleed from pitched instruments into the drum bus.

One outlier: **Arise - Run Run Run** produced a negative drums SDR (−3.3 dB), suggesting an unusual arrangement where the drum content in the mixture was too sparse or spectrally ambiguous for reliable isolation.

### Vocals — 9.91 dB SDR

Vocals are the most studied stem in the separation literature. Fadr's 9.91 dB median is competitive with published open-source results — state-of-the-art models (Demucs v4, MDX-Net) score roughly 8–10 dB on this dataset, so Fadr sits at or above the open-source baseline.

The main outlier is **PR - Oh No** (−5.06 dB), indicating the vocal was heavily processed, doubled, or buried in a dense mix to the point where the separator could not locate it reliably.

### Other — 6.09 dB SDR (weakest)

The "other" stem is the hardest category in MUSDB18 by design — it is defined as *everything that is not vocals, drums, or bass*, which typically includes piano, guitar, strings, synths, and any additional layering. Because its spectral content overlaps heavily with vocals and bass, separators consistently underperform here relative to the three named stems.

A median of 6.09 dB is in the "fair" range. Five tracks produced negative SDR scores for this stem (notably **PR - Oh No** and **Punkdisco - Oral Hygiene**), indicating particularly dense or unconventional arrangements.

---

## Track-level spread

| | SDR |
|---|---|
| **5 best-performing tracks** (avg across stems) | BKS - Too Much (13.55), Speak Softly - Broken Man (13.32), Mu - Too Bright (13.28), Enda Reilly - Cur An Long Ag Seol (13.22), Speak Softly - Like Horses (12.87) |
| **5 worst-performing tracks** | PR - Oh No (−0.39), Carlos Gonzalez - A Place For Us (4.02), AM Contra - Heart Peripheral (4.17), Punkdisco - Oral Hygiene (4.19), Timboz - Pony (4.58) |

The best-performing tracks tend to have clear arrangement roles for each instrument and relatively sparse mixes. The worst-performing tracks are either heavily layered, have unconventional production styles, or contain instruments that blur stem category boundaries (e.g., bass guitar with significant upper-harmonic content).

**PR - Oh No** is the most significant outlier — it is the only track with a negative *average* SDR across stems (−0.39 dB), pulling down the vocals, bass, and other medians. This is likely a difficult production rather than a systematic Fadr failure.

---

## What limits quality

For all four stems, **SIR > SDR** by an average of 6 dB. This means:

- Bleed from other stems into each stem's output is **not the primary quality bottleneck**
- The main source of degradation is **processing artifacts** (SAR < SIR), introduced by the neural network during separation

In practical terms: the stems Fadr produces are well-separated but may have subtle audible smearing or tonal coloration introduced by the model. Improving SAR (reducing artifact energy) would have a larger impact on perceived quality than reducing SIR (reducing bleed).

---

## Data coverage

| | Count |
|---|---|
| Tracks evaluated | 46 |
| Tracks skipped (Fadr API 502 errors) | 3 (BKS - Too Much, Moosmusic - Big Dummy Shake, Timboz - Pony — `other` stem only), 1 (Secretariat - Borderline — all stems) |
| Total (track, stem) measurements | 193 |
| Evaluation window | 1 second, non-overlapping |
| Evaluation protocol | Standard MUSDB18 BSS Eval |
