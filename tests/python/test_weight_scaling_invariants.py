"""Oracle-free weight-transform metamorphic relations.

Multiplying every edge weight by a constant ``c > 0``:

* scales shortest-path lengths, min/max spanning-tree total weight and the
  (weighted) Wiener index by exactly ``c`` (linearity)
* leaves the min/max spanning-tree edge sets and the shortest-path node
  sequences unchanged (a positive monotone transform preserves argmin/argmax)
* leaves min/max spanning-edge iterator choices unchanged under the same scaling
* relabels spanning-tree edge/weight outputs in lockstep

Adding the same constant to every edge leaves min/max spanning-tree and
spanning-edge choices unchanged and shifts total tree weight by that constant
times ``n - 1``.

Negating every edge weight swaps minimum and maximum spanning-tree choices.

These exercise the weighted code paths without any networkx oracle.

br-r37-c1-6fji3
br-r37-c1-6ws5d
br-r37-c1-pvstf
br-r37-c1-0g5x6
br-r37-c1-u1ot8
br-r37-c1-fdti4
br-r37-c1-rjwkl
br-r37-c1-j9nsw
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


def _shifted(g, k):
    gc = g.copy()
    for u, v in gc.edges():
        gc[u][v]["weight"] += k
    return gc


def _edge_record_weight_set(edge_records):
    return {
        (frozenset((u, v)), d["weight"])
        for u, v, d in edge_records
    }


def _edge_record_set(edge_records):
    return {frozenset((u, v)) for u, v, _ in edge_records}


def _mapped_edge_record_weight_set(edge_records, mapping):
    return {
        (frozenset((mapping[u], mapping[v])), d["weight"])
        for u, v, d in edge_records
    }


def _edge_weight_set(tree):
    return _edge_record_weight_set(tree.edges(data=True))


def _mapped_edge_weight_set(tree, mapping):
    return _mapped_edge_record_weight_set(tree.edges(data=True), mapping)


def _tree_weight(tree):
    return sum(d["weight"] for _, _, d in tree.edges(data=True))


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
    maxst_base = sum(d["weight"] for _, _, d in
                     fnx.maximum_spanning_tree(g, weight="weight").edges(data=True))
    maxst_scaled = sum(d["weight"] for _, _, d in
                       fnx.maximum_spanning_tree(gc, weight="weight").edges(data=True))
    assert maxst_scaled == pytest.approx(c * maxst_base)
    assert fnx.wiener_index(gc, weight="weight") == pytest.approx(
        c * fnx.wiener_index(g, weight="weight")
    )


@pytest.mark.parametrize("k", [1, 5, 11])
@pytest.mark.parametrize("seed", range(30))
def test_spanning_tree_outputs_shift_uniformly(k, seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    shifted = _shifted(g, k)
    expected_shift = k * (n - 1)

    base_min = fnx.minimum_spanning_tree(g, weight="weight")
    shifted_min = fnx.minimum_spanning_tree(shifted, weight="weight")
    assert _edge_record_set(base_min.edges(data=True)) == _edge_record_set(
        shifted_min.edges(data=True)
    )
    assert _tree_weight(shifted_min) == pytest.approx(
        _tree_weight(base_min) + expected_shift
    )

    base_max = fnx.maximum_spanning_tree(g, weight="weight")
    shifted_max = fnx.maximum_spanning_tree(shifted, weight="weight")
    assert _edge_record_set(base_max.edges(data=True)) == _edge_record_set(
        shifted_max.edges(data=True)
    )
    assert _tree_weight(shifted_max) == pytest.approx(
        _tree_weight(base_max) + expected_shift
    )


@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka"])
@pytest.mark.parametrize("k", [1, 5, 11])
@pytest.mark.parametrize("seed", range(30))
def test_spanning_edge_iterators_shift_invariant(algorithm, k, seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, _ = res
    shifted = _shifted(g, k)

    base_min = fnx.minimum_spanning_edges(
        g, algorithm=algorithm, weight="weight", data=True
    )
    shifted_min = fnx.minimum_spanning_edges(
        shifted, algorithm=algorithm, weight="weight", data=True
    )
    assert _edge_record_set(base_min) == _edge_record_set(shifted_min)

    base_max = fnx.maximum_spanning_edges(
        g, algorithm=algorithm, weight="weight", data=True
    )
    shifted_max = fnx.maximum_spanning_edges(
        shifted, algorithm=algorithm, weight="weight", data=True
    )
    assert _edge_record_set(base_max) == _edge_record_set(shifted_max)


@pytest.mark.parametrize("seed", range(30))
def test_negated_weights_swap_spanning_tree_extrema(seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, _ = res
    negated = _scaled(g, -1)

    base_min = fnx.minimum_spanning_tree(g, weight="weight")
    base_max = fnx.maximum_spanning_tree(g, weight="weight")
    negated_min = fnx.minimum_spanning_tree(negated, weight="weight")
    negated_max = fnx.maximum_spanning_tree(negated, weight="weight")

    assert _edge_record_set(negated_min.edges(data=True)) == _edge_record_set(
        base_max.edges(data=True)
    )
    assert _edge_record_set(negated_max.edges(data=True)) == _edge_record_set(
        base_min.edges(data=True)
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


@pytest.mark.parametrize("c", [2, 3, 7])
@pytest.mark.parametrize("seed", range(30))
def test_argmax_invariant_under_positive_scaling(c, seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, _ = res
    gc = _scaled(g, c)

    base_max = sorted(tuple(sorted(e)) for e in
                      fnx.maximum_spanning_tree(g, weight="weight").edges())
    scaled_max = sorted(tuple(sorted(e)) for e in
                        fnx.maximum_spanning_tree(gc, weight="weight").edges())
    assert base_max == scaled_max


@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka"])
@pytest.mark.parametrize("c", [2, 3, 7])
@pytest.mark.parametrize("seed", range(30))
def test_spanning_edge_iterators_positive_scaling_invariant(algorithm, c, seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, _ = res
    gc = _scaled(g, c)

    base_min = fnx.minimum_spanning_edges(
        g, algorithm=algorithm, weight="weight", data=True
    )
    scaled_min = fnx.minimum_spanning_edges(
        gc, algorithm=algorithm, weight="weight", data=True
    )
    assert _edge_record_set(base_min) == _edge_record_set(scaled_min)

    base_max = fnx.maximum_spanning_edges(
        g, algorithm=algorithm, weight="weight", data=True
    )
    scaled_max = fnx.maximum_spanning_edges(
        gc, algorithm=algorithm, weight="weight", data=True
    )
    assert _edge_record_set(base_max) == _edge_record_set(scaled_max)


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


@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka"])
@pytest.mark.parametrize("seed", range(30))
def test_spanning_edge_iterators_relabeling_equivariant(algorithm, seed):
    res = _connected_weighted(seed, distinct=True)
    if res is None:
        pytest.skip("disconnected")
    g, n = res
    mapping = {node: f"edge-node-{seed}-{node}" for node in range(n)}
    relabelled = fnx.relabel_nodes(g, mapping)

    base_min = fnx.minimum_spanning_edges(
        g, algorithm=algorithm, weight="weight", data=True
    )
    relabelled_min = fnx.minimum_spanning_edges(
        relabelled, algorithm=algorithm, weight="weight", data=True
    )
    assert _mapped_edge_record_weight_set(
        base_min, mapping
    ) == _edge_record_weight_set(relabelled_min)

    base_max = fnx.maximum_spanning_edges(
        g, algorithm=algorithm, weight="weight", data=True
    )
    relabelled_max = fnx.maximum_spanning_edges(
        relabelled, algorithm=algorithm, weight="weight", data=True
    )
    assert _mapped_edge_record_weight_set(
        base_max, mapping
    ) == _edge_record_weight_set(relabelled_max)
