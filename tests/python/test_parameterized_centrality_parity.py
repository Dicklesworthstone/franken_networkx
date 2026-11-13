"""Parity for parameterized centrality variants.

Centrality functions take many flags that each select a distinct code path —
``endpoints``, ``normalized``, subset sources/targets, pagerank
``personalization``/``alpha``, katz ``alpha``/``beta``, closeness
``wf_improved``, harmonic ``nbunch``. These are less exercised than the default
forms; this pins fnx == networkx across them.

No mocks: real fnx and real networkx on identically-built graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _round(d, p=5):
    return {k: (round(v, p) if isinstance(v, float) else v) for k, v in d.items()}


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(6, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, r


@pytest.mark.parametrize("seed", range(40))
def test_betweenness_variants(seed):
    fg, ng, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _round(fnx.betweenness_centrality(fg, endpoints=True)) == _round(
        nx.betweenness_centrality(ng, endpoints=True)
    )
    assert _round(fnx.betweenness_centrality(fg, normalized=False)) == _round(
        nx.betweenness_centrality(ng, normalized=False)
    )
    fe = {tuple(sorted(k)): round(v, 5) for k, v in fnx.edge_betweenness_centrality(fg).items()}
    ne = {tuple(sorted(k)): round(v, 5) for k, v in nx.edge_betweenness_centrality(ng).items()}
    assert fe == ne
    src, tgt = list(range(n // 2)), list(range(n // 2, n))
    assert _round(
        fnx.betweenness_centrality_subset(fg, sources=src, targets=tgt)
    ) == _round(nx.betweenness_centrality_subset(ng, sources=src, targets=tgt))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_and_katz_variants(seed):
    fg, ng, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    pers = {i: r.random() for i in range(n)}
    assert _round(fnx.pagerank(fg, personalization=pers)) == _round(
        nx.pagerank(ng, personalization=pers)
    )
    assert _round(fnx.pagerank(fg, alpha=0.7)) == _round(nx.pagerank(ng, alpha=0.7))
    assert _round(fnx.katz_centrality_numpy(fg, alpha=0.05, beta=0.5)) == _round(
        nx.katz_centrality_numpy(ng, alpha=0.05, beta=0.5)
    )


@pytest.mark.parametrize("seed", range(40))
def test_closeness_and_harmonic_variants(seed):
    fg, ng, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert _round(fnx.closeness_centrality(fg, wf_improved=False)) == _round(
        nx.closeness_centrality(ng, wf_improved=False)
    )
    assert _round(fnx.harmonic_centrality(fg, nbunch=[0, 1])) == _round(
        nx.harmonic_centrality(ng, nbunch=[0, 1])
    )


@pytest.mark.parametrize("seed", range(40))
def test_each_parameter_actually_changes_the_result(seed):
    """Parity alone cannot see a parameter that BOTH libraries ignore.

    Every assertion in this file compares fnx to networkx with the same flag
    set. If a flag were dropped on the floor by both, the comparison would
    still pass — the file would be pinning the default path under a variant's
    name. Requiring each variant to differ from its default is the missing half.
    """
    fg, _, n, r = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")

    default_betweenness = fnx.betweenness_centrality(fg)
    assert fnx.betweenness_centrality(fg, endpoints=True) != default_betweenness
    assert fnx.betweenness_centrality(fg, normalized=False) != default_betweenness
    sources, targets = list(range(n // 2)), list(range(n // 2, n))
    assert fnx.betweenness_centrality_subset(
        fg, sources=sources, targets=targets
    ) != default_betweenness

    default_pagerank = fnx.pagerank(fg)
    assert fnx.pagerank(fg, personalization={i: r.random() for i in range(n)}) != default_pagerank
    assert fnx.pagerank(fg, alpha=0.7) != default_pagerank

    assert fnx.katz_centrality_numpy(fg, alpha=0.05, beta=0.5) != fnx.katz_centrality_numpy(fg)
    assert fnx.harmonic_centrality(fg, nbunch=[0, 1]) != fnx.harmonic_centrality(fg)


def _sparse_pair(seed):
    """Sparse enough to be disconnected, which is where wf_improved bites."""
    r = random.Random(seed)
    n = r.randint(6, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.18]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng


@pytest.mark.parametrize("seed", range(40))
def test_wf_improved_is_exercised_where_it_is_not_the_identity(seed):
    """wf_improved=False is a NO-OP on a connected graph.

    The sweep above tests it on connected graphs only, so it compares the
    default against the default — 0 of its 38 connected draws show any
    difference. The Wasserman-Faust correction scales by the reachable
    fraction, which is 1 when everything is reachable; it only does anything
    once the graph splits.
    """
    fg, ng = _sparse_pair(seed)
    if fnx.is_connected(fg):
        pytest.skip("connected — wf_improved is the identity here")

    corrected = fnx.closeness_centrality(fg)
    uncorrected = fnx.closeness_centrality(fg, wf_improved=False)
    assert uncorrected != corrected                      # the flag now bites
    assert _round(uncorrected) == _round(nx.closeness_centrality(ng, wf_improved=False))
    assert _round(corrected) == _round(nx.closeness_centrality(ng))


def _closeness_filtered_rows(owner, graph_type):
    graph = getattr(owner, graph_type)()
    graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 3)], weight="distance")
    if graph.is_multigraph():
        predicate = lambda u, v, key: u < v
    else:
        predicate = lambda u, v: u < v
    return owner.subgraph_view(graph, filter_edge=predicate)


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("u", [None, 1, 2])
@pytest.mark.parametrize("distance", [None, "distance"])
@pytest.mark.parametrize("wf_improved", [False, True])
def test_closeness_public_filtered_rows(owner, graph_type, u, distance, wf_improved):
    reference = _closeness_filtered_rows(nx, graph_type)
    graph = _closeness_filtered_rows(owner, graph_type)
    options = dict(u=u, distance=distance, wf_improved=wf_improved)
    expected = nx.closeness_centrality(reference, **options)
    actual = fnx.closeness_centrality(graph, **options)
    if isinstance(expected, dict):
        assert list(actual.items()) == list(expected.items())
    else:
        assert actual == expected
    if u is None and distance is None and wf_improved:
        assert actual == {0: 2 / 3, 1: 0.5, 2: 0.0}


@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("warm_cache", [False, True])
@pytest.mark.parametrize("u", [None, 1])
def test_closeness_public_backend_recovers_filtered_rows(graph_type, warm_cache, u):
    graph = _closeness_filtered_rows(nx, graph_type)
    if warm_cache:
        nx.degree_centrality(graph, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    expected = nx.closeness_centrality(graph, u=u)
    actual = nx.closeness_centrality(graph, u=u, backend="franken_networkx")
    assert actual == expected


def _closeness_reverse_provider_result(algorithm, owner, graph_type, u, distance):
    trace = []

    class ReverseProvider(getattr(owner, graph_type)):
        def reverse(self, *args, **kwargs):
            trace.append((args, kwargs))
            graph = getattr(owner, graph_type)()
            graph.add_nodes_from([2, 0, 1])
            graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 3)], weight="distance")
            return graph

    graph = ReverseProvider()
    graph.add_edges_from([(1, 0), (2, 0)])
    result = algorithm(graph, u=u, distance=distance)
    return list(result.items()) if isinstance(result, dict) else result, trace


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("u", [None, 1])
@pytest.mark.parametrize("distance", [None, "distance"])
def test_closeness_public_reverse_result_is_authoritative(owner, graph_type, u, distance):
    expected = _closeness_reverse_provider_result(
        nx.closeness_centrality, nx, graph_type, u, distance
    )
    actual = _closeness_reverse_provider_result(
        fnx.closeness_centrality, owner, graph_type, u, distance
    )
    assert actual == expected
    assert actual[1] == [((), {})]


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_closeness_public_reverse_error_precedes_missing_source(owner, graph_type):
    class ReverseProvider(getattr(owner, graph_type)):
        def reverse(self, *args, **kwargs):
            raise RuntimeError("reverse provider failed")

    graph = ReverseProvider()
    graph.add_edge(0, 1)
    with pytest.raises(RuntimeError, match="^reverse provider failed$"):
        fnx.closeness_centrality(graph, u="missing")


def _closeness_option_mutation_result(algorithm, owner, graph_type):
    graph = getattr(owner, graph_type)()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(0, 1), (1, 2)])
    trace = []

    class Correction:
        def __bool__(self):
            trace.append(tuple(graph.edges()))
            if len(trace) == 1:
                graph.remove_edge(1, 2)
                graph.add_edge(2, 3)
            return True

    result = algorithm(graph, wf_improved=Correction())
    return list(result.items()), trace


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
def test_closeness_public_option_protocol_observes_each_search(owner, graph_type):
    expected = _closeness_option_mutation_result(nx.closeness_centrality, nx, graph_type)
    actual = _closeness_option_mutation_result(fnx.closeness_centrality, owner, graph_type)
    assert actual == expected
    assert actual[0] == [(0, 4 / 9), (1, 1 / 3), (2, 1 / 3), (3, 1 / 3)]
    assert len(actual[1]) == 4


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("size", [0, 1, 4])
def test_closeness_public_dormant_option_is_not_evaluated(owner, size):
    class Correction:
        def __bool__(self):
            raise AssertionError("isolates must not evaluate the correction")

    graph = owner.Graph()
    graph.add_nodes_from(range(size))
    assert fnx.closeness_centrality(graph, wf_improved=Correction()) == dict.fromkeys(
        range(size), 0.0
    )


def _closeness_size_provider_result(algorithm, owner):
    trace = []

    class SizedGraph(owner.Graph):
        def __len__(self):
            size = super().__len__() + len(trace)
            trace.append(size)
            return size

    graph = SizedGraph()
    graph.add_edges_from([(0, 1), (1, 2)])
    trace.clear()
    result = algorithm(graph)
    return list(result.items()), trace


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
def test_closeness_public_size_is_read_after_each_search(owner):
    expected = _closeness_size_provider_result(nx.closeness_centrality, nx)
    actual = _closeness_size_provider_result(fnx.closeness_centrality, owner)
    assert actual == expected
    assert actual[1] == [3, 4, 5]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("location", ["graph", "node", "edge"])
def test_closeness_public_native_reverse_copy_hooks_are_preserved(graph_type, location):
    trace = []

    class CannotCopy:
        def __deepcopy__(self, memo):
            trace.append(location)
            raise RuntimeError("metadata cannot be copied")

    graph = getattr(fnx, graph_type)()
    graph.add_edge(0, 1)
    if location == "graph":
        attrs = graph.graph
    elif location == "node":
        attrs = graph.nodes[0]
    elif graph.is_multigraph():
        attrs = graph[0][1][0]
    else:
        attrs = graph[0][1]
    attrs["payload"] = CannotCopy()
    with pytest.raises(RuntimeError, match="^metadata cannot be copied$"):
        fnx.closeness_centrality(graph, u="missing")
    assert trace == [location]


@pytest.mark.parametrize("distance", [None, "distance"])
@pytest.mark.parametrize("u", ["missing", []])
def test_closeness_public_source_validation_matches_search(distance, u):
    graph = nx.DiGraph([(0, 1)])
    with pytest.raises(Exception) as expected:
        nx.closeness_centrality(graph, u=u, distance=distance)
    with pytest.raises(type(expected.value)) as actual:
        fnx.closeness_centrality(graph, u=u, distance=distance)
    assert actual.value.args == expected.value.args
