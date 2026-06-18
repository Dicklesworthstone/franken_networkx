"""Differential + metamorphic parity for matrix-exponential spectral metrics.

Covers ``communicability_exp`` (G[u][v] = (exp(A))_{uv}),
``subgraph_centrality`` (diagonal of exp(A)) and ``estrada_index``
(trace of exp(A) = sum of eigenvalue exponentials). None had a dedicated
test file.

Locks fnx to upstream networkx across random connected graphs, the
metamorphic trace identity ``estrada_index == sum(subgraph_centrality)``,
and an empty-graph golden. scipy/numpy is warmed first so cold-init
timing/precision noise never enters the comparison.

br-r37-c1-d1nzg
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.fixture(scope="module", autouse=True)
def _warm_scipy():
    # Trigger one expm so the first measured call isn't cold.
    fnx.subgraph_centrality(fnx.path_graph(3))
    nx.subgraph_centrality(nx.path_graph(3))


def _connected_pair(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    p_cur = p
    for _ in range(60):
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        if nx.is_connected(ng):
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


@pytest.mark.parametrize("seed", range(40))
def test_subgraph_centrality_and_estrada_match_networkx(seed):
    pair = _connected_pair(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    fsc = fnx.subgraph_centrality(fg)
    nsc = nx.subgraph_centrality(ng)
    assert set(fsc) == set(nsc)
    for k in nsc:
        assert fsc[k] == pytest.approx(nsc[k], rel=1e-6)
    assert fnx.estrada_index(fg) == pytest.approx(nx.estrada_index(ng), rel=1e-6)


@pytest.mark.parametrize("seed", range(40))
def test_communicability_exp_matches_networkx(seed):
    pair = _connected_pair(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    fc = fnx.communicability_exp(fg)
    nc = nx.communicability_exp(ng)
    for u in nc:
        for v in nc[u]:
            assert fc[u][v] == pytest.approx(nc[u][v], rel=1e-6)


@pytest.mark.parametrize("seed", range(40))
def test_estrada_equals_trace_of_subgraph_centrality(seed):
    # estrada_index = trace(exp(A)) = sum of the diagonal = sum of the
    # subgraph centralities. Holds regardless of the reference.
    pair = _connected_pair(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, _, _ = pair
    assert fnx.estrada_index(fg) == pytest.approx(
        sum(fnx.subgraph_centrality(fg).values()), rel=1e-9
    )


def test_empty_graph_golden():
    # No edges -> A = 0 -> exp(A) = I -> every subgraph centrality is 1 and
    # estrada_index == number of nodes.
    fg = fnx.empty_graph(4)
    ng = nx.empty_graph(4)
    for value in fnx.subgraph_centrality(fg).values():
        assert value == pytest.approx(1.0)
    assert fnx.estrada_index(fg) == pytest.approx(4.0)
    assert fnx.estrada_index(fg) == pytest.approx(nx.estrada_index(ng))
