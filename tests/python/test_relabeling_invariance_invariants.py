"""Oracle-free relabeling-invariance of order-invariant scalar metrics.

Renaming the nodes of a graph (to shuffled integers or to string labels)
must not change any metric that depends only on graph structure. This
directly guards against label-type / iteration-order dependence bugs — the
class that produced the spanning-tree str-node defect.

br-r37-c1-jeohx
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_METRICS = {
    "diameter": lambda g: fnx.diameter(g),
    "radius": lambda g: fnx.radius(g),
    "transitivity": lambda g: round(fnx.transitivity(g), 10),
    "triangles_sum": lambda g: sum(fnx.triangles(g).values()),
    "node_connectivity": lambda g: fnx.node_connectivity(g),
    "edge_connectivity": lambda g: fnx.edge_connectivity(g),
    "wiener_index": lambda g: fnx.wiener_index(g),
    "average_clustering": lambda g: round(fnx.average_clustering(g), 10),
    "n_spanning_trees": lambda g: round(fnx.number_of_spanning_trees(g), 4),
}


def _connected_graph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    ng = nx.Graph(list(g.edges()))
    ng.add_nodes_from(range(n))
    if not nx.is_connected(ng):
        return None
    return g, n


@pytest.mark.parametrize("metric", list(_METRICS))
@pytest.mark.parametrize("seed", range(40))
def test_scalar_metric_invariant_under_relabeling(metric, seed):
    res = _connected_graph(seed)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    fn = _METRICS[metric]
    base = fn(g)
    # Shuffled integer relabeling.
    perm = list(range(n))
    random.Random(seed + 1).shuffle(perm)
    g_int = fnx.relabel_nodes(g, {i: perm[i] for i in range(n)})
    assert fn(g_int) == base
    # String relabeling.
    g_str = fnx.relabel_nodes(g, {i: f"node_{i}" for i in range(n)})
    assert fn(g_str) == base


@pytest.mark.parametrize("seed", range(40))
def test_degree_assortativity_invariant_under_relabeling(seed):
    res = _connected_graph(seed, p=0.45)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    if g.number_of_edges() < 2:
        pytest.skip("too few edges")
    base = round(fnx.degree_assortativity_coefficient(g), 8)
    g_str = fnx.relabel_nodes(g, {i: f"v{i}" for i in range(n)})
    assert round(fnx.degree_assortativity_coefficient(g_str), 8) == base
