"""br-r37-c1-359bl: regression — fnx.waxman_graph(seed=N) must
produce the same edge set as nx.waxman_graph(seed=N).

Before this fix, fnx computed ``L = sqrt((x1-x0)^2 + (y1-y0)^2)``
(the domain diagonal) when ``L`` was unspecified. nx computes
``L = max(metric(x, y) for x, y in combinations(pos.values(), 2))``
— the actual maximum pair distance, which is always <= the domain
diagonal. The larger fnx L made the connection probability
``beta * exp(-d / (alpha * L))`` artificially higher, so fnx
produced extra edges (e.g. 3 edges vs nx's 1 on n=15, seed=42).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
@pytest.mark.parametrize("n", [10, 15, 25, 30])
@pytest.mark.parametrize("seed", [42, 100, 7, 999])
def test_waxman_graph_waxman1_edge_set_matches_nx(n, seed):
    """Waxman-1 (L=None): fnx must produce the same edge set as nx
    for the same seed and n."""
    fg = fnx.waxman_graph(n, seed=seed)
    ng = nx.waxman_graph(n, seed=seed)
    assert sorted(fg.edges()) == sorted(ng.edges()), (
        f"n={n} seed={seed}: fnx={fg.number_of_edges()}e nx={ng.number_of_edges()}e"
    )


@needs_nx
@pytest.mark.parametrize("seed", [42, 100, 7])
def test_waxman_graph_waxman2_edge_set_matches_nx(seed):
    """Waxman-2 (L specified): edge set must also match."""
    fg = fnx.waxman_graph(15, L=2.0, seed=seed)
    ng = nx.waxman_graph(15, L=2.0, seed=seed)
    assert sorted(fg.edges()) == sorted(ng.edges())


@needs_nx
def test_waxman_graph_positions_match_nx():
    """The node positions must be identical (node attrs use ``pos_name``)."""
    fg = fnx.waxman_graph(15, seed=42)
    ng = nx.waxman_graph(15, seed=42)
    for n in fg.nodes():
        assert fg.nodes[n]["pos"] == ng.nodes[n]["pos"]


@needs_nx
def test_waxman_graph_deterministic_across_calls():
    """Same seed should always give same result (within fnx)."""
    g1 = fnx.waxman_graph(15, seed=42)
    g2 = fnx.waxman_graph(15, seed=42)
    assert sorted(g1.edges()) == sorted(g2.edges())
