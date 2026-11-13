"""Parity coverage for single_source_shortest_path(_length) missing-source error.

Bead franken_networkx-s7nb: both wrappers must raise NodeNotFound when
the source isn't in the graph, matching upstream NetworkX, instead of
silently returning an empty dict.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_single_source_shortest_path_missing_source_raises():
    fg = fnx.path_graph(3)
    ng = nx.path_graph(3)

    with pytest.raises(fnx.NodeNotFound, match="Source .* not in G"):
        fnx.single_source_shortest_path(fg, "z")
    with pytest.raises(nx.NodeNotFound, match="Source .* not in G"):
        nx.single_source_shortest_path(ng, "z")


def test_single_source_shortest_path_length_missing_source_raises():
    fg = fnx.path_graph(3)
    ng = nx.path_graph(3)

    with pytest.raises(fnx.NodeNotFound, match="Source .* is not in G"):
        fnx.single_source_shortest_path_length(fg, "z")
    with pytest.raises(nx.NodeNotFound, match="Source .* is not in G"):
        nx.single_source_shortest_path_length(ng, "z")


def test_single_source_shortest_path_valid_source_matches_networkx():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    assert fnx.single_source_shortest_path(fg, 0) == nx.single_source_shortest_path(
        ng, 0
    )
    assert fnx.single_source_shortest_path_length(
        fg, 0
    ) == dict(nx.single_source_shortest_path_length(ng, 0))


def test_single_source_shortest_path_cutoff_matches_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    assert fnx.single_source_shortest_path(
        fg, 0, cutoff=2
    ) == nx.single_source_shortest_path(ng, 0, cutoff=2)


def test_single_source_shortest_path_multigraph_matches_networkx():
    fg = fnx.MultiGraph()
    ng = nx.MultiGraph()
    edges = [(0, 1), (0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (2, 4)]
    for graph in (fg, ng):
        graph.add_edges_from(edges)

    assert fnx.single_source_shortest_path(fg, 0) == nx.single_source_shortest_path(
        ng, 0
    )
    assert fnx.single_source_shortest_path(
        fg, 0, cutoff=2
    ) == nx.single_source_shortest_path(ng, 0, cutoff=2)


def test_single_source_shortest_path_directed_matches_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (4, 0)])

    assert fnx.single_source_shortest_path(fg, 0) == nx.single_source_shortest_path(
        ng, 0
    )
    assert fnx.single_source_shortest_path_length(fg, 0) == dict(
        nx.single_source_shortest_path_length(ng, 0)
    )
    assert fnx.single_source_shortest_path(fg, 0, cutoff=1) == nx.single_source_shortest_path(
        ng, 0, cutoff=1
    )


# br-r37-c1-lqp4u: every class emits from a BFS parent table - each path its
# parent's list plus the node, one C concatenation - with Fx-hashed tables; the
# DiGraph route built an owned String path per node and ran 0.16x networkx on a
# 40x40 grid with reciprocal edges, where Graph ran 0.83x.


def _grid_edges(k=12):
    grid = nx.grid_2d_graph(k, k)
    index = {node: i for i, node in enumerate(grid)}
    return [(index[u], index[v]) for u, v in grid.edges()]


def _twins(cls, edges, reciprocal):
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, cls)()
        graph.add_nodes_from(range(len(edges) // 2, -1, -1))
        graph.add_edges_from(edges)
        if reciprocal:
            graph.add_edges_from((v, u) for u, v in edges)
        graphs.append(graph)
    return graphs


@pytest.mark.parametrize("cutoff", [None, 0, 1, 3])
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_single_source_shortest_path_order_and_objects_match_networkx(cls, cutoff):
    fg, ng = _twins(cls, _grid_edges(), reciprocal=cls in ("DiGraph", "MultiDiGraph"))
    f = fnx.single_source_shortest_path(fg, 5, cutoff=cutoff)
    n = nx.single_source_shortest_path(ng, 5, cutoff=cutoff)
    assert list(f.items()) == list(n.items())
    assert [type(k) for k in f] == [type(k) for k in n]


def test_single_source_shortest_path_on_a_reverse_view_matches_networkx():
    edges = [(0, 1), (1, 2), (2, 3), (4, 3), (3, 5), (1, 5)]
    fg, ng = fnx.DiGraph(edges), nx.DiGraph(edges)
    for source in (5, 3, 0):
        f = fnx.single_source_shortest_path(fg.reverse(copy=False), source)
        n = nx.single_source_shortest_path(ng.reverse(copy=False), source)
        assert list(f.items()) == list(n.items())


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_single_source_shortest_path_lists_are_independent(cls):
    graph = getattr(fnx, cls)()
    graph.add_edges_from((i, i + 1) for i in range(6))
    paths = fnx.single_source_shortest_path(graph, 0)
    assert len({id(path) for path in paths.values()}) == len(paths)
    paths[3].append("x")
    assert paths[4] == [0, 1, 2, 3, 4]


def test_directed_single_source_shortest_path_costs_what_the_undirected_one_does():
    """Same grid, same process: the DiGraph with reciprocal edges reaches the
    same nodes through the same rows, so it must not cost several times the
    Graph call (it cost 4.8x through the String-path kernel)."""
    import time

    edges = _grid_edges(40)
    undirected = fnx.Graph(edges)
    directed = fnx.DiGraph(edges)
    directed.add_edges_from((v, u) for u, v in edges)

    def best(fn, reps=10, rounds=7):
        fn()
        out = []
        for _ in range(rounds):
            start = time.perf_counter()
            for _ in range(reps):
                fn()
            out.append((time.perf_counter() - start) / reps)
        return min(out)

    ratio = best(lambda: fnx.single_source_shortest_path(directed, 0)) / best(
        lambda: fnx.single_source_shortest_path(undirected, 0)
    )
    assert ratio < 2.0, ratio


def _asymmetric_source_view(owner, graph_type):
    graph = getattr(owner, graph_type)()
    graph.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
    if graph.is_multigraph():
        predicate = lambda u, v, key: u < v
    else:
        predicate = lambda u, v: u < v
    return owner.subgraph_view(graph, filter_edge=predicate)


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("name", ["single_source_shortest_path_length", "predecessor"])
@pytest.mark.parametrize("source", [0, 2])
@pytest.mark.parametrize("cutoff", [None, 0, 1.5])
def test_public_source_search_preserves_asymmetric_rows(owner, graph_type, name, source, cutoff):
    reference = _asymmetric_source_view(nx, graph_type)
    graph = _asymmetric_source_view(owner, graph_type)
    options = {"cutoff": cutoff}
    if name == "predecessor":
        options["return_seen"] = True
    expected = getattr(nx, name)(reference, source, **options)
    actual = getattr(fnx, name)(graph, source, **options)
    if name == "predecessor":
        assert [list(part.items()) for part in actual] == [list(part.items()) for part in expected]
    else:
        assert list(actual.items()) == list(expected.items())


@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("name", ["single_source_shortest_path_length", "predecessor"])
@pytest.mark.parametrize("warm_cache", [False, True])
def test_public_source_backend_recovers_rows(graph_type, name, warm_cache):
    graph = _asymmetric_source_view(nx, graph_type)
    if warm_cache:
        nx.degree_centrality(graph, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    expected = getattr(nx, name)(graph, 2)
    actual = getattr(nx, name)(graph, 2, backend="franken_networkx")
    assert list(actual.items()) == list(expected.items())
    assert set(actual) == {2, 3}


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("name", ["single_source_shortest_path_length", "predecessor"])
def test_public_source_validation_does_not_read_rows(owner, name):
    class UnreadableRow(dict):
        def __iter__(self):
            raise AssertionError("a missing source must not visit adjacency")

    graph = owner.Graph()
    graph.add_nodes_from([0, 1])
    graph._adj = {0: UnreadableRow({1: {}}), 1: {0: {}}}
    with pytest.raises(fnx.NodeNotFound, match="Source missing"):
        getattr(fnx, name)(graph, "missing")


def _predecessor_cutoff_protocol_result(algorithm, owner, graph_type):
    graph = getattr(owner, graph_type)()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    trace = []

    class Cutoff:
        def __int__(self):
            raise AssertionError("a cutoff provider must not be converted")

        def __bool__(self):
            trace.append("truth")
            return True

        def __le__(self, level):
            trace.append(("compare", level))
            return level >= 2

    result = algorithm(graph, 0, cutoff=Cutoff(), return_seen=True)
    return [list(part.items()) for part in result], trace


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_public_predecessor_cutoff_runs_after_each_level(owner, graph_type):
    expected = _predecessor_cutoff_protocol_result(nx.predecessor, nx, graph_type)
    actual = _predecessor_cutoff_protocol_result(fnx.predecessor, owner, graph_type)
    assert actual == expected
    assert actual[1] == ["truth", ("compare", 1), "truth", ("compare", 2)]


@pytest.mark.parametrize("owner", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("target", [2, 3, "missing"])
@pytest.mark.parametrize("return_seen", [False, True])
def test_public_predecessor_target_forms_keep_live_rows(owner, target, return_seen):
    reference = _asymmetric_source_view(nx, "Graph")
    graph = _asymmetric_source_view(owner, "Graph")
    expected = nx.predecessor(reference, 2, target=target, return_seen=return_seen)
    actual = fnx.predecessor(graph, 2, target=target, return_seen=return_seen)
    assert actual == expected
