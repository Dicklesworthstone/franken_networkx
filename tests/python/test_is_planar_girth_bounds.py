"""Regression tests for the ``_raw_is_planar`` kernel's conservative
necessary-condition check.

History: a girth-based bound ``m <= g(n-2)/(g-2)`` was briefly added
(br-r37-c1-x0gc6) to reject K3,3 / Petersen / Heawood in the raw kernel,
then **removed in 5a23f997c** ("remove non-monotone girth/BCC checks for
edge-deletion safety"). The girth bound is unsound for any caller that
reasons about subgraphs: deleting an edge can *increase* the girth (e.g.
3→4), which tightens the girth bound, so a graph passing the bound can
have a subgraph that fails it — breaking the "if G passes, every subgraph
passes" monotonicity that edge-deletion planarity reasoning relies on.

So ``_raw_is_planar`` now applies only Euler's monotone bound
``m <= 3n-6``. This is a *conservative* necessary condition: it rejects
graphs that are definitely non-planar (K5: m=10 > 9) but ACCEPTS (returns
True for) graphs it cannot rule out, including K3,3 / Petersen / Heawood,
which all satisfy ``m <= 3n-6``. Full correctness is the public wrapper's
job — ``fnx.is_planar`` applies a bipartite/girth-4 edge bound and then
delegates to NetworkX's Left-Right planarity test (see the
``test_public_is_planar_*`` cases below).
"""

from __future__ import annotations

import franken_networkx as fnx
import pytest


# ---------------------------------------------------------------------------
# Raw kernel is conservative: it only enforces the monotone m <= 3n-6 bound,
# so non-planar graphs that satisfy that bound are NOT caught here (they are
# caught by the public wrapper). See 5a23f997c.
# ---------------------------------------------------------------------------


def test_raw_is_planar_does_not_reject_k33():
    """K3,3 (n=6, m=9) satisfies 3n-6=12, so the raw Euler bound cannot
    rule it out — the public wrapper rejects it instead."""
    g = fnx.complete_bipartite_graph(3, 3)
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_does_not_reject_petersen():
    """Petersen (n=10, m=15) satisfies 3n-6=24 — not caught by the raw
    Euler bound (the girth-based bound was removed in 5a23f997c)."""
    g = fnx.petersen_graph()
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_does_not_reject_heawood():
    """Heawood (n=14, m=21) satisfies 3n-6=36 — not caught by the raw
    Euler bound."""
    g = fnx.heawood_graph()
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_still_rejects_k5():
    """K5 (n=5, m=10) violates the monotone Euler bound 3n-6=9 < 10,
    so the raw kernel still rejects it."""
    g = fnx.complete_graph(5)
    assert fnx._raw_is_planar(g) is False


# ---------------------------------------------------------------------------
# Planar graphs must remain accepted (no false positives introduced)
# ---------------------------------------------------------------------------


def test_raw_is_planar_accepts_path():
    """Path graph is a tree (no cycles)."""
    g = fnx.path_graph(10)
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_accepts_cycle():
    g = fnx.cycle_graph(6)
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_accepts_complete_4():
    g = fnx.complete_graph(4)
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_accepts_star():
    g = fnx.star_graph(5)
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_accepts_5_cycle():
    """C5 has girth=5 but m=5 ≤ bound 5(n-2)/3=5 — must remain planar."""
    g = fnx.cycle_graph(5)
    assert fnx._raw_is_planar(g) is True


def test_raw_is_planar_accepts_cube():
    """3-cube (Q3): n=8, m=12, girth=4. Bound 2(n-2)=12 ≥ 12 → planar."""
    g = fnx.hypercube_graph(3)
    assert fnx._raw_is_planar(g) is True


# ---------------------------------------------------------------------------
# Public wrapper still delegates for full correctness
# ---------------------------------------------------------------------------


def test_public_is_planar_still_correct_on_petersen():
    """Public wrapper has always been correct (delegates to nx)."""
    g = fnx.petersen_graph()
    assert fnx.is_planar(g) is False


def test_public_is_planar_still_correct_on_k33():
    g = fnx.complete_bipartite_graph(3, 3)
    assert fnx.is_planar(g) is False


def test_public_is_planar_girth4_rejects_without_lr_fallback(monkeypatch):
    """Mycielski(4) is triangle-free, non-bipartite, and violates 2n-4."""
    g = fnx.mycielski_graph(4)

    def fail_check_planarity(_candidate):
        raise AssertionError("girth-4 edge bound should reject before LR fallback")

    monkeypatch.setattr(fnx, "check_planarity", fail_check_planarity)

    assert g.number_of_nodes() == 11
    assert g.number_of_edges() == 20
    assert fnx.is_bipartite(g) is False
    assert fnx.is_planar(g) is False


@pytest.mark.parametrize("graph_factory", [fnx.petersen_graph, fnx.heawood_graph])
def test_public_is_planar_sparse_high_girth_graphs_still_use_lr(
    graph_factory, monkeypatch
):
    g = graph_factory()
    calls = []

    def fake_check_planarity(candidate):
        calls.append(candidate)
        return False, None

    monkeypatch.setattr(fnx, "check_planarity", fake_check_planarity)

    assert fnx.is_planar(g) is False
    assert calls == [g]


def test_public_is_planar_preserves_directed_check_planarity_semantics():
    g = fnx.DiGraph()
    g.add_nodes_from(range(5))
    cycle_edges = [(node, (node + 1) % 5) for node in range(5)]
    g.add_edges_from(cycle_edges)
    g.add_edges_from((v, u) for u, v in cycle_edges)

    assert g.number_of_edges() > 3 * g.number_of_nodes() - 6
    assert fnx.check_planarity(g)[0] is True
    assert fnx.is_planar(g) is True


def test_public_is_planar_preserves_multigraph_check_planarity_semantics():
    g = fnx.MultiGraph()
    g.add_nodes_from(range(5))
    for _ in range(4):
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 3)

    assert g.number_of_edges() > 3 * g.number_of_nodes() - 6
    assert fnx.check_planarity(g)[0] is True
    assert fnx.is_planar(g) is True
