"""br-r37-c1-ilj40 — weighted degree with non-finite sums.

`dict(G.degree(weight=...))` returns NaN where networkx returns an infinity, on
all four classes. The cause is Neumaier compensation applied to a non-finite
running sum: with a single infinite term the compensation is
``(0 - inf) + inf = nan`` and the result is ``inf + nan = nan``. The shim records
the accumulator as "Neumaier-compensated in Rust, bit-identical to nx" — it is
bit-identical only while the sum stays finite.

THE OVERFLOW CASE IS THE SERIOUS ONE. ``1e308 + 1e308`` is ordinary FINITE input.
networkx overflows it to ``inf``; fnx returns ``nan``. The infinity cases need
someone to have put an infinity in deliberately; this one does not.

The SCALAR path is correct — ``G.degree(n, weight=...)`` goes through the Python
helper and agrees with networkx — so a correct reference lives in the same file
as the broken bulk path.

WHAT THIS FILE DOES. The bug cannot be fixed here: the compensation is in Rust
and /data is at its 58G floor, so builds are frozen. Rather than leave the
finding as prose in a bead, this pins it as executable state — the eight shapes
that currently AGREE are asserted properly, so a fix cannot regress them, and the
four broken shapes are recorded so the pin FAILS when the bug is fixed and
someone must come back and flip it.

It also does NOT hardcode which node carries the residue, because my first draft
did and got it wrong: for ``inf_plus_neg_inf`` the obvious node agrees and a
different one diverges. Checking a single node is the same narrow mistake that
let this defect sit unnoticed.
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

INF = float("inf")
NAN = float("nan")

# shape name -> edges as (u, v, weight)
AGREEING_SHAPES = {
    "single_nan": [("a", "b", NAN)],
    "huge_finite_alone": [("a", "b", 1e308)],
    "tiny_plus_huge": [("a", "b", 1e-308), ("a", "c", 1e308)],
    "ten_ordinary": [("a", f"x{i}", 0.1) for i in range(10)],
    "mixed_int_float": [("a", "b", 1), ("a", "c", 0.5)],
    "negative": [("a", "b", -1), ("a", "c", -2.5)],
    "zeros": [("a", "b", 0), ("a", "c", 0)],
    "ints_only": [("a", "b", 1), ("a", "c", 2)],
}

# Shapes where at least one node's bulk weighted degree is NaN in fnx and an
# infinity in networkx. Keyed by shape only: WHICH node diverges is not fixed,
# and an earlier draft of this file got that wrong. For `inf_plus_neg_inf` node
# "a" agrees (NaN in both, because inf + -inf really is NaN) while node "b",
# whose only incident weight is the infinity, diverges. Checking one node would
# have classified that shape as healthy — which is exactly the narrow check this
# whole bead came from.
BROKEN_SHAPES = {
    "single_inf": [("a", "b", INF)],
    "single_neg_inf": [("a", "b", -INF)],
    "overflow_to_inf": [("a", "b", 1e308), ("a", "c", 1e308)],
    "inf_plus_neg_inf": [("a", "b", INF), ("a", "c", -INF)],
}


def _build(lib, cls_name, edges):
    graph = getattr(lib, cls_name)()
    for u, v, weight in edges:
        graph.add_edge(u, v, weight=weight)
    return graph


def _same(left, right):
    """NaN-aware equality, since NaN != NaN would make every row 'differ'."""
    if isinstance(left, float) and isinstance(right, float):
        if math.isnan(left) and math.isnan(right):
            return True
    return left == right


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("shape", sorted(AGREEING_SHAPES))
def test_bulk_weighted_degree_matches_networkx_where_it_currently_does(
    cls_name, shape
):
    """Every shape that agrees today, asserted properly.

    This is the half that guards the eventual fix: whatever is done to the
    compensation must not disturb these.
    """
    edges = AGREEING_SHAPES[shape]
    want = dict(_build(nx, cls_name, edges).degree(weight="weight"))
    got = dict(_build(fnx, cls_name, edges).degree(weight="weight"))
    assert sorted(got) == sorted(want)
    for node in want:
        assert _same(got[node], want[node]), (cls_name, shape, node)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("shape", sorted(BROKEN_SHAPES))
def test_scalar_weighted_degree_is_correct_even_where_bulk_is_not(cls_name, shape):
    """The scalar path is the working reference; it must stay working.

    If this ever starts failing too, the bug has spread from the bulk
    accumulator into the path a fix would otherwise be checked against.
    """
    edges = BROKEN_SHAPES[shape]
    gnx = _build(nx, cls_name, edges)
    gfx = _build(fnx, cls_name, edges)
    for node in gnx.nodes():
        assert _same(
            gfx.degree(node, weight="weight"), gnx.degree(node, weight="weight")
        ), (cls_name, shape, node)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("shape", sorted(BROKEN_SHAPES))
def test_the_nonfinite_bulk_residue_is_still_exactly_as_recorded(cls_name, shape):
    """br-r37-c1-ilj40, pinned as executable state rather than prose.

    Fails when the bug is FIXED, which is the point: replace this with
    ``assert _same(got, want)`` and delete BROKEN_SHAPES at that time.
    """
    edges = BROKEN_SHAPES[shape]
    want = dict(_build(nx, cls_name, edges).degree(weight="weight"))
    got = dict(_build(fnx, cls_name, edges).degree(weight="weight"))
    assert sorted(got) == sorted(want), "node sets must agree regardless"

    diverging = [n for n in want if not _same(got[n], want[n])]
    if not diverging:
        pytest.fail(
            f"br-r37-c1-ilj40 appears FIXED for {cls_name}/{shape}: bulk weighted "
            "degree now matches networkx everywhere. Move this shape into "
            "AGREEING_SHAPES and delete it from BROKEN_SHAPES."
        )
    # Characterise the residue rather than hardcoding which node it lands on:
    # every divergence must be fnx NaN against a networkx infinity. Anything
    # else is a DIFFERENT defect and should not pass quietly under this pin.
    for node in diverging:
        assert isinstance(got[node], float) and math.isnan(got[node]), (
            f"{cls_name}/{shape}/{node}: expected NaN residue, got {got[node]!r}"
        )
        assert isinstance(want[node], float) and math.isinf(want[node]), (
            f"{cls_name}/{shape}/{node}: networkx gave {want[node]!r}, not an "
            "infinity — the pin's premise is stale"
        )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_size_weight_shares_the_defect_and_is_pinned_with_it(cls_name):
    """size(weight) sums the same accumulator, so it inherits the same NaN."""
    edges = BROKEN_SHAPES["overflow_to_inf"]
    want = _build(nx, cls_name, edges).size(weight="weight")
    got = _build(fnx, cls_name, edges).size(weight="weight")
    if _same(got, want):
        pytest.fail(
            "br-r37-c1-ilj40 appears FIXED for size(weight); fold this into the "
            "agreeing assertions."
        )
    assert math.isnan(got), f"residue changed shape: {got!r}"


def test_the_pin_is_not_vacuous():
    """A pin over an empty shape table would pass for the wrong reason."""
    assert len(BROKEN_SHAPES) == 4
    assert len(AGREEING_SHAPES) >= 8
    assert set(BROKEN_SHAPES).isdisjoint(AGREEING_SHAPES)
