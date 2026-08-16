"""br-r37-c1-ilj40 — weighted degree with non-finite sums.

`dict(G.degree(weight=...))` USED TO return NaN where networkx returns an
infinity, on all four classes: Neumaier compensation applied to a non-finite
running sum makes ``(0 - inf) + inf = nan``, and the result ``inf + nan = nan``.
The shim described the accumulator as "Neumaier-compensated in Rust,
bit-identical to nx" — it was bit-identical only while the sum stayed finite.

THE OVERFLOW CASE WAS THE SERIOUS ONE. ``1e308 + 1e308`` is ordinary FINITE
input; networkx overflows it to ``inf`` and fnx returned ``nan``, so a graph of
large finite weights silently produced a wrong number. The infinity cases need
someone to have written an infinity deliberately; that one does not.

The SCALAR path was always correct, which is what localised the defect to the
bulk accumulator.

STATUS: FIXED. The guard landed in Rust and reached the shipped extension; this
file's residue pins fired on the first rebuild, which is what they were written
to do, and have been flipped to ordinary parity assertions. All twelve shapes now
agree on all four classes.

The file still does NOT hardcode which node carries a divergence, because the
draft that did got it wrong: for ``inf_plus_neg_inf`` the obvious node agrees and
a different one diverges. It also keeps bulk and scalar compared against each
other — while the bug was live those two disagreed, and that is what localised it.
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

# br-r37-c1-ilj40 IS FIXED. These four were the residue; they now agree with
# networkx on every class, so they live here as ordinary parity cases. They are
# kept as a named group rather than merged away because they are the shapes the
# guard exists for, and a regression in the non-finite guard would show up here
# first.
FORMERLY_BROKEN_SHAPES = {
    "single_inf": [("a", "b", INF)],
    "single_neg_inf": [("a", "b", -INF)],
    "overflow_to_inf": [("a", "b", 1e308), ("a", "c", 1e308)],
    "inf_plus_neg_inf": [("a", "b", INF), ("a", "c", -INF)],
}
AGREEING_SHAPES.update(FORMERLY_BROKEN_SHAPES)


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
def test_bulk_weighted_degree_matches_networkx(cls_name, shape):
    """All twelve shapes, including the four the guard was written for.

    The eight that always agreed are the regression half: whatever is done to
    the compensation must not disturb them.
    """
    edges = AGREEING_SHAPES[shape]
    want = dict(_build(nx, cls_name, edges).degree(weight="weight"))
    got = dict(_build(fnx, cls_name, edges).degree(weight="weight"))
    assert sorted(got) == sorted(want)
    for node in want:
        assert _same(got[node], want[node]), (cls_name, shape, node)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("shape", sorted(FORMERLY_BROKEN_SHAPES))
def test_scalar_and_bulk_agree_on_the_non_finite_shapes(cls_name, shape):
    """br-r37-c1-ilj40 fixed the BULK path; the scalar path was always right.

    Both must now agree with networkx AND with each other. While the bug was
    live these two disagreed, which is what localised it, so keeping them
    compared is the cheapest guard against the guard being dropped again.
    """
    edges = FORMERLY_BROKEN_SHAPES[shape]
    gnx = _build(nx, cls_name, edges)
    gfx = _build(fnx, cls_name, edges)
    bulk = dict(gfx.degree(weight="weight"))
    want = dict(gnx.degree(weight="weight"))
    for node in want:
        assert _same(bulk[node], want[node]), (cls_name, shape, node, "bulk")
        assert _same(
            gfx.degree(node, weight="weight"), gnx.degree(node, weight="weight")
        ), (cls_name, shape, node, "scalar")
        assert _same(bulk[node], gfx.degree(node, weight="weight")), (
            cls_name, shape, node, "bulk vs scalar",
        )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_size_weight_matches_networkx_on_an_overflowing_sum(cls_name):
    """size(weight) sums the same accumulator, so it inherited the same fix."""
    edges = FORMERLY_BROKEN_SHAPES["overflow_to_inf"]
    want = _build(nx, cls_name, edges).size(weight="weight")
    got = _build(fnx, cls_name, edges).size(weight="weight")
    assert _same(got, want), cls_name


def test_the_pin_is_not_vacuous():
    """A pin over an empty shape table would pass for the wrong reason."""
    assert len(FORMERLY_BROKEN_SHAPES) == 4
    assert len(AGREEING_SHAPES) >= 12
    assert set(FORMERLY_BROKEN_SHAPES).issubset(AGREEING_SHAPES)
