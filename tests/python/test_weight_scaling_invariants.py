"""Oracle-free weight-scaling metamorphic relations.

Multiplying every edge weight by a constant ``c > 0``:

* scales shortest-path lengths, MST total weight and the (weighted) Wiener
  index by exactly ``c`` (linearity)
* leaves the MST edge set and the shortest-path node sequences unchanged
  (a positive monotone transform preserves the argmin)
* relabels spanning-tree edge/weight outputs in lockstep

These exercise the weighted code paths without any networkx oracle.

br-r37-c1-6fji3
br-r37-c1-6ws5d
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected_weighted(seed, distinct, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    counter = 0
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                counter += 1
                w = counter * 10 + rng.randint(1, 9) if distinct else rng.randint(1, 9)
                g.add_edge(u, v, weight=w)
    ng = nx.Graph(list(g.edges()))
    ng.add_nodes_from(range(n))
    if not nx.is_connected(ng):
        return None
    return g, n


def _scaled(g, c):
    gc = g.copy()
    for u, v in gc.edges():
        gc[u][v]["weight"] *= c
    return gc


def _edge_weight_set(tree):
    return {
        (frozenset((u, v)), d["weight"])
        for u, v, d in tree.edges(data=True)
    }


def _mapped_edge_weight_set(tree, mapping):
    return {
        (frozenset((mapping[u], mapping[v])), d["weight"])
        for u, v, d in tree.edges(data=True)
    }


@pytest.mark.parametrize("c", [2, 3, 5, 10])
@pytest.mark.parametrize("seed", range(30))
def test_weighted_metrics_scale_linearly(c, seed):
    res = _connected_weighted(seed, distinct=False)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    gc = _scaled(g, c)
    for s in range(min(2, n)):
        base = fnx.single_source_dijkstra_path_length(g, s, weight="weight")
        scaled = fnx.single_source_dijkstra_path_length(gc, s, weight="weight")
        assert all(scaled[t] == pytest.approx(c * base[t]) for t in base)
    mst_base = sum(d["weight"] for _, _, d in
                   fnx.minimum_spanning_tree(g, weight="weight").edges(data=True))
    mst_scaled = sum(d["weight"] for _, _, d in
                     fnx.minimum_spanning_tree(gc, weight="weight").edges(data=True))
    assert mst_scaled == pytest.approx(c * mst_base)
    assert fnx.wiener_index(gc, weight="weight") == pytest.approx(
        c * fnx.wiener_index(g, weight="weight")
    )


@pytest.mark.parametrize("c", [2, 3, 7])
@pytest.mark.parametrize("seed", range(30))
def test_argmin_invariant_under_positive_scaling(c, seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    gc = _scaled(g, c)
    base_mst = sorted(tuple(sorted(e)) for e in
                      fnx.minimum_spanning_tree(g, weight="weight").edges())
    scaled_mst = sorted(tuple(sorted(e)) for e in
                        fnx.minimum_spanning_tree(gc, weight="weight").edges())
    assert base_mst == scaled_mst
    for s in range(min(2, n)):
        for t in range(n):
            if s == t:
                continue
            assert fnx.dijkstra_path(g, s, t, weight="weight") == (
                fnx.dijkstra_path(gc, s, t, weight="weight")
            )


@pytest.mark.parametrize("seed", range(30))
def test_spanning_tree_outputs_relabeling_equivariant(seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    mapping = {node: f"tree-node-{seed}-{node}" for node in range(n)}
    relabelled = fnx.relabel_nodes(g, mapping)

    base_min = fnx.minimum_spanning_tree(g, weight="weight")
    relabelled_min = fnx.minimum_spanning_tree(relabelled, weight="weight")
    assert _mapped_edge_weight_set(base_min, mapping) == _edge_weight_set(relabelled_min)

    base_max = fnx.maximum_spanning_tree(g, weight="weight")
    relabelled_max = fnx.maximum_spanning_tree(relabelled, weight="weight")
    assert _mapped_edge_weight_set(base_max, mapping) == _edge_weight_set(relabelled_max)
