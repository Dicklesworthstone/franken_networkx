"""Regression coverage for the offline clause-3 gate replay."""

from __future__ import annotations

import importlib.util
import statistics
import sys
from pathlib import Path

import pytest


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


def test_clause3_rescore_reports_the_required_win_lose_split():
    """Only rows vetoed solely by clause 3 may enter the publication table."""
    noisy_null_nx = [0.970] * 21
    neutral_null = [1.000] * 21
    rows = [
        {
            "label": "rescued win",
            "ratio_samples": [4.4] * 21,
            "null_nx_samples": noisy_null_nx,
            "null_fnx_samples": neutral_null,
        },
        {
            "label": "rescued loss",
            "ratio_samples": [0.6] * 21,
            "null_nx_samples": noisy_null_nx,
            "null_fnx_samples": neutral_null,
        },
        {
            "label": "already decidable",
            "ratio_samples": [1.2] * 21,
            "null_nx_samples": neutral_null,
            "null_fnx_samples": neutral_null,
        },
    ]

    table = rescore.rescore_rows(rows, "pooled")

    assert table["rows_rescored"] == 3
    assert table["previously_vetoed_now_decidable_count"] == 2
    assert table["previously_vetoed_now_decidable_wins"] == 1
    assert table["previously_vetoed_now_decidable_loses"] == 1
    assert [row["label"] for row in table["previously_vetoed_now_decidable"]] == [
        "rescued win",
        "rescued loss",
    ]


def test_clause3_rescore_rejects_a_capture_that_disagrees_with_current_gate():
    row = {
        "label": "tampered capture",
        "ratio_samples": [1.2] * 21,
        "null_nx_samples": [1.0] * 21,
        "null_fnx_samples": [1.0] * 21,
        "decision_gate": {"decidable": False},
    }

    with pytest.raises(ValueError, match="tampered capture"):
        rescore.rescore_rows([row], "pooled")


def test_claim_incumbent_single_source_shortest_path_has_complete_oracle(monkeypatch):
    """The published full-path claim must keep a paired, SHA-locked row."""
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("FNX_CLAIM_INCUMBENT_JOBS", "single_source_shortest_path")
    perf_harness.EXTRA_PROVENANCE.clear()

    rows = perf_harness.suite_claim_incumbent()

    assert len(rows) == 1
    label, nx_arm, fnx_arm = rows[0]
    assert label.startswith("claim/single_source_shortest_path ")
    assert nx_arm() == fnx_arm()
    fixture = perf_harness.EXTRA_PROVENANCE[
        "claim_single_source_shortest_path_fixture"
    ]
    assert fixture["output_items"] == 1_999
    assert fixture["complete_output_sha256"] == (
        "29f652f086c2aa346957d904b30b78ad41d55e2841f2e872125a94078f526d65"
    )


