"""Differential parity for WEIGHTED centrality / path variants.

Weight handling (which keyword, how distances vs. influence weights are
interpreted, directed vs. undirected) is a recurring source of subtle
divergence. This pins fnx == networkx for the weighted forms across both
undirected and directed random graphs.

No mocks: real fnx and real networkx on identically-constructed weighted graphs.
"""

from __future__ import annotations

import math
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _norm(x):
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, float):
        return round(x, 5) if math.isfinite(x) else repr(x)
    if isinstance(x, (list, tuple)):
        return type(x)(_norm(v) for v in x)
    return x


def _weighted_undirected(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    g = fnx.Graph(); g.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                g.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return g, ng


def _weighted_directed(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    g = fnx.DiGraph(); g.add_nodes_from(range(n))
    ng = nx.DiGraph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.4:
                w = r.randint(1, 9)
                g.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return g, ng


@pytest.mark.parametrize("seed", range(40))
def test_weighted_undirected_centralities_match(seed):
    g, ng = _weighted_undirected(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    assert _norm(fnx.betweenness_centrality(g, weight="weight")) == _norm(
        nx.betweenness_centrality(ng, weight="weight")
    )
    assert _norm(fnx.closeness_centrality(g, distance="weight")) == _norm(
        nx.closeness_centrality(ng, distance="weight")
    )
    assert _norm(fnx.pagerank(g, weight="weight")) == _norm(
        nx.pagerank(ng, weight="weight")
    )
    assert _norm(fnx.clustering(g, weight="weight")) == _norm(
        nx.clustering(ng, weight="weight")
    )
    assert _norm(fnx.average_shortest_path_length(g, weight="weight")) == _norm(
        nx.average_shortest_path_length(ng, weight="weight")
    )


@pytest.mark.parametrize("seed", range(50))
def test_weighted_directed_centralities_match(seed):
    g, ng = _weighted_directed(seed)
    assert _norm(fnx.pagerank(g, weight="weight")) == _norm(
        nx.pagerank(ng, weight="weight")
    )
    assert _norm(fnx.betweenness_centrality(g, weight="weight")) == _norm(
        nx.betweenness_centrality(ng, weight="weight")
    )
    assert _norm(dict(fnx.all_pairs_dijkstra_path_length(g, weight="weight"))) == (
        _norm(dict(nx.all_pairs_dijkstra_path_length(ng, weight="weight")))
    )
    assert round(fnx.overall_reciprocity(g), 5) == round(
        nx.overall_reciprocity(ng), 5
    )


# br-r37-c1-mfqlz: this module is "weighted centrality/PATH differential parity"
# and the only path function used was all_pairs_dijkstra_path_LENGTH. A weighted
# tie-break divergence hides precisely there: two routes of equal total weight
# leave every length identical while the chosen route differs, so a
# length-only comparison cannot see it. The weighted path differs from the
# unweighted one on 12 of 36 connected seeds, so this arm reaches real work.
@pytest.mark.parametrize("seed", range(40))
def test_weighted_undirected_paths_match(seed):
    g, ng = _weighted_undirected(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    n = g.number_of_nodes()
    r = random.Random(seed + 9)
    s, t = r.sample(range(n), 2)
    assert fnx.dijkstra_path(g, s, t, weight="weight") == (
        nx.dijkstra_path(ng, s, t, weight="weight")
    )
    assert _norm({k: dict(v) for k, v in fnx.all_pairs_dijkstra_path(g, weight="weight")}) == (
        _norm({k: dict(v) for k, v in nx.all_pairs_dijkstra_path(ng, weight="weight")})
    )


@pytest.mark.parametrize("seed", range(50))
def test_weighted_directed_paths_match(seed):
    g, ng = _weighted_directed(seed)
    assert _norm({k: dict(v) for k, v in fnx.all_pairs_dijkstra_path(g, weight="weight")}) == (
        _norm({k: dict(v) for k, v in nx.all_pairs_dijkstra_path(ng, weight="weight")})
    )


# br-r37-c1-mfqlz: `_norm` returns dicts, and dict equality ignores insertion
# order — so every assertion above is blind to the ORDER of the returned
# node->value map, which is observable. Verified equal for all of these across
# their seeds before being asserted.
@pytest.mark.parametrize("seed", range(40))
def test_weighted_result_key_order_parity(seed):
    g, ng = _weighted_undirected(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    for call in (
        lambda L, G: L.betweenness_centrality(G, weight="weight"),
        lambda L, G: L.closeness_centrality(G, distance="weight"),
        lambda L, G: L.pagerank(G, weight="weight"),
        lambda L, G: L.clustering(G, weight="weight"),
    ):
        assert list(call(fnx, g).keys()) == list(call(nx, ng).keys())


@pytest.mark.parametrize("seed", range(50))
def test_weighted_directed_result_key_order_parity(seed):
    g, ng = _weighted_directed(seed)
    for call in (
        lambda L, G: L.pagerank(G, weight="weight"),
        lambda L, G: L.betweenness_centrality(G, weight="weight"),
        lambda L, G: dict(L.all_pairs_dijkstra_path_length(G, weight="weight")),
    ):
        assert list(call(fnx, g).keys()) == list(call(nx, ng).keys())


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("wf_improved", [False, True])
@pytest.mark.parametrize("base_weight", [1, 0.25, 2**53 + 1])
def test_weighted_closeness_source_rows_preserve_scores(
    graph_type, wf_improved, base_weight
):
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(range(8))
        graph.add_weighted_edges_from(
            [
                (0, 1, base_weight),
                (1, 2, base_weight + 1),
                (2, 3, base_weight + 2),
                (4, 5, base_weight),
                (1, 1, base_weight),
            ],
            weight="distance",
        )
        if graph.is_multigraph():
            graph.add_edge(0, 1, distance=base_weight + 3)
        graphs.append(graph)
    expected = nx.closeness_centrality(
        graphs[0], distance="distance", wf_improved=wf_improved
    )
    actual = fnx.closeness_centrality(
        graphs[1], distance="distance", wf_improved=wf_improved
    )
    assert list(actual.items()) == list(expected.items())
    for node in graphs[1]:
        assert actual[node] == fnx.closeness_centrality(
            graphs[1], u=node, distance="distance", wf_improved=wf_improved
        )


def _weighted_closeness_python_peak(module, graph):
    import gc
    import tracemalloc

    warmup = graph.__class__()
    warmup.add_edge("a", "b", distance=1.0)
    module.closeness_centrality(warmup, distance="distance")
    gc.collect()
    tracemalloc.start()
    try:
        result = module.closeness_centrality(graph, distance="distance")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_weighted_closeness_retains_only_one_distance_row(graph_type):
    # Both implementations run in this invocation on the same connected
    # weighted graph. A modest star keeps the traversal cheap while exposing
    # retention of the quadratic collection of Python distance dictionaries.
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(range(600))
        for node in range(1, 600):
            graph.add_edge(0, node, distance=1.0)
            if graph.is_directed():
                graph.add_edge(node, 0, distance=1.0)
        graphs.append(graph)
    expected, oracle_peak = _weighted_closeness_python_peak(nx, graphs[0])
    actual, native_peak = _weighted_closeness_python_peak(fnx, graphs[1])
    assert list(actual.items()) == list(expected.items())
    # Allow normal per-graph caches and interpreter variance while rejecting
    # retention of all 360,000 pairwise distances.
    assert native_peak <= max(2 * 1024**2, 8 * oracle_peak), (
        native_peak,
        oracle_peak,
    )


def _live_distance_centrality_result(module, owner, graph_type, name, options, view):
    graph = getattr(owner, graph_type)()
    graph.add_weighted_edges_from(
        [(0, 1, 10), (1, 2, 10), (2, 0, 50), (0, 3, 20), (3, 1, 20)],
        weight="distance",
    )
    if graph.is_multigraph():
        graph.add_edge(0, 1, key="alternate", distance=15)
    work = graph
    if view == "filtered":
        work = graph.subgraph(list(graph))
    elif view == "reverse":
        if not graph.is_directed():
            pytest.skip("reverse requires a directed graph")
        work = graph.reverse(copy=False)
    trace = []

    def distance(source, target, data):
        later = graph[1][2][0] if graph.is_multigraph() else graph[1][2]
        later["distance"] = 1
        rows = list(data.values()) if graph.is_multigraph() else [data]
        for row in rows:
            row["calls"] = row.get("calls", 0) + 1
        values = tuple(row["distance"] for row in rows)
        trace.append((source, target, values))
        return min(values)

    result = getattr(module, name)(work, distance=distance, **options)
    if isinstance(result, dict):
        result = list(result.items())
    if graph.is_multigraph():
        attrs = [(u, v, k, dict(d)) for u, v, k, d in graph.edges(keys=True, data=True)]
    else:
        attrs = [(u, v, dict(d)) for u, v, d in graph.edges(data=True)]
    return result, trace, attrs


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("view", ["plain", "filtered", "reverse"])
@pytest.mark.parametrize(
    "name,options",
    [
        ("closeness_centrality", {}),
        ("closeness_centrality", {"u": 2}),
        ("harmonic_centrality", {}),
        ("harmonic_centrality", {"nbunch": [2]}),
        ("harmonic_centrality", {"sources": [0, 2]}),
    ],
)
def test_weighted_centrality_live_callback_rows(graph_type, owner, view, name, options):
    expected = _live_distance_centrality_result(nx, nx, graph_type, name, options, view)
    actual = _live_distance_centrality_result(fnx, owner, graph_type, name, options, view)
    # Score, callback order and caller-visible writes are independent contracts.
    # Directed closeness retains NetworkX's reverse(copy=True) boundary; harmonic
    # transposition and the explicit input views retain shared edge dictionaries.
    assert actual == expected


def _asymmetric_distance_view(owner, graph_type, view):
    graph = getattr(owner, graph_type)()
    graph.add_weighted_edges_from(
        [(0, 1, 1), (1, 0, 7), (1, 2, 2), (2, 1, 9), (2, 0, 4), (0, 2, 11)],
        weight="distance",
    )
    if graph.is_multigraph():
        graph.add_edge(0, 1, key="alternate", distance=12)
        graph.add_edge(1, 0, key="alternate", distance=15)
    if view == "reverse":
        graph = graph.reverse(copy=False)
    work = graph.to_undirected(as_view=True)
    return work.subgraph(list(work)) if view == "filtered" else work


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("view", ["plain", "filtered", "reverse"])
@pytest.mark.parametrize(
    "name,options",
    [
        ("closeness_centrality", {}),
        ("closeness_centrality", {"u": 2}),
        ("harmonic_centrality", {}),
        ("harmonic_centrality", {"nbunch": [2]}),
    ],
)
def test_weighted_centrality_asymmetric_view_rows(graph_type, owner, view, name, options):
    reference = _asymmetric_distance_view(nx, graph_type, view)
    graph = _asymmetric_distance_view(owner, graph_type, view)
    expected = getattr(nx, name)(reference, distance="distance", **options)
    actual = getattr(fnx, name)(graph, distance="distance", **options)
    if isinstance(expected, dict):
        assert list(actual.items()) == list(expected.items())
    else:
        assert actual == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("wf_improved", [False, True])
def test_weighted_closeness_directed_copy_order(graph_type, owner, wf_improved):
    results = []
    for algorithm, graph_module in ((nx.closeness_centrality, nx), (fnx.closeness_centrality, owner)):
        graph = getattr(graph_module, graph_type)()
        graph.add_edges_from([(0, 1), (1, 2), (2, 0)])

        def distance(source, target, data):
            graph.add_node("added")
            return 1

        results.append(algorithm(graph, u=0, distance=distance, wf_improved=wf_improved))
        assert len(graph) == 4
    # The callback changes the original graph while the search and its
    # normalization retain the three-node reversed copy.
    assert results == [2 / 3, 2 / 3]
