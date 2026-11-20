"""br-r37-c1-t2gyx: regression tests for bidirectional_shortest_path
and efficiency directed-graph handling."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_bidirectional_shortest_path_digraph_matches_nx():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(0, 1), (1, 2), (2, 3)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.bidirectional_shortest_path(g, 0, 3) == nx.bidirectional_shortest_path(gx, 0, 3)


@needs_nx
def test_bidirectional_shortest_path_multidigraph_matches_nx():
    g = fnx.MultiDiGraph()
    gx = nx.MultiDiGraph()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.bidirectional_shortest_path(g, 0, 2) == nx.bidirectional_shortest_path(gx, 0, 2)


@needs_nx
def test_bidirectional_shortest_path_multigraph_tiebreak_matches_nx():
    g = fnx.MultiGraph()
    gx = nx.MultiGraph()
    for edge in [("s", "a"), ("s", "b"), ("b", "t"), ("a", "t"), ("s", "a")]:
        g.add_edge(*edge)
        gx.add_edge(*edge)

    assert fnx.bidirectional_shortest_path(g, "s", "t") == (
        nx.bidirectional_shortest_path(gx, "s", "t")
    )
    assert fnx.shortest_path(g, "s", "t") == nx.shortest_path(gx, "s", "t")


def test_bidirectional_shortest_path_undirected_unchanged():
    g = fnx.path_graph(5)
    assert fnx.bidirectional_shortest_path(g, 0, 4) == [0, 1, 2, 3, 4]


def test_efficiency_directed_raises():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.efficiency(g, 0, 2)


def test_efficiency_multidigraph_raises():
    g = fnx.MultiDiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.efficiency(g, 0, 2)


def test_efficiency_undirected_still_works():
    g = fnx.path_graph(3)
    assert fnx.efficiency(g, 0, 2) == 0.5  # 1 / distance(0,2)=2


def _path_outcome(function, graph, source, target, **kwargs):
    try:
        return ("return", function(graph, source, target, **kwargs))
    except Exception as exc:
        return ("error", type(exc), str(exc))


def _asymmetric_path_graph(library, graph_type, storage, prime=None):
    graph = getattr(library, graph_type)()
    graph.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
    if storage == "filtered":
        hidden = set()
        view = library.subgraph_view(
            graph, filter_edge=lambda u, v, *key: (u, v) not in hidden
        )
        if prime is not None:
            prime(view)
        hidden.update((u, v) for u in graph for v in graph[u] if u > v)
        return view
    if prime is not None:
        prime(graph)
    graph._adj = {
        node: {neighbor: data for neighbor, data in row.items() if node < neighbor}
        for node, row in graph._adj.items()
    }
    return graph


@pytest.mark.parametrize("library", [fnx, nx], ids=["fnx", "networkx"])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("storage", ["filtered", "assigned"])
@pytest.mark.parametrize("algorithm", [
    "bidirectional_shortest_path", "shortest_path", "shortest_path_length",
])
@pytest.mark.parametrize("source,target", [(0, 3), (3, 0), (0, 1), (0, 0), (9, 3), (0, 9)])
def test_bidirectional_queries_preserve_public_rows(
    library, graph_type, storage, algorithm, source, target
):
    actual = _asymmetric_path_graph(library, graph_type, storage)
    expected = _asymmetric_path_graph(nx, graph_type, storage)
    assert _path_outcome(getattr(fnx, algorithm), actual, source, target) == (
        _path_outcome(getattr(nx, algorithm), expected, source, target)
    )


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("storage", ["filtered", "assigned"])
@pytest.mark.parametrize("algorithm", [
    "bidirectional_shortest_path", "shortest_path", "shortest_path_length",
])
def test_bidirectional_backend_recovers_public_rows(warm, graph_type, storage, algorithm):
    def prime(graph):
        nx.number_connected_components(graph, backend="franken_networkx")

    graph = _asymmetric_path_graph(nx, graph_type, storage, prime if warm else None)
    if warm:
        assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")
    function = getattr(nx, algorithm)
    expected = _path_outcome(function, graph, 3, 0)
    assert _path_outcome(function, graph, 3, 0, backend="franken_networkx") == expected


@pytest.mark.parametrize("graph_type", [nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph])
@pytest.mark.parametrize("source,target", [(0, 3), (0, 0), (9, 3), (0, 9)])
def test_bidirectional_provider_reads_match_reference(graph_type, source, target):
    class ObservedGraph(graph_type):
        def __contains__(self, node):
            self.events.append(("contains", node))
            return super().__contains__(node)

        def is_directed(self):
            self.events.append(("directed",))
            return super().is_directed()

    graphs = [ObservedGraph(), ObservedGraph()]
    for graph in graphs:
        graph.events = []
        graph.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        graph.events.clear()
    assert _path_outcome(fnx.bidirectional_shortest_path, graphs[0], source, target) == (
        _path_outcome(nx.bidirectional_shortest_path, graphs[1], source, target)
    )
    assert graphs[0].events == graphs[1].events
