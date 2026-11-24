"""NetworkX backend access to owned load and percolation centrality."""

import networkx as nx
import pytest

import franken_networkx as fnx


_QUERIES = [
    ("load_centrality", {}),
    ("load_centrality", {"weight": "weight"}),
    ("load_centrality", {"v": 1, "normalized": False}),
    ("load_centrality", {"cutoff": 2}),
    ("edge_load_centrality", {}),
    ("edge_load_centrality", {"cutoff": 0}),
    ("edge_load_centrality", {"cutoff": 2}),
    ("percolation_centrality", {}),
    ("percolation_centrality", {"weight": "weight"}),
]


def _graph(library=nx, cls_name="Graph"):
    graph = getattr(library, cls_name)()
    graph.add_nodes_from((node, {"percolation": (node + 1) / 5}) for node in range(4))
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 1), (2, 3, 1), (0, 3, 4)])
    if graph.is_multigraph():
        graph.add_edge(0, 1, weight=2)
    return graph


def _warm(graph):
    nx.convert_node_labels_to_integers(graph, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


@pytest.mark.parametrize("name,options", _QUERIES)
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["cold", "warm", "native"])
def test_backend_load_and_percolation_queries(name, options, cls_name, route):
    expected = getattr(nx, name)(_graph(nx, cls_name), backend="networkx", **options)
    graph = _graph(fnx if route == "native" else nx, cls_name)
    if route == "warm":
        _warm(graph)
    actual = getattr(nx, name)(G=graph, backend="franken_networkx", **options)
    assert actual == pytest.approx(expected)
    if isinstance(expected, dict):
        assert list(actual) == list(expected)


@pytest.mark.parametrize("name", ["load_centrality", "edge_load_centrality", "percolation_centrality"])
@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("warm", [False, True])
def test_backend_centralities_preserve_asymmetric_filtered_rows(name, cls_name, warm):
    base = _graph(nx, cls_name)
    graph = nx.subgraph_view(base, filter_edge=lambda u, v, *key: u < v)
    expected = getattr(nx, name)(graph, backend="networkx")
    if warm:
        _warm(graph)
    actual = getattr(nx, name)(graph, backend="franken_networkx")
    assert actual == expected


@pytest.mark.parametrize("name", ["load_centrality", "percolation_centrality"])
def test_backend_weight_callbacks_receive_live_edge_attributes(name):
    def query(backend):
        graph = _graph(nx, "DiGraph")
        if backend == "franken_networkx":
            _warm(graph)
        calls = []

        def weight(u, v, data):
            assert data is graph[u][v]
            calls.append((u, v))
            if len(calls) == 1:
                graph[0][3]["weight"] = 1
            return data["weight"]

        result = getattr(nx, name)(graph, weight=weight, backend=backend)
        return result, calls

    expected, expected_calls = query("networkx")
    actual, actual_calls = query("franken_networkx")
    assert actual == expected
    assert actual_calls == expected_calls


def test_backend_percolation_reads_updated_attributes_after_cached_conversion():
    graph = _graph(nx, "DiGraph")
    _warm(graph)
    graph.nodes[0]["percolation"] = 0.9
    expected = nx.percolation_centrality(graph, backend="networkx")
    assert nx.percolation_centrality(graph, backend="franken_networkx") == expected


def test_backend_percolation_keeps_extra_state_entries():
    graph = _graph(nx, "DiGraph")
    _warm(graph)
    states = {node: 0.5 for node in graph}
    states["outside"] = 5
    expected = nx.percolation_centrality(graph, states=states, backend="networkx")
    assert nx.percolation_centrality(
        graph, states=states, backend="franken_networkx"
    ) == expected


def test_backend_percolation_state_values_mutate_original_graph():
    def query(backend):
        graph = _graph(nx, "DiGraph")
        if backend == "franken_networkx":
            _warm(graph)

        class States(dict):
            def values(self):
                graph.add_edge(1, 3, weight=1)
                return super().values()

        states = States(dict.fromkeys(graph, 0.5))
        result = nx.percolation_centrality(graph, states=states, backend=backend)
        return result, graph.has_edge(1, 3)

    assert query("franken_networkx") == query("networkx")


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("route", ["native", "cold", "warm"])
@pytest.mark.parametrize("raises", [False, True])
def test_load_node_comparisons_follow_each_source_search(
    cls_name, weight, route, raises
):
    def query(library, backend=None):
        armed = changed = False
        comparisons = []
        graph = getattr(library, cls_name)()

        class Node(int):
            def __lt__(self, other):
                nonlocal changed
                if armed:
                    comparisons.append((int(self), int(other)))
                    if not changed:
                        changed = True
                        graph.add_edge(0, 2, weight=1)
                        if raises:
                            raise LookupError("node comparison changed the graph")
                return int.__lt__(self, other)

        nodes = [Node(i) for i in range(4)]
        graph.add_edges_from(
            (nodes[i], nodes[(i + 1) % 4], {"weight": 1}) for i in range(4)
        )
        if route == "warm" and backend == "franken_networkx":
            _warm(graph)
        armed = True
        try:
            result = library.load_centrality(graph, weight=weight, backend=backend)
            outcome = ("scores", list(result.items()))
        except Exception as error:
            outcome = ("error", type(error).__name__, str(error))
        finally:
            armed = False
        return outcome, comparisons, changed, list(graph.edges())

    expected = query(nx)
    actual = (
        query(fnx) if route == "native" else query(nx, backend="franken_networkx")
    )
    assert actual == expected
    if cls_name == "DiGraph":
        # Each distance is unique on a directed cycle, so labels never compare.
        assert actual[1] == []
        assert not actual[2]
        assert actual[0][0] == "scores"
    else:
        assert actual[1]
        assert actual[2]


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_load_hash_mutation_runs_outside_native_result_borrows(cls_name, weight):
    def query(library):
        armed = False
        hashes = 0
        changed = False
        graph = getattr(library, cls_name)()

        class Node(int):
            def __hash__(self):
                nonlocal hashes, changed
                if armed:
                    hashes += 1
                    # A later hash must affect the current source search, too.
                    # Change a later row without resizing the active source row.
                    if hashes == 9:
                        changed = True
                        graph.add_edge(1, 3, weight=1)
                return int.__hash__(self)

        nodes = [Node(i) for i in range(4)]
        graph.add_edges_from(
            (nodes[i], nodes[(i + 1) % 4], {"weight": 1}) for i in range(4)
        )
        armed = True
        try:
            result = library.load_centrality(graph, weight=weight)
        finally:
            armed = False
        return list(result.items()), changed, list(graph.edges())

    expected = query(nx)
    assert query(fnx) == expected
