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


@pytest.mark.parametrize("seed", range(25))
def test_simrank_call_forms(seed):
    """simrank has three distinct return shapes and the file uses only one.

    The bare call returns a nested dict; `source` returns one row; `source` and
    `target` together return a scalar. Those are separate code paths, and
    importance_factor changes the answer (verified: it differs from the default
    on this family, so a dropped argument would not hide behind parity).
    """
    fg, ng, n = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")

    damped = fnx.simrank_similarity(fg, importance_factor=0.5)
    assert _norm(damped, 4) == _norm(nx.simrank_similarity(ng, importance_factor=0.5), 4)
    assert _norm(damped, 4) != _norm(fnx.simrank_similarity(fg), 4)

    assert _norm(fnx.simrank_similarity(fg, source=0), 4) == _norm(
        nx.simrank_similarity(ng, source=0), 4
    )
    assert round(fnx.simrank_similarity(fg, source=0, target=1), 4) == round(
        nx.simrank_similarity(ng, source=0, target=1), 4
    )


@pytest.mark.parametrize("seed", range(25))
def test_all_pairs_node_connectivity_nbunch(seed):
    """`nbunch` restricts the pairs computed and was never passed."""
    fg, ng, n = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")

    restricted = _norm(dict(fnx.all_pairs_node_connectivity(fg, nbunch=[0, 1])))
    assert restricted == _norm(dict(nx.all_pairs_node_connectivity(ng, nbunch=[0, 1])))
    assert restricted != _norm(dict(fnx.all_pairs_node_connectivity(fg)))


def test_weight_and_normalized_parameters_reach_networkx_parity():
    """Two more unpassed parameters.

    Unlike the ones above I could NOT build an input where either changes the
    answer — networkx returns the same value with and without them on every
    witness I tried — so this asserts parity only and makes no claim that they
    alter the result.
    """
    fg, ng, n = _connected(0)
    assert round(fnx.global_reaching_centrality(fg, normalized=False), 5) == round(
        nx.global_reaching_centrality(ng, normalized=False), 5
    )

    wf, wn = fnx.Graph(), nx.Graph()
    for u, v, w in [(0, 1, 1), (1, 2, 10), (2, 3, 1), (3, 0, 1)]:
        wf.add_edge(u, v, weight=w)
        wn.add_edge(u, v, weight=w)
    assert {k: set(v) for k, v in fnx.voronoi_cells(wf, {0, 2}, weight="weight").items()} == {
        k: set(v) for k, v in nx.voronoi_cells(wn, {0, 2}, weight="weight").items()
    }


def test_voronoi_cells_reports_unreachable_nodes():
    """What the disconnected skip discards.

    voronoi_cells does not refuse a disconnected graph — it collects everything
    it cannot reach under an "unreachable" key, which is a return shape none of
    the connected draws can produce.
    """
    fg = fnx.Graph([(0, 1), (2, 3)])
    ng = nx.Graph([(0, 1), (2, 3)])

    cells = {k: set(v) for k, v in fnx.voronoi_cells(fg, {0}).items()}
    assert cells == {0: {0, 1}, "unreachable": {2, 3}}
    assert cells == {k: set(v) for k, v in nx.voronoi_cells(ng, {0}).items()}
