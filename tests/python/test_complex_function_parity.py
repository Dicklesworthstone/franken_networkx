"""Parity for complex / less-common functions.

Iterative (simrank), spectral (communicability, subgraph_centrality_exp),
all-pairs (all_pairs_node_connectivity, average_node_connectivity), and
structure-partitioning (voronoi_cells) functions are individually complex and
less exercised than the headline metrics. This pins them against networkx.

No mocks: real fnx and real networkx on identically-built connected graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _norm(x, p=5):
    if isinstance(x, dict):
        return {k: _norm(v, p) for k, v in x.items()}
    if isinstance(x, float):
        return round(x, p)
    if isinstance(x, (list, tuple)):
        return type(x)(_norm(v, p) for v in x)
    return x


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(6, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(25))
def test_iterative_and_spectral(seed):
    fg, ng, n = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _norm(fnx.simrank_similarity(fg), 4) == _norm(nx.simrank_similarity(ng), 4)
    assert _norm(fnx.communicability(fg), 3) == _norm(nx.communicability(ng), 3)
    assert _norm(fnx.subgraph_centrality_exp(fg), 3) == _norm(
        nx.subgraph_centrality_exp(ng), 3
    )


@pytest.mark.parametrize("seed", range(25))
def test_all_pairs_and_partitioning(seed):
    fg, ng, n = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _norm(dict(fnx.all_pairs_node_connectivity(fg))) == _norm(
        dict(nx.all_pairs_node_connectivity(ng))
    )
    assert round(fnx.average_node_connectivity(fg), 5) == round(
        nx.average_node_connectivity(ng), 5
    )
    fv = {k: set(v) for k, v in fnx.voronoi_cells(fg, {0, n - 1}).items()}
    nv = {k: set(v) for k, v in nx.voronoi_cells(ng, {0, n - 1}).items()}
    assert fv == nv


@pytest.mark.parametrize("seed", range(25))
def test_reaching_and_percolation(seed):
    fg, ng, n = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert round(fnx.global_reaching_centrality(fg), 5) == round(
        nx.global_reaching_centrality(ng), 5
    )
    assert _norm(fnx.percolation_centrality(fg), 5) == _norm(
        nx.percolation_centrality(ng), 5
    )
