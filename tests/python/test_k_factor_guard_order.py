"""br-r37-c1-jocy2: regression tests for k_factor guard ordering.

nx applies @not_implemented_for("directed", "multigraph") decorators
which fire BEFORE the function body. Previously fnx's k=0 short-circuit
returned an empty Graph on directed / multigraph input.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    "cls",
    [fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph],
)
@pytest.mark.parametrize("k", [0, 1, 2])
def test_wrong_type_raises_regardless_of_k(cls, k):
    g = cls()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.k_factor(g, k)


def test_simple_undirected_k0_returns_empty_subgraph():
    g = fnx.path_graph(3)
    h = fnx.k_factor(g, 0)
    assert set(h.nodes()) == {0, 1, 2}
    assert h.number_of_edges() == 0


def test_simple_undirected_negative_k_raises():
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NetworkXError, match="non-negative"):
        fnx.k_factor(g, -1)


def test_simple_undirected_k1_perfect_matching():
    g = fnx.complete_graph(4)
    h = fnx.k_factor(g, 1)
    # k=1 factor is a perfect matching — every node has degree 1
    assert all(d == 1 for _, d in h.degree())


def test_k_factor_regular_graphs_matches_nx():
    import networkx as nx

    for seed in [0, 2, 5, 8, 10]:
        g_nx = nx.random_regular_graph(4, 10, seed=seed)
        g_fnx = fnx.random_regular_graph(4, 10, seed=seed)
        kf_nx = nx.k_factor(g_nx, 2)
        kf_fnx = fnx.k_factor(g_fnx, 2)
        assert all(d == 2 for _, d in kf_fnx.degree())
        assert kf_fnx.number_of_nodes() == 10
        assert kf_fnx.number_of_edges() == 10
