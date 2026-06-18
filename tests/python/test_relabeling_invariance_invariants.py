"""Oracle-free relabeling-invariance of order-invariant scalar metrics.

Renaming the nodes of a graph (to shuffled integers or to string labels)
must not change any metric that depends only on graph structure. This
directly guards against label-type / iteration-order dependence bugs — the
class that produced the spanning-tree str-node defect.

br-r37-c1-jeohx
br-r37-c1-j78ld
br-r37-c1-pltsy
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

_NODE_METRIC_MAPS = {
    "degree_centrality": lambda g: fnx.degree_centrality(g),
    "closeness_centrality": lambda g: fnx.closeness_centrality(g),
    "betweenness_centrality": lambda g: fnx.betweenness_centrality(g),
    "harmonic_centrality": lambda g: fnx.harmonic_centrality(g),
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


def _undirected_edge_metric_map(values):
    return {frozenset(edge): value for edge, value in values.items()}


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


@pytest.mark.parametrize("metric", list(_NODE_METRIC_MAPS))
@pytest.mark.parametrize("seed", range(30))
def test_node_metric_maps_relabeling_equivariant(metric, seed):
    res = _connected_graph(seed, p=0.45)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    mapping = {i: f"node-{seed}-{i}" for i in range(n)}
    g_str = fnx.relabel_nodes(g, mapping)
    metric_fn = _NODE_METRIC_MAPS[metric]

    base = metric_fn(g)
    relabelled = metric_fn(g_str)

    # Value-equivariance: every node's metric value is unchanged under relabeling.
    assert set(relabelled) == {mapping[node] for node in base}
    for node, value in base.items():
        assert relabelled[mapping[node]] == pytest.approx(value)

    # Key-order equivariance: most centrality maps emit keys in node-iteration
    # order, which relabeling preserves. harmonic_centrality is the exception —
    # it emits keys in an internal (non-node) order, and networkx does NOT
    # preserve that order under relabeling either (fnx matches nx byte-for-byte,
    # so this is not an fnx divergence). Only assert key order where it holds.
    if metric != "harmonic_centrality":
        assert list(relabelled) == [mapping[node] for node in base]


@pytest.mark.parametrize("seed", range(30))
def test_edge_metric_maps_relabeling_equivariant(seed):
    res = _connected_graph(seed, p=0.45)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    mapping = {i: f"edge-node-{seed}-{i}" for i in range(n)}
    g_str = fnx.relabel_nodes(g, mapping)

    base = _undirected_edge_metric_map(fnx.edge_betweenness_centrality(g))
    relabelled = _undirected_edge_metric_map(
        fnx.edge_betweenness_centrality(g_str)
    )
    expected = {
        frozenset(mapping[node] for node in edge): value
        for edge, value in base.items()
    }

    assert set(relabelled) == set(expected)
    for edge, value in expected.items():
        assert relabelled[edge] == pytest.approx(value)
