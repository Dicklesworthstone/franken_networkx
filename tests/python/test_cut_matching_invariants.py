"""Oracle-free cut / matching theorem-invariants.

* Whitney: ``node_connectivity <= edge_connectivity <= min_degree``
* ``stoer_wagner`` global min cut == ``edge_connectivity`` (unit weights)
* Gomory-Hu tree min-cut between s, t == ``minimum_cut_value(s, t)``
* Gallai: ``|max matching| + |min edge cover| == n`` (no isolated nodes)

br-r37-c1-4eodq
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected_unweighted(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    ng = nx.Graph(g.edges())
    ng.add_nodes_from(range(n))
    return g, ng, n


@pytest.mark.parametrize("seed", range(60))
def test_whitney_inequality_and_stoer_wagner(seed):
    g, ng, n = _connected_unweighted(seed)
    if not nx.is_connected(ng) or n < 2:
        pytest.skip("disconnected or trivial")
    kappa = fnx.node_connectivity(g)
    lam = fnx.edge_connectivity(g)
    min_deg = min(d for _, d in g.degree())
    assert kappa <= lam <= min_deg
    # Stoer-Wagner global min cut equals edge connectivity for unit weights.
    cut_value, _ = fnx.stoer_wagner(g)
    assert cut_value == lam
    assert cut_value == nx.stoer_wagner(ng)[0]


@pytest.mark.parametrize("seed", range(60))
def test_gallai_matching_plus_edge_cover(seed):
    g, ng, n = _connected_unweighted(seed)
    if not nx.is_connected(ng) or min((d for _, d in g.degree()), default=0) < 1:
        pytest.skip("isolated node or disconnected")
    matching = fnx.max_weight_matching(g, maxcardinality=True)
    edge_cover = fnx.min_edge_cover(g)
    # Gallai's theorem: maximum matching + minimum edge cover == |V|.
    assert len(matching) + len(edge_cover) == n


@pytest.mark.parametrize("seed", range(40))
def test_gomory_hu_tree_min_cuts(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.5:
                c = rng.randint(1, 9)
                fg.add_edge(u, v, capacity=c)
                ng.add_edge(u, v, capacity=c)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    tree = fnx.gomory_hu_tree(fg)
    for s in range(min(2, n)):
        for t in range(s + 1, n):
            path = nx.shortest_path(tree, s, t)
            tree_cut = min(tree[u][v]["weight"] for u, v in zip(path, path[1:]))
            assert tree_cut == fnx.minimum_cut_value(fg, s, t)


def test_gomory_hu_missing_capacity_raises_like_networkx():
    fg = fnx.Graph([(0, 1), (1, 2), (2, 0)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(nx.NetworkXUnbounded):
        fnx.gomory_hu_tree(fg)
    with pytest.raises(nx.NetworkXUnbounded):
        nx.gomory_hu_tree(ng)
