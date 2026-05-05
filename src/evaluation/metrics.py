import warnings

import mir_eval
import numpy as np
import soundfile as sf

STEMS = ["vocals", "drums", "bass", "other"]

# Standard MUSDB18 evaluation protocol: 1-second non-overlapping windows
WINDOW_SAMPLES = 44100
HOP_SAMPLES = 44100
SILENCE_THRESHOLD = 1e-7  # skip windows where the reference is silent


def _load_mono(path: str) -> tuple:
    audio, sr = sf.read(path, always_2d=True)
    return audio.mean(axis=1), sr


def _trim_to_shortest(arrays: list) -> list:
    n = min(len(a) for a in arrays)
    return [a[:n] for a in arrays]


def evaluate_track(reference_paths: dict, estimated_paths: dict) -> dict:
    """
    Compute windowed BSS Eval metrics for all stems of one track simultaneously.

    Uses 1-second non-overlapping windows (standard MUSDB18 evaluation protocol).
    Evaluating all sources together gives meaningful SIR values.
    Returns median SDR/SIR/SAR across windows per stem.

    Args:
        reference_paths: {stem_name: path} for all reference stems
        estimated_paths: {stem_name: path} for estimated stems (may be a subset)

    Returns:
        {stem_name: {"sdr": float, "sir": float, "sar": float}}
    """
    available = [s for s in STEMS if s in estimated_paths]
    if not available:
        return {}

    refs, ests = [], []
    for stem in available:
        ref, _ = _load_mono(reference_paths[stem])
        est, _ = _load_mono(estimated_paths[stem])
        refs.append(ref)
        ests.append(est)

    refs = _trim_to_shortest(refs)
    ests = _trim_to_shortest(ests)
    n_samples = len(refs[0])

    window_sdrs = {s: [] for s in available}
    window_sirs = {s: [] for s in available}
    window_sars = {s: [] for s in available}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)

        for start in range(0, n_samples - WINDOW_SAMPLES + 1, HOP_SAMPLES):
            end = start + WINDOW_SAMPLES
            ref_win = np.stack([r[start:end] for r in refs])
            est_win = np.stack([e[start:end] for e in ests])

            if np.max(np.abs(ref_win)) < SILENCE_THRESHOLD:
                continue

            try:
                sdr, sir, sar, _ = mir_eval.separation.bss_eval_sources(
                    ref_win, est_win, compute_permutation=False
                )
            except Exception:
                continue

            for i, stem in enumerate(available):
                window_sdrs[stem].append(float(sdr[i]))
                window_sirs[stem].append(float(sir[i]))
                window_sars[stem].append(float(sar[i]))

    results = {}
    for stem in available:
        vals = window_sdrs[stem]
        if not vals:
            continue
        finite_sirs = [v for v in window_sirs[stem] if np.isfinite(v)]
        results[stem] = {
            "sdr": float(np.median(vals)),
            "sir": float(np.median(finite_sirs)) if finite_sirs else float("inf"),
            "sar": float(np.median(window_sars[stem])),
        }

    return results
