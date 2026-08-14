"""Regression coverage for the offline clause-3 gate replay."""

from __future__ import annotations

import importlib.util
import statistics
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


perf_harness = _load_module("fnx_perf_harness", REPO / "scripts" / "perf_harness.py")
rescore = _load_module("fnx_rescore_clause3", REPO / "scripts" / "rescore_clause3.py")


def _paired_result(label: str, samples: list[float]):
    median = statistics.median(samples)
    return perf_harness.PairedResult(
        label=label,
        ratio_p50=median,
        ratio_ci=perf_harness._median_ci(samples),
        p50_a=1.0,
        p50_b=1.0,
        cv_a=0.0,
        cv_b=0.0,
        mad_ratio=0.0,
        wins="0/0",
        rounds=len(samples),
        ratios=samples,
    )


def test_clause3_rescore_replays_the_production_bootstrap_and_current_verdict():
    """Archived rows must retain clauses 1/2 exactly while clause 3 varies."""
    production_reps, production_seed = perf_harness._median_ci.__defaults__
    assert (rescore.BOOT_REPS, rescore.BOOT_SEED) == (
        production_reps,
        production_seed,
    )

    candidate = [4.40, 4.41, 4.42] * 7
    null_nx = [0.986, 0.994, 1.002] * 7
    null_fnx = [0.992, 1.000, 1.008] * 7
    production = perf_harness.gate_decision(
        _paired_result("candidate", candidate),
        _paired_result("[A/A nx] candidate", null_nx),
        _paired_result("[A/A fnx] candidate", null_fnx),
    )
    replay = rescore.decide(
        {
            "ratio_samples": candidate,
            "null_nx_samples": null_nx,
            "null_fnx_samples": null_fnx,
        },
        "current",
    )

    assert replay["c1"] is production["ci_excludes_one"]
    assert replay["c2"] is production["clears_2x_half_width"]
    assert replay["c3"] is production["null_median_bias_bounded"]
    assert replay["decidable"] is production["decidable"]
