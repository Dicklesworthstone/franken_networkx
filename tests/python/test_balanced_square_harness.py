"""Regression lock for br-r37-c1-7x25w — the per-slot `gc.collect()` bias.

`scripts/balanced_square_ab.py` collected before EVERY timed slot. The collect
sat outside the timed region, so it was never charged directly; what it did was
walk every GC-tracked container in the process and leave the caches cold, so the
arm restarting with the larger tracked heap paid more to warm back up. That arm
is always fnx — an fnx Graph carries `node_py_attrs`, `edge_py_attrs`,
`edge_py_attrs_by_endpoint`, `adj_row_py`, the node-key map and the index
lookaside, where the networkx arm is plain dicts. Symmetric procedure,
asymmetric effect, in the direction that made fnx look slow.

MEASURED on the same ELF, same row, same round count, differing ONLY in whether
the collector runs per slot (`(u,v) in G.edges()`, N=2000/E=8000, reps=4000,
41 rounds, both admissible with clean nulls):

    per-slot collect   0.7741x  CI [0.7621, 0.7970]  nulls 1.0047/1.0012
    per-round collect  1.0577x  CI [1.0525, 1.0609]  nulls 1.0110/1.0018

A 1.37x bias that crosses 1.0 — it made a win read as a loss.

**The A/A null cannot catch this and that is the point.** Both halves of a
square are equally cold, so the null comes out at 1.0 and certifies a biased
ratio. These tests therefore assert the harness's STRUCTURE, because the
harness's own gate is blind to the defect by construction.
"""

from __future__ import annotations

import gc
import importlib.util
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "scripts" / "balanced_square_ab.py"


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("balanced_square_ab", HARNESS)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _count_collects(monkeypatch, harness, **kwargs):
    """Run one row with a counting `gc.collect` and return (calls, row)."""
    calls = []
    real_collect = gc.collect
    monkeypatch.setattr(
        harness.gc, "collect", lambda *a, **k: (calls.append(1), real_collect(*a, **k))[1]
    )
    row = harness.run_row("probe", lambda: None, lambda: None, **kwargs)
    return len(calls), row


def test_timed_slots_do_not_collect(monkeypatch, harness):
    """One collect per ROUND, not one per slot.

    The square has 8 slots, so a reintroduced per-slot collect shows up as 8x
    the call count — this is the exact defect, counted rather than argued.
    """
    rounds = 5
    calls, _row = _count_collects(monkeypatch, harness, rounds=rounds, warmup=0)
    assert calls == rounds, (
        f"expected one gc.collect() per round ({rounds}), got {calls}; "
        f"{len(harness.SQUARE)} slots per round means {rounds * len(harness.SQUARE)} "
        "is the per-slot defect"
    )


def test_the_defect_is_reproducible_on_demand(monkeypatch, harness):
    """`--gc-per-slot` restores the old behaviour so the bias can be bounded.

    It exists to reproduce a defect, not to measure with, and it must actually
    reproduce it — otherwise the comparison that quantifies the bias is not
    measuring what it claims.
    """
    rounds = 5
    calls, _row = _count_collects(
        monkeypatch, harness, rounds=rounds, warmup=0, gc_per_slot=True
    )
    assert calls == rounds + rounds * len(harness.SQUARE)


def test_time_slot_does_not_collect_by_default(harness):
    before = gc.get_count()
    del before
    calls = []
    real_collect = gc.collect
    harness.gc.collect = lambda *a, **k: (calls.append(1), real_collect(*a, **k))[1]
    try:
        harness.time_slot(lambda: None)
        assert calls == []
        harness.time_slot(lambda: None, collect_first=True)
        assert len(calls) == 1
    finally:
        harness.gc.collect = real_collect


