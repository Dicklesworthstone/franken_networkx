"""br-r37-c1-x0gc6: regression tests for the is_planar girth-based
necessary-condition tightening.

Before the fix, ``_raw_is_planar`` only checked Euler's bound
``m <= 3n-6``, which K3,3 (n=6, m=9, bound 12) and Petersen (n=10,
m=15, bound 24) both pass, so both were misclassified as planar.

After the fix, the kernel additionally checks
``m <= g(n-2)/(g-2)`` where g is the girth:
- bipartite / triangle-free graphs (g=4): bound = 2(n-2)
- girth-5 graphs: bound = 5(n-2)/3
- girth-6 graphs: bound = 6(n-2)/4

This still does not constitute a full LR-planarity test; the public
wrapper continues to delegate to NetworkX for full correctness. But
the documented examples (K3,3, Petersen) and the Heawood graph
(another famous non-planar) are now correctly rejected by the raw
kernel itself.
"""

from __future__ import annotations

import franken_networkx as fnx
import pytest


# ---------------------------------------------------------------------------
# Newly-rejected non-planar graphs (regression target)
# ---------------------------------------------------------------------------


def test_raw_is_planar_rejects_k33():
    """K3,3 has n=6, m=9, girth=4. Bound 2(n-2)=8 < 9 → not planar."""
    g = fnx.complete_bipartite_graph(3, 3)
    assert fnx._raw_is_planar(g) is False


def test_raw_is_planar_rejects_petersen():
    """Petersen has n=10, m=15, girth=5. Bound 5(n-2)/3=13 < 15 → not planar."""
    g = fnx.petersen_graph()
    assert fnx._raw_is_planar(g) is False


def test_raw_is_planar_rejects_heawood():
    """Heawood graph (n=14, m=21, girth=6) is non-planar.
    Bound 6(n-2)/4=18 < 21 → not planar."""
    g = fnx.heawood_graph()
    assert fnx._raw_is_planar(g) is False


def test_raw_is_planar_still_rejects_k5():
    """K5 was already rejected by the 3n-6 bound; ensure the new
    girth check doesn't break that path."""
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
