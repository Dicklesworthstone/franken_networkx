"""Regression tests for exact native planarity and wrapper edge bounds.

``_raw_is_planar`` uses the same exact Left-Right algorithm as the public
wrapper. Necessary edge bounds can reject some non-planar graphs early;
passing a bound must never substitute for the full planarity decision.
"""

from __future__ import annotations

import franken_networkx as fnx
import pytest


# ---------------------------------------------------------------------------
# The raw entry point must reject non-planar graphs that pass Euler's bound.
# ---------------------------------------------------------------------------


def test_raw_is_planar_rejects_k33():
    """K3,3 (n=6, m=9) passes Euler's bound but is non-planar."""
    g = fnx.complete_bipartite_graph(3, 3)
    assert fnx._raw_is_planar(g) is False


def test_raw_is_planar_rejects_petersen():
    """Petersen (n=10, m=15) needs the full planarity test."""
    g = fnx.petersen_graph()
    assert fnx._raw_is_planar(g) is False


def test_raw_is_planar_rejects_heawood():
    """Heawood (n=14, m=21) needs the full planarity test."""
    g = fnx.heawood_graph()
    assert fnx._raw_is_planar(g) is False


def test_raw_is_planar_still_rejects_k5():
    """K5 (n=5, m=10) violates the monotone Euler bound 3n-6=9 < 10,
    so the raw kernel still rejects it."""
    g = fnx.complete_graph(5)
    assert fnx._raw_is_planar(g) is False


# ---------------------------------------------------------------------------
# Planar graphs must remain accepted.
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
# Public wrapper uses exact native planarity after its early rejection checks.
# ---------------------------------------------------------------------------


def test_public_is_planar_still_correct_on_petersen():
    g = fnx.petersen_graph()
    assert fnx.is_planar(g) is False


def test_public_is_planar_still_correct_on_k33():
    g = fnx.complete_bipartite_graph(3, 3)
    assert fnx.is_planar(g) is False


def test_public_is_planar_girth4_rejects_without_lr_fallback(monkeypatch):
    """Mycielski(4) is triangle-free, non-bipartite, and violates 2n-4."""
    g = fnx.mycielski_graph(4)

    def fail_full_planarity(_candidate):
        raise AssertionError("girth-4 edge bound should reject before any full planarity test")

    # is_planar runs the native Left-Right kernel (_fnx.is_planar_lr) and only
    # falls back to check_planarity on exception; patch BOTH so the test fails
    # loudly if the cheap girth-4 bound does not short-circuit first.
    monkeypatch.setattr(fnx, "check_planarity", fail_full_planarity)
    monkeypatch.setattr(fnx._fnx, "is_planar_lr", fail_full_planarity)

    assert g.number_of_nodes() == 11
    assert g.number_of_edges() == 20
    assert fnx.is_bipartite(g) is False
    assert fnx.is_planar(g) is False


@pytest.mark.parametrize("graph_factory", [fnx.petersen_graph, fnx.heawood_graph])
def test_public_is_planar_sparse_high_girth_graphs_still_use_lr(
    graph_factory, monkeypatch
):
    # br-r37-c1-vp8j0: is_planar decides graphs that pass the cheap Euler/girth
    # necessary-condition bounds with the native Left-Right planarity kernel
    # (_fnx.is_planar_lr, br-r37-c1-...zuxh1; 132159d3a replaced the old
    # fnx.check_planarity delegation). Petersen (n=10, m=15) and Heawood
    # (n=14, m=21) both satisfy m <= 3n-6 AND the girth-4 bound m <= 2n-4, so
    # the cheap bounds cannot rule them out — the full LR kernel MUST run to
    # return the correct False. Patch the LR kernel to prove it is the path
    # taken (the previous test patched fnx.check_planarity, which is now only
    # the exception fallback and is never reached).
    g = graph_factory()
    calls = []

    def fake_is_planar_lr(candidate):
        calls.append(candidate)
        return False

    monkeypatch.setattr(fnx._fnx, "is_planar_lr", fake_is_planar_lr)

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