def test_the_collector_is_off_inside_a_timed_slot(monkeypatch, harness):
    """No collection may land inside a timed region.

    Hoisting the collect out of the slot is only safe if the collector is also
    quiet across the square; otherwise a collection triggered by allocation
    lands in a random slot and the timing is worse than before.
    """
    seen = []
    monkeypatch.setattr(
        harness,
        "time_slot",
        lambda fn, **kwargs: (seen.append(gc.isenabled()), 1)[1],
    )
    harness.run_row("probe", lambda: None, lambda: None, rounds=3, warmup=0)
    assert seen and not any(seen), "gc was enabled during a timed slot"
    assert gc.isenabled(), "run_row must re-enable the collector when it finishes"


def test_calls_per_slot_puts_k_calls_inside_one_timed_slot(harness):
    """br-r37-c1-j3i9q: a timed slot may hold K calls, and defaults to one.

    The whole-algorithm workload has one call per unit of work, so at K=1 its
    A/A null compares the variance of ONE call against ONE call and 9 of 11 rows
    failed while reporting stable ratios. K is what makes the null resolvable —
    and the default must stay 1, so no row measured before this change silently
    means something else.
    """
    calls = []
    harness.time_slot(lambda: calls.append(1))
    assert len(calls) == 1, "default must be one call per slot"

    calls.clear()
    harness.time_slot(lambda: calls.append(1), calls=5)
    assert len(calls) == 5


def test_calls_per_slot_reaches_every_slot_of_the_square(monkeypatch, harness):
    """K applies to BOTH arms, or the ratio measures different amounts of work."""
    incumbent, candidate = [], []
    rounds, k = 3, 4
    harness.run_row(
        "probe",
        lambda: incumbent.append(1),
        lambda: candidate.append(1),
        rounds=rounds,
        warmup=0,
        calls_per_slot=k,
    )
    slots_per_arm = len(harness.SQUARE) // 2
    # The warm-up scales with the slot: each arm is warmed with as much work as
    # a timed slot holds, or ROUND_WARM_CALLS, whichever is more.
    warm = max(harness.ROUND_WARM_CALLS, k)
    expected = rounds * (warm + slots_per_arm * k)
    assert len(incumbent) == len(candidate) == expected


def test_each_round_warms_both_arms_before_timing(monkeypatch, harness):
    """A collect leaves the caches cold; both arms must reheat symmetrically.

    Without this the fixed harness reported first/second-half nulls of
    1.1783/1.3516 — the asymmetry the per-slot collect had been hiding by
    making every slot equally cold.
    """
    incumbent, candidate = [], []
    monkeypatch.setattr(harness, "time_slot", lambda fn, **kwargs: (fn(), 1)[1])
    rounds = 3
    harness.run_row(
        "probe",
        lambda: incumbent.append(1),
        lambda: candidate.append(1),
        rounds=rounds,
        warmup=0,
    )
    slots_per_arm = len(harness.SQUARE) // 2
    expected = rounds * (harness.ROUND_WARM_CALLS + slots_per_arm)
    assert len(incumbent) == len(candidate) == expected
    assert harness.ROUND_WARM_CALLS >= 1


def test_busy_smt_sibling_rejects_an_otherwise_admissible_square(monkeypatch, harness):
    """A clean A/A result is not bankable if its SMT sibling is saturated.

    The negative case has perfect nulls and a CI excluding 1. Removing the
    whole-run sibling verdict turns it into an incorrect ADMISSIBLE result.
    """
    monkeypatch.setattr(harness, "begin_sibling_watch", lambda: (46, 0, 0.0))
    monkeypatch.setattr(harness, "end_sibling_watch", lambda _watch: 100.0)
    monkeypatch.setattr(
        harness,
        "_time_square",
        lambda *_args, **_kwargs: ([10] * 4, [5] * 4, [], [], [14] * 4, [14] * 4),
    )

    row = harness.run_row("probe", lambda: None, lambda: None, rounds=3, warmup=0)

    assert row["ratio"] == pytest.approx(2.0)
    assert row["null_incumbent"] == pytest.approx(1.0)
    assert row["null_fnx"] == pytest.approx(1.0)
    assert row["sibling_busy_pct"] == pytest.approx(100.0)
    assert row["verdict"] == "SIBLING-CONTENDED"