# br-r37-c1-d4xot: the `ci` variant is the offline analogue of the bead's
# "re-draw the null and take the median of medians" candidate. It is strictly
# more permissive than `current`, so the properties worth pinning are the ones
# that stop it becoming a blanket pass.
def _load_rescorer():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "rescore_clause3.py"
    spec = importlib.util.spec_from_file_location("rescore_under_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_variant_rejects_a_genuinely_biased_null():
    """A null that is tightly centred away from 1.0 must STILL be vetoed.

    This is the property that separates 'one noisy draw' from 'a biased
    measurement'. Clause 3 exists to catch the second, and a variant that
    stopped catching it would be the loosening the bead forbids.
    """
    mod = _load_rescorer()
    biased = [0.90 + 0.0001 * i for i in range(21)]  # tight, centred ~0.901
    assert mod._clause3("current", biased, biased, 4.4) is False
    assert mod._clause3("ci", biased, biased, 4.4) is False


def test_ci_variant_admits_a_noisy_null_centred_on_one():
    """A wide null whose spread reaches the band is draw noise, not bias."""
    mod = _load_rescorer()
    noisy = [1.0 + (0.06 if i % 2 else -0.05) for i in range(21)]
    assert mod._clause3("ci", noisy, noisy, 4.4) is True


def test_ci_is_never_stricter_than_current():
    """Pinned because the WIN/LOSE integrity table assumes this direction.

    If `ci` could veto a row `current` admits, 'newly undecidable' rows would
    appear and the table's reading would change.
    """
    mod = _load_rescorer()
    import random

    rng = random.Random(11)
    for _ in range(200):
        centre = rng.uniform(0.93, 1.07)
        spread = rng.uniform(0.0, 0.08)
        samples = [centre + rng.uniform(-spread, spread) for _ in range(21)]
        if mod._clause3("current", samples, samples, 3.0):
            assert mod._clause3("ci", samples, samples, 3.0), (
                "ci vetoed a row current admits"
            )


def test_ci_variant_is_reachable_from_the_cli(tmp_path):
    """Exercise the real CLI: an unknown --variant must be rejected, `ci` accepted.

    The first version of this test asserted that the string "ci" appeared in the
    source file, which would pass on any comment mentioning it. Running the
    parser is the only check that the choice is actually wired.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "rescore_clause3.py"
    rows = tmp_path / "rows.json"
    rows.write_text(json.dumps([]))

    accepted = subprocess.run(
        [sys.executable, str(script), str(rows), "--variant", "ci"],
        capture_output=True, text=True,
    )
    rejected = subprocess.run(
        [sys.executable, str(script), str(rows), "--variant", "not-a-variant"],
        capture_output=True, text=True,
    )
    # `ci` must get past argument parsing (it then fails on the empty capture,
    # which is the rescorer failing CLOSED and is the correct behaviour).
    assert "invalid choice" not in (accepted.stderr or "")
    assert "invalid choice" in (rejected.stderr or "")


# br-r37-c1-d4xot: PROPERTIES OF THE CANDIDATE VARIANTS, derived from constructed
# cases rather than from the suite. These are NOT the integrity table the bead
# demands - that needs an admitted run - but they are decidable now, and they say
# what to look for when the table finally exists.
def test_relative_variant_forgives_a_tightly_biased_null_when_the_effect_is_large():
    """The sharpest edge on `relative`, and the reason to read its table closely.

    A null centred at 0.91 with a spread of +/-0.001 over 21 samples is not draw
    noise - it is a measurement that is genuinely biased by 9 percent. `current`
    and `ci` both veto it. `relative` ADMITS it, because it forgives any bias
    smaller than the effect / RELATIVE_K, and the effect here is 4.4x.

    That is the inversion worth naming: `relative` is most forgiving exactly when
    the effect is largest, which is when an experimenter is most likely to accept
    a biased null as a result. It may still be the right trade, but the bead's
    WIN/LOSE table is what should decide it, not the size of the headline number.
    """
    mod = _load_rescorer()
    tight_biased = [0.91 + 0.0001 * (i % 3) for i in range(21)]
    clean = [1.0 + 0.0001 * (i % 3) for i in range(21)]
    assert mod._clause3("current", tight_biased, clean, 4.4) is False
    assert mod._clause3("ci", tight_biased, clean, 4.4) is False
    assert mod._clause3("relative", tight_biased, clean, 4.4) is True


def test_pooled_variant_can_mask_a_single_arm_bias():
    """`pooled` averages the arms, and this bead's failures are SINGLE-arm.

    The demonstration evidence reports run2 vetoed by the nx null (0.9772) and
    run7 by the fnx null (0.9574) - different arms on different runs. Pooling
    mixes a biased arm with a clean one, so a bias big enough to matter in one
    arm can land inside the bound once halved.
    """
    mod = _load_rescorer()
    biased = [0.962 + 0.0001 * (i % 3) for i in range(21)]
    clean = [1.0 + 0.0001 * (i % 3) for i in range(21)]
    assert mod._clause3("current", biased, clean, 4.4) is False
    assert mod._clause3("pooled", biased, clean, 4.4) is True


def test_every_variant_still_admits_a_clean_null():
    """None of the candidates may reject a null that is genuinely centred."""
    mod = _load_rescorer()
    clean = [1.0 + 0.0005 * (i % 5) for i in range(21)]
    for variant in ("current", "pooled", "relative", "ci"):
        assert mod._clause3(variant, clean, clean, 4.4) is True, variant


def test_rescorer_parses_a_realistic_stdout_capture(tmp_path):
    """End-to-end: the real capture will be a JSON line inside other output.

    Worth pinning because the one quiet window this bead is waiting for must not
    be spent discovering that the parser chokes on surrounding harness chatter.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "rescore_clause3.py"
    rows = [
        {
            "label": "synthetic",
            "ratio_samples": [4.4 + 0.001 * (i % 5) for i in range(21)],
            "null_nx_samples": [1.0 + 0.0005 * (i % 3) for i in range(21)],
            "null_fnx_samples": [1.0 - 0.0005 * (i % 3) for i in range(21)],
        }
    ]
    capture = tmp_path / "run.txt"
    capture.write_text(
        "perf_harness starting\nhost thinkstation1\n"
        f"benchmark_results_json={json.dumps(rows)}\ndone\n"
    )
    proc = subprocess.run(
        [sys.executable, str(script), str(capture), "--variant", "ci"],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert "1 of 1 rows carry raw samples" in proc.stdout
    assert "variant: ci" in proc.stdout
    assert "must be reverted" in proc.stdout  # the predicate reminder survives
