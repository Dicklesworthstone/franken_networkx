"""Oracle-free relabeling-equivariance of graph-returning operations.

A structural graph transformation must commute with node relabeling up to
isomorphism: ``op(relabel(G))`` is isomorphic to ``op(G)``. This guards the
label-dependence bug class for graph-RETURNING functions — the family where
the spanning-tree str-node defect lived.

br-r37-c1-rhkmf
br-r37-c1-o1jjg
br-r37-c1-ip7l4
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _to_nx(g):
    cls = nx.DiGraph if g.is_directed() else nx.Graph
    h = cls(list(g.edges()))
    h.add_nodes_from(g.nodes())
    return h


def _isomorphic(a, b):
    return nx.is_isomorphic(_to_nx(a), _to_nx(b))


def _random_graph(seed, directed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 8)
    g = (fnx.DiGraph if directed else fnx.Graph)()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < p:
                g.add_edge(u, v)
    return g, n


def _weighted_chain_with_chords(seed, directed):
    rng = random.Random(seed)
    n = rng.randint(5, 8)
    g = (fnx.DiGraph if directed else fnx.Graph)()
    g.add_nodes_from(range(n))
    for u in range(n - 1):
        g.add_edge(u, u + 1, weight=1)
    for u in range(n):
        for v in range(u + 2, n):
            if rng.random() < 0.45:
                g.add_edge(u, v, weight=100 + u * n + v)
    return g, n


def _mapped_path(path, mapping):
    return [mapping[node] for node in path]


def _mapped_node_sets(sets, mapping):
    return {frozenset(mapping[node] for node in node_set) for node_set in sets}


def _edge_sets(edges):
    return {frozenset(edge) for edge in edges}


def _mapped_edge_sets(edges, mapping):
    return {frozenset(mapping[node] for node in edge) for edge in edges}


_UNDIRECTED_OPS = {
    "complement": lambda g: fnx.complement(g),
    "k_core": lambda g: fnx.k_core(g),
    "subgraph": lambda g: g.subgraph(list(g)[: max(1, len(g) - 1)]).copy(),
}

_DIRECTED_OPS = {
    "reverse": lambda g: fnx.reverse(g),
    "transitive_closure": lambda g: fnx.transitive_closure(g),
    "condensation": lambda g: fnx.condensation(g),
}


@pytest.mark.parametrize("op_name", list(_UNDIRECTED_OPS))
@pytest.mark.parametrize("seed", range(30))
def test_undirected_ops_relabeling_equivariant(op_name, seed):
    g, n = _random_graph(seed, directed=False)
    op = _UNDIRECTED_OPS[op_name]
    g_relabelled = fnx.relabel_nodes(g, {i: f"s{i}" for i in range(n)})
    assert _isomorphic(op(g), op(g_relabelled))


@pytest.mark.parametrize("op_name", list(_DIRECTED_OPS))
@pytest.mark.parametrize("seed", range(30))
def test_directed_ops_relabeling_equivariant(op_name, seed):
    g, n = _random_graph(seed, directed=True)
    op = _DIRECTED_OPS[op_name]
    g_relabelled = fnx.relabel_nodes(g, {i: f"s{i}" for i in range(n)})
    assert _isomorphic(op(g), op(g_relabelled))


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_shortest_path_sequences_relabeling_equivariant(directed, seed):
    g, n = _weighted_chain_with_chords(seed, directed)
    mapping = {i: f"node_{seed}_{i}" for i in range(n)}
    g_relabelled = fnx.relabel_nodes(g, mapping)
    source = 0
    target = n - 1

    base_shortest = fnx.shortest_path(g, source, target, weight="weight")
    relabelled_shortest = fnx.shortest_path(
        g_relabelled, mapping[source], mapping[target], weight="weight"
    )
    assert relabelled_shortest == _mapped_path(base_shortest, mapping)

    base_dijkstra = fnx.dijkstra_path(g, source, target, weight="weight")
    relabelled_dijkstra = fnx.dijkstra_path(
        g_relabelled, mapping[source], mapping[target], weight="weight"
    )
    assert relabelled_dijkstra == _mapped_path(base_dijkstra, mapping)

    base_all = list(fnx.all_shortest_paths(g, source, target, weight="weight"))
    relabelled_all = list(
        fnx.all_shortest_paths(
            g_relabelled, mapping[source], mapping[target], weight="weight"
        )
    )
    assert relabelled_all == [_mapped_path(path, mapping) for path in base_all]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_single_source_path_dict_relabeling_equivariant(directed, seed):
    g, n = _weighted_chain_with_chords(seed, directed)
    mapping = {i: f"label-{seed}-{i}" for i in range(n)}
    g_relabelled = fnx.relabel_nodes(g, mapping)

    base_paths = fnx.single_source_dijkstra_path(g, 0, weight="weight")
    relabelled_paths = fnx.single_source_dijkstra_path(
        g_relabelled, mapping[0], weight="weight"
    )
    expected = {
        mapping[target]: _mapped_path(path, mapping)
        for target, path in base_paths.items()
    }
    assert relabelled_paths == expected


@pytest.mark.parametrize("seed", range(30))
def test_undirected_set_outputs_relabeling_equivariant(seed):
    g, n = _random_graph(seed, directed=False, p=0.35)
    mapping = {i: f"component-{seed}-{i}" for i in range(n)}
    g_relabelled = fnx.relabel_nodes(g, mapping)

    assert _edge_sets(fnx.bridges(g_relabelled)) == _mapped_edge_sets(
        fnx.bridges(g), mapping
    )
    assert set(fnx.articulation_points(g_relabelled)) == {
        mapping[node] for node in fnx.articulation_points(g)
    }
    assert _mapped_node_sets(fnx.connected_components(g), mapping) == {
        frozenset(component) for component in fnx.connected_components(g_relabelled)
    }
    assert _mapped_node_sets(fnx.biconnected_components(g), mapping) == {
        frozenset(component) for component in fnx.biconnected_components(g_relabelled)
    }


@pytest.mark.parametrize("seed", range(30))
def test_directed_component_outputs_relabeling_equivariant(seed):
    g, n = _random_graph(seed, directed=True, p=0.35)
    mapping = {i: f"directed-component-{seed}-{i}" for i in range(n)}
    g_relabelled = fnx.relabel_nodes(g, mapping)

    assert _mapped_node_sets(fnx.strongly_connected_components(g), mapping) == {
        frozenset(component)
        for component in fnx.strongly_connected_components(g_relabelled)
    }
    assert _mapped_node_sets(fnx.weakly_connected_components(g), mapping) == {
        frozenset(component)
        for component in fnx.weakly_connected_components(g_relabelled)
    }
