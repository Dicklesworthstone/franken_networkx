"""Parity coverage for all_pairs_shortest_path(_length) iterator contract.

Bead franken_networkx-pnrd: both wrappers must return generators of
(source, mapping) pairs, matching upstream NetworkX's public surface,
rather than plain dicts.
"""

import types
import sys
import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


_NATIVE_STREAM_ALL_PAIRS = {
    "all_pairs_shortest_path": "single_source_shortest_path",
    "all_pairs_shortest_path_length": "single_source_shortest_path_length",
    "all_pairs_dijkstra": "single_source_dijkstra",
    "all_pairs_dijkstra_path": "single_source_dijkstra_path",
    "all_pairs_dijkstra_path_length": "single_source_dijkstra_path_length",
}


@pytest.mark.parametrize("weight", ["weight", "cost"])
@pytest.mark.parametrize("cutoff", [None, 2])
def test_native_stream_all_pairs_source_length_preserves_multigraph_row_order(weight, cutoff):
    graphs = [module.MultiGraph() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from([4, 2, 0, 1, 3, 5])
        for (u, v), value in zip([(4, 1), (4, 2), (1, 3), (2, 3), (3, 0)],
                                 [1, 1.0, 1, 1.0, 0.25]):
            graph.add_edge(u, v, **{weight: value})
            graph.add_edge(u, v, **{weight: float(value)})
    expected = nx.single_source_dijkstra_path_length(graphs[1], 0, weight=weight, cutoff=cutoff)
    actual = fnx.single_source_dijkstra_path_length(graphs[0], 0, weight=weight, cutoff=cutoff)
    assert list(actual.items()) == list(expected.items())
    assert [type(value) for value in actual.values()] == [type(value) for value in expected.values()]
    for graph in graphs:
        graph[1][3][0][weight] = 0.5
    expected = nx.single_source_dijkstra_path_length(graphs[1], 0, weight=weight, cutoff=cutoff)
    actual = fnx.single_source_dijkstra_path_length(graphs[0], 0, weight=weight, cutoff=cutoff)
    assert list(actual.items()) == list(expected.items())
    assert [type(value) for value in actual.values()] == [type(value) for value in expected.values()]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _NATIVE_STREAM_ALL_PAIRS)
@pytest.mark.parametrize("change", ["edge-add", "edge-remove", "weight-change"])
def test_native_stream_all_pairs_observes_changes_between_yields(kind, name, change):
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(5))
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (1, 4)], weight=1)
    actual = getattr(fnx, name)(graphs[0])
    expected = getattr(nx, name)(graphs[1])
    first = next(actual)
    assert _private_all_pairs_contract([first], name) == (
        _private_all_pairs_contract([next(expected)], name)
    )
    first_snapshot = repr(first)
    for graph in graphs:
        if change == "edge-add":
            graph.add_edge(1, 3, weight=0.5)
        elif change == "edge-remove":
            graph.remove_edge(1, 2)
        elif graph.is_multigraph():
            graph[1][2][0]["weight"] = 4
        else:
            graph[1][2]["weight"] = 4
    assert _private_all_pairs_contract(list(actual), name) == (
        _private_all_pairs_contract(list(expected), name)
    )
    assert repr(first) == first_snapshot


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name,source_name", _NATIVE_STREAM_ALL_PAIRS.items())
def test_native_stream_all_pairs_computes_only_consumed_sources(kind, name, source_name):
    graph = getattr(fnx, kind)()
    graph.add_edges_from([(0, 1), (1, 2)])
    source_code = inspect.unwrap(getattr(fnx, source_name)).__code__
    calls = []

    def profile(frame, event, function):
        if event == "call" and frame.f_code is source_code:
            calls.append(frame.f_locals["source"])

    previous_profile = sys.getprofile()
    sys.setprofile(profile)
    try:
        rows = getattr(fnx, name)(graph)
        assert isinstance(rows, types.GeneratorType)
        assert calls == []
        assert next(rows)[0] == 0
        assert calls == [0]
        assert next(rows)[0] == 1
        assert calls == [0, 1]
        rows.close()
        assert calls == [0, 1]
    finally:
        sys.setprofile(previous_profile)


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("weight", ["weight", "cost"])
@pytest.mark.parametrize("weights", [
    (1, 1.0, 1, 1.0, 0.25),
    (0, 0.0, 1.0, 1, 0.5),
    (None, 2.0, True, False, 0.5),
])
def test_mixed_builtin_all_pairs_lengths_types_and_finalize_order(kind, mode, weight, weights):
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from([4, 2, 0, 1, 3, 5])
        for (u, v), value in zip([(4, 1), (4, 2), (1, 3), (2, 3), (3, 0)], weights):
            attrs = {} if value is None else {weight: value}
            graph.add_edge(u, v, **attrs)
            if graph.is_multigraph():
                # Equal-value alternatives retain the FIRST key's number type;
                # more expensive float keys must not taint an integer minimum.
                graph.add_edge(u, v, **{weight: float(1 if value is None else value)})
                graph.add_edge(u, v, **{weight: 9.0})
    expected = list(nx.all_pairs_dijkstra_path_length(graphs[1], weight=weight))
    with fnx.compatibility_mode(mode):
        actual = list(fnx.all_pairs_dijkstra_path_length(graphs[0], weight=weight))
        assert fnx.get_compatibility_mode() == mode
    assert _private_all_pairs_contract(actual, "all_pairs_dijkstra_path_length") == (
        _private_all_pairs_contract(expected, "all_pairs_dijkstra_path_length")
    )


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_mixed_builtin_length_only_dijkstra_uses_real_length_kernel(kind):
    graph = getattr(fnx, kind)()
    graph.add_edge("a", "b", weight=1)
    graph.add_edge("b", "c", weight=0.5)
    if graph.is_multigraph():
        graph.add_edge("a", "b", weight=2.0)
    native_calls = []

    def profile(frame, event, function):
        if event == "c_call":
            if function in (fnx._raw_all_pairs_dijkstra,
                            fnx._raw_single_source_dijkstra,
                            fnx._raw_mdg_ss_dijkstra):
                native_calls.append("paths")
            elif function is fnx._raw_all_pairs_dijkstra_path_length:
                native_calls.append("batch-lengths")
            elif function in (fnx._raw_single_source_dijkstra_path_length,
                              fnx._raw_mdg_ss_dijkstra_path_length):
                native_calls.append("lengths")

    previous_profile = sys.getprofile()
    sys.setprofile(profile)
    try:
        actual = dict(fnx.all_pairs_dijkstra_path_length(graph))
    finally:
        sys.setprofile(previous_profile)
    assert actual["a"]["c"] == 1.5
    # Length-only remains native, but the public generator must not compute
    # unconsumed sources. Each consumed source has its own typed length call.
    assert native_calls == ["lengths"] * len(graph), native_calls


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("domain", ["large-int", "fraction", "decimal"])
@pytest.mark.parametrize("cutoff", [None, 3])
def test_exact_domain_all_pairs_lengths_still_preserve_types(kind, domain, cutoff):
    from decimal import Decimal
    from fractions import Fraction

    value = {"large-int": 2**70, "fraction": Fraction(1, 3), "decimal": Decimal("0.1")}[domain]
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from([2, 0, 1, 3])
        graph.add_edge(0, 1, weight=value)
        graph.add_edge(1, 2, weight=1)
        if graph.is_multigraph():
            graph.add_edge(0, 1, weight=value + 1)
    actual = list(fnx.all_pairs_dijkstra_path_length(graphs[0], cutoff=cutoff))
    expected = list(nx.all_pairs_dijkstra_path_length(graphs[1], cutoff=cutoff))
    assert _private_all_pairs_contract(actual, "all_pairs_dijkstra_path_length") == (
        _private_all_pairs_contract(expected, "all_pairs_dijkstra_path_length")
    )


def _relabel_path_mapping(paths, mapping):
    """Map a path dictionary through a node relabeling without reordering it."""
    return {
        mapping[source]: [mapping[node] for node in path]
        for source, path in paths.items()
    }


def _relabel_all_pairs_paths(pairs, mapping):
    """Map the complete ordered all-pairs path result through ``mapping``."""
    return [
        (mapping[source], _relabel_path_mapping(paths, mapping))
        for source, paths in pairs
    ]


@pytest.mark.parametrize("graph_type", [fnx.Graph, fnx.DiGraph])
def test_shortest_path_sequences_are_equivariant_under_relabeling(graph_type):
    """Relabeling must preserve shortest-path sequence order as well as values.

    The diamond forces two equal shortest paths, while the isolate ensures the
    all-pairs iterators also retain their ordered unreachable-source row.
    """
    graph = graph_type()
    graph.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
    graph.add_node(4)
    mapping = {
        0: "source",
        1: ("left", 1),
        2: "right",
        3: ("target", 3),
        4: "isolated",
    }
    relabeled = fnx.relabel_nodes(graph, mapping)

    assert _relabel_path_mapping(
        fnx.single_source_shortest_path(graph, 0), mapping
    ) == fnx.single_source_shortest_path(relabeled, mapping[0])
    assert _relabel_all_pairs_paths(
        list(fnx.all_pairs_shortest_path(graph)), mapping
    ) == list(fnx.all_pairs_shortest_path(relabeled))
    assert [
        [mapping[node] for node in path]
        for path in fnx.all_shortest_paths(graph, 0, 3)
    ] == list(fnx.all_shortest_paths(relabeled, mapping[0], mapping[3]))

    assert {
        mapping[source]: {mapping[target]: distance for target, distance in lengths.items()}
        for source, lengths in fnx.all_pairs_shortest_path_length(graph)
    } == dict(fnx.all_pairs_shortest_path_length(relabeled))


def test_all_pairs_shortest_path_returns_generator_of_pairs():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)

    f_res = fnx.all_pairs_shortest_path(fg)
    n_res = nx.all_pairs_shortest_path(ng)

    assert isinstance(f_res, types.GeneratorType)
    assert isinstance(n_res, types.GeneratorType)

    # Source-insertion order matches upstream.
    f_pairs = list(f_res)
    n_pairs = list(n_res)
    assert [s for s, _ in f_pairs] == [s for s, _ in n_pairs]
    # Every per-source dict matches upstream.
    f_dict = dict(f_pairs)
    n_dict = dict(n_pairs)
    for src in n_dict:
        assert f_dict[src] == n_dict[src]


def test_all_pairs_shortest_path_length_returns_generator_of_pairs():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)

    f_res = fnx.all_pairs_shortest_path_length(fg)
    n_res = nx.all_pairs_shortest_path_length(ng)

    assert isinstance(f_res, types.GeneratorType)
    assert isinstance(n_res, types.GeneratorType)

    f_pairs = list(f_res)
    n_pairs = list(n_res)
    assert [s for s, _ in f_pairs] == [s for s, _ in n_pairs]
    f_dict = dict(f_pairs)
    n_dict = dict(n_pairs)
    for src in n_dict:
        assert f_dict[src] == n_dict[src]


def test_all_pairs_shortest_path_cutoff_preserved():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    f = dict(fnx.all_pairs_shortest_path(fg, cutoff=2))
    n = dict(nx.all_pairs_shortest_path(ng, cutoff=2))
    for src in n:
        # Every path within cutoff must match upstream.
        assert f[src] == n[src]


def test_all_pairs_shortest_path_directed_matches_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (4, 0)])

    assert list(fnx.all_pairs_shortest_path(fg)) == list(nx.all_pairs_shortest_path(ng))
    assert list(fnx.all_pairs_shortest_path_length(fg)) == list(
        nx.all_pairs_shortest_path_length(ng)
    )
    assert list(fnx.all_pairs_shortest_path(fg, cutoff=1)) == list(
        nx.all_pairs_shortest_path(ng, cutoff=1)
    )


def test_all_pairs_shortest_path_rejects_unknown_backend():
    fg = fnx.path_graph(3)
    with pytest.raises(ImportError):
        list(fnx.all_pairs_shortest_path(fg, backend="nonexistent"))
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        list(fnx.all_pairs_shortest_path(fg, foo="bar"))


def test_all_pairs_shortest_path_length_rejects_unknown_backend():
    fg = fnx.path_graph(3)
    with pytest.raises(ImportError):
        list(fnx.all_pairs_shortest_path_length(fg, backend="nonexistent"))
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        list(fnx.all_pairs_shortest_path_length(fg, foo="bar"))


def _networkx_distance_matrix(graph, sources, nodelist, cutoff=None):
    np = pytest.importorskip("numpy")
    matrix = np.full((len(sources), len(nodelist)), -1, dtype=np.int32)
    positions = {node: index for index, node in enumerate(nodelist)}
    for row, source in enumerate(sources):
        for target, distance in nx.single_source_shortest_path_length(
            graph, source, cutoff=cutoff
        ).items():
            matrix[row, positions[target]] = distance
    return matrix


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cutoff", [None, 2])
def test_native_stream_all_pairs_private_matrix_uses_authoritative_rows(kind, cutoff):
    np = pytest.importorskip("numpy")
    fg, ng = _private_all_pairs_twins(kind)
    sources = [2, 0, 2, 1]
    expected = _networkx_distance_matrix(ng, sources, list(ng), cutoff=cutoff)
    actual = fnx.shortest_path_length_matrix(fg, sources, cutoff=cutoff)
    assert actual.dtype == np.int32
    assert actual.shape == (len(sources), len(ng))
    np.testing.assert_array_equal(actual, expected)
    assert not actual.flags.writeable
    with pytest.raises(ValueError):
        actual.setflags(write=True)
    for graph in (fg, ng):
        _private_all_pairs_add_edge(graph, 1, 3)
    expected = _networkx_distance_matrix(ng, list(ng), list(ng), cutoff=cutoff)
    np.testing.assert_array_equal(fnx.shortest_path_length_matrix(fg, cutoff=cutoff), expected)
    assert fnx.shortest_path_length_matrix(fg, []).shape == (0, len(fg))
    with pytest.raises(fnx.NodeNotFound, match="Source 99 is not in G"):
        fnx.shortest_path_length_matrix(fg, [0, 99], cutoff=cutoff)


@pytest.mark.parametrize(
    ("fnx_type", "nx_type", "edges"),
    [
        (fnx.Graph, nx.Graph, [(0, 1), (1, 2), (3, 4)]),
        (fnx.DiGraph, nx.DiGraph, [(0, 1), (1, 2), (3, 4)]),
        (fnx.MultiGraph, nx.MultiGraph, [(0, 1), (0, 1), (1, 2), (3, 4)]),
        (fnx.MultiDiGraph, nx.MultiDiGraph, [(0, 1), (0, 1), (1, 2), (3, 4)]),
    ],
)
@pytest.mark.parametrize("cutoff", [None, 0, 1, 3])
def test_shortest_path_length_matrix_matches_networkx(
    fnx_type, nx_type, edges, cutoff
):
    np = pytest.importorskip("numpy")
    fg = fnx_type()
    ng = nx_type()
    for graph in (fg, ng):
        graph.add_nodes_from(range(6))
        graph.add_edges_from(edges)
    sources = [2, 3, 2, 5]
    actual = fnx.shortest_path_length_matrix(fg, sources, cutoff=cutoff)
    expected = _networkx_distance_matrix(ng, sources, list(ng), cutoff=cutoff)

    assert actual.dtype == np.int32
    assert actual.shape == (len(sources), len(ng))
    assert not actual.flags.writeable
    np.testing.assert_array_equal(actual, expected)


def test_shortest_path_length_matrix_defaults_views_and_edge_cases():
    np = pytest.importorskip("numpy")
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)

    full = fnx.shortest_path_length_matrix(fg)
    expected = _networkx_distance_matrix(ng, list(ng), list(ng))
    np.testing.assert_array_equal(full, expected)

    view = fg.subgraph([1, 2, 3, 4])
    nx_view = ng.subgraph([1, 2, 3, 4])
    view_matrix = fnx.shortest_path_length_matrix(view, [4, 1], cutoff=2)
    view_expected = _networkx_distance_matrix(
        nx_view, [4, 1], list(nx_view), cutoff=2
    )
    np.testing.assert_array_equal(view_matrix, view_expected)

    negative = fnx.shortest_path_length_matrix(fg, [2], cutoff=-1)
    np.testing.assert_array_equal(negative, np.array([[-1, -1, 0, -1, -1, -1]]))
    assert fnx.shortest_path_length_matrix(fg, []).shape == (0, len(fg))
    assert fnx.shortest_path_length_matrix(fnx.Graph()).shape == (0, 0)

    with pytest.raises(fnx.NodeNotFound, match="Source 99 is not in G"):
        fnx.shortest_path_length_matrix(fg, [99])


_REVERSE_ALL_PAIRS = (
    "all_pairs_shortest_path",
    "all_pairs_shortest_path_length",
)


def _reverse_all_pairs_graphs(graph_type):
    graphs = [getattr(lib, graph_type)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(["sink", ("left", 1), 9, "source", "isolate"])
        graph.add_edges_from([
            (("left", 1), "sink"), (9, "sink"),
            ("source", ("left", 1)), ("source", 9),
            ("source", "source"), (("left", 1), "sink"),
        ])
    return graphs


def _reverse_all_pairs_ordered(result):
    return [(source, list(row.items())) for source, row in result]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
@pytest.mark.parametrize("cutoff", [None, 0, 1, 2, -1, 1.5, float("inf"), float("nan")])
def test_reverse_all_pairs_order_cutoff_and_ties(graph_type, name, cutoff):
    fg, ng = _reverse_all_pairs_graphs(graph_type)
    actual = getattr(fnx, name)(fg.reverse(copy=False), cutoff=cutoff)
    expected = getattr(nx, name)(ng.reverse(copy=False), cutoff=cutoff)
    assert isinstance(actual, types.GeneratorType)
    assert _reverse_all_pairs_ordered(actual) == _reverse_all_pairs_ordered(expected)
    assert list(fg.edges()) == list(ng.edges())


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
def test_reverse_all_pairs_only_consumed_rows_use_native_bfs(graph_type, name, monkeypatch):
    fg, ng = _reverse_all_pairs_graphs(graph_type)
    calls = []
    copies = []
    bfs = fnx._bfs_edges_raw
    materialize = fnx._materialize_view

    def observed_bfs(graph, source, **kwargs):
        calls.append((graph, source, kwargs))
        return bfs(graph, source, **kwargs)

    def observed_materialize(view):
        copies.append(view)
        return materialize(view)

    monkeypatch.setattr(fnx, "_bfs_edges_raw", observed_bfs)
    monkeypatch.setattr(fnx, "_materialize_view", observed_materialize)
    actual = getattr(fnx, name)(fg.reverse(copy=False), cutoff=2)
    expected = getattr(nx, name)(ng.reverse(copy=False), cutoff=2)
    assert calls == copies == []
    first = next(actual)
    assert list(first[1].items()) == list(next(expected)[1].items())
    assert len(calls) == 1
    assert calls[0] == (fg, "sink", {"reverse": True, "depth_limit": 2})
    second = next(actual)
    assert list(second[1].items()) == list(next(expected)[1].items())
    assert len(calls) == 2
    assert calls[1][0] is fg
    assert copies == []
    actual.close()
    expected.close()
    assert len(calls) == 2


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
def test_reverse_all_pairs_edge_mutation_between_yields(graph_type, name):
    fg = getattr(fnx, graph_type)([(0, 1), (1, 2), (2, 3)])
    ng = getattr(nx, graph_type)([(0, 1), (1, 2), (2, 3)])
    actual = getattr(fnx, name)(fg.reverse(copy=False))
    expected = getattr(nx, name)(ng.reverse(copy=False))
    first = next(actual)
    assert first == next(expected)
    first_snapshot = repr(first)
    for graph in (fg, ng):
        graph.add_edge(3, 1)
    second = next(actual)
    oracle_second = next(expected)
    assert second[0] == oracle_second[0] == 1
    assert list(second[1].items()) == list(oracle_second[1].items())
    assert 3 in second[1]
    for graph in (fg, ng):
        graph.remove_edge(1, 2)
        graph.add_edge(0, 2)
    assert _reverse_all_pairs_ordered(actual) == _reverse_all_pairs_ordered(expected)
    assert repr(first) == first_snapshot
    assert list(fg.edges()) == list(ng.edges())


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
def test_reverse_all_pairs_discovery_objects_and_independent_results(graph_type, name):
    graphs = [getattr(lib, graph_type)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(6))
        graph.add_edges_from([(0, 2.0), (0, 1.0), (1.0, 3), (2, 3.0), (3.0, 4)])
    outputs = [list(getattr(lib, name)(graph.reverse(copy=False)))
               for lib, graph in zip((fnx, nx), graphs)]
    assert _reverse_all_pairs_ordered(outputs[0]) == _reverse_all_pairs_ordered(outputs[1])
    for (fs, fr), (ns, nr) in zip(*outputs):
        assert type(fs) is type(ns)
        assert [(key, type(key)) for key in fr] == [(key, type(key)) for key in nr]
        if name == "all_pairs_shortest_path":
            for key in nr:
                assert [(node, type(node)) for node in fr[key]] == [
                    (node, type(node)) for node in nr[key]
                ]
    rows = [row for _, row in outputs[0]]
    assert len({id(row) for row in rows}) == len(rows)
    if name == "all_pairs_shortest_path":
        paths = [path for row in rows for path in row.values()]
        assert len({id(path) for path in paths}) == len(paths)
        rows[4][0].append("caller-write")
        assert "caller-write" not in rows[3][0]
    rows[0]["caller-write"] = "value"
    assert all("caller-write" not in row for row in rows[1:])


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
@pytest.mark.parametrize("shape", ["filtered", "nested", "conversion", "subclass", "private"])
def test_reverse_all_pairs_ineligible_roots_keep_safe_fallback(graph_type, name, shape):
    fg, ng = _reverse_all_pairs_graphs(graph_type)
    views = []
    for lib, graph in zip((fnx, nx), (fg, ng)):
        if shape == "filtered":
            graph = graph.subgraph(["sink", 9, "source", "isolate"])
        elif shape == "nested":
            graph = graph.reverse(copy=False)
            # reverse(copy=False) on fnx's reverse view unwraps its root.
            # Build an actual second view to exercise the nested-root guard.
            views.append(
                fnx._reverse_directed_view_for(graph) if lib is fnx
                else nx.classes.graphviews.reverse_view(graph)
            )
            continue
        elif shape == "conversion":
            graph = graph.to_undirected(as_view=True).to_directed(as_view=True)
        elif shape == "subclass":
            graph = type("CustomDirected", (getattr(lib, graph_type),), {})(graph)
        else:
            graph._succ = {node: {} for node in graph}
            graph._pred = {node: {} for node in graph}
        views.append(graph.reverse(copy=False))
    assert fnx._reverse_view_root(views[0]) is None
    assert _reverse_all_pairs_ordered(getattr(fnx, name)(views[0])) == (
        _reverse_all_pairs_ordered(getattr(nx, name)(views[1]))
    )


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
def test_reverse_all_pairs_empty_and_namespace_routes(graph_type, name):
    import franken_networkx.algorithms.shortest_paths.unweighted as unweighted

    function = getattr(fnx, name)
    assert getattr(nx.algorithms, name) is getattr(nx, name)
    assert getattr(unweighted, name) is function
    assert getattr(fnx.algorithms, name) is function
    assert list(function(getattr(fnx, graph_type)().reverse(copy=False))) == []
    fg, ng = _reverse_all_pairs_graphs(graph_type)
    assert _reverse_all_pairs_ordered(getattr(unweighted, name)(fg.reverse(copy=False))) == (
        _reverse_all_pairs_ordered(getattr(nx, name)(ng.reverse(copy=False)))
    )


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
def test_reverse_all_pairs_backend_errors_do_not_start_traversal(graph_type, name, monkeypatch):
    fg, _ = _reverse_all_pairs_graphs(graph_type)
    calls = []
    bfs = fnx._bfs_edges_raw

    def observed_bfs(*args, **kwargs):
        calls.append(args)
        return bfs(*args, **kwargs)

    monkeypatch.setattr(fnx, "_bfs_edges_raw", observed_bfs)
    function = getattr(fnx, name)
    with pytest.raises(ImportError):
        list(function(fg.reverse(copy=False), backend="nonexistent"))
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        list(function(fg.reverse(copy=False), foo="bar"))
    assert calls == []


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
@pytest.mark.parametrize("mutation", ["add", "remove", "replace"])
def test_reverse_all_pairs_live_source_iterator_mutation_errors(graph_type, name, mutation):
    graphs = [getattr(lib, graph_type)([(0, 1), (1, 2), (2, 3)])
              for lib in (fnx, nx)]
    iterators = [getattr(lib, name)(graph.reverse(copy=False))
                 for lib, graph in zip((fnx, nx), graphs)]
    assert next(iterators[0]) == next(iterators[1])
    for graph in graphs:
        if mutation == "add":
            graph.add_node(7)
        elif mutation == "remove":
            graph.remove_node(3)
        else:
            graph.remove_node(0)
            graph.add_node(7)
    outcomes = []
    for iterator in iterators:
        rows = []
        with pytest.raises(RuntimeError) as error:
            while True:
                source, row = next(iterator)
                rows.append((source, list(row.items())))
        outcomes.append((rows, str(error.value)))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
def test_reverse_all_pairs_reads_graph_on_first_next_not_generator_creation(graph_type, name):
    graphs = [getattr(lib, graph_type)([(0, 1), (1, 2)]) for lib in (fnx, nx)]
    iterators = [getattr(lib, name)(graph.reverse(copy=False))
                 for lib, graph in zip((fnx, nx), graphs)]
    for graph in graphs:
        graph.add_edge(3, 1)
    assert _reverse_all_pairs_ordered(iterators[0]) == _reverse_all_pairs_ordered(iterators[1])


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
@pytest.mark.parametrize("seed", [1951, 1952, 1953, 1954])
def test_reverse_all_pairs_random_row_order_and_read_only(graph_type, name, seed):
    ng = nx.gnp_random_graph(18, .18, seed=seed, directed=True)
    if graph_type == "MultiDiGraph":
        ng = nx.MultiDiGraph(ng)
        ng.add_edges_from(list(ng.edges())[:8])
    fg = getattr(fnx, graph_type)()
    fg.add_nodes_from(ng)
    fg.add_edges_from(ng.edges(keys=True) if ng.is_multigraph() else ng.edges())
    before = list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges())
    actual = _reverse_all_pairs_ordered(getattr(fnx, name)(fg.reverse(copy=False)))
    expected = _reverse_all_pairs_ordered(getattr(nx, name)(ng.reverse(copy=False)))
    assert actual == expected
    assert list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges()) == before


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_ALL_PAIRS)
def test_native_stream_all_pairs_concrete_graphs_use_source_native_route(graph_type, name):
    graphs = [getattr(lib, graph_type)([(0, 2), (0, 1), (2, 3), (1, 3)])
              for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_node(4)
    calls = []
    source_raw = getattr(fnx, "_raw_" + _NATIVE_STREAM_ALL_PAIRS[name])
    batch_raw = getattr(fnx, "_raw_" + name)

    def profile(frame, event, function):
        if event == "c_call":
            if function is source_raw:
                calls.append("source")
            elif function is batch_raw:
                calls.append("batch")

    previous_profile = sys.getprofile()
    sys.setprofile(profile)
    try:
        actual = _reverse_all_pairs_ordered(getattr(fnx, name)(graphs[0], cutoff=2))
    finally:
        sys.setprofile(previous_profile)
    expected = _reverse_all_pairs_ordered(getattr(nx, name)(graphs[1], cutoff=2))
    assert actual == expected
    assert calls == ["source"] * len(graphs[0])


_PRIVATE_ALL_PAIRS_VIEWS = [
    (kind, view)
    for kind in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("plain", "subgraph", "restricted", "conversion", "edge_subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")]
_PRIVATE_UNWEIGHTED_PAIRS = (
    "all_pairs_shortest_path", "all_pairs_shortest_path_length",
)
_PRIVATE_TARGET_SURFACES = (
    "single_target_shortest_path", "single_target_shortest_path_length",
)
_PRIVATE_WEIGHTED_SURFACES = (
    "dijkstra_predecessor_and_distance", "multi_source_dijkstra",
    "multi_source_dijkstra_path", "multi_source_dijkstra_path_length",
)


def _private_weighted_result_contract(value):
    if isinstance(value, dict):
        return [(key, type(key), _private_weighted_result_contract(item))
                for key, item in value.items()]
    if isinstance(value, (list, tuple)):
        return type(value), [_private_weighted_result_contract(item) for item in value]
    return value, type(value)


def _private_weighted_node_identity(actual, expected):
    if isinstance(expected, dict):
        assert all(a is e for a, e in zip(actual, expected))
        for node in expected:
            _private_weighted_node_identity(actual[node], expected[node])
    elif isinstance(expected, list):
        assert all(a is e for a, e in zip(actual, expected))
    elif isinstance(expected, tuple):
        for a, e in zip(actual, expected):
            _private_weighted_node_identity(a, e)


@pytest.mark.parametrize("kind,view", _PRIVATE_ALL_PAIRS_VIEWS)
@pytest.mark.parametrize("name", _PRIVATE_WEIGHTED_SURFACES)
@pytest.mark.parametrize("weight,cutoff", [(None, None), ("weight", None), ("cost", 3)])
def test_private_weighted_views_order_types_identity_and_literal(kind, view, name, weight, cutoff):
    from franken_networkx._fnx import cgse

    graphs = _private_all_pairs_twins(kind)
    fg, ng = [_private_all_pairs_view(module, graph, view)
              for module, graph in zip((fnx, nx), graphs)]
    source = float(3 if view == "reverse" else 0)
    args = (source,) if name == "dijkstra_predecessor_and_distance" else ([source],)
    actual, witnesses = cgse.collect_witnesses(
        lambda: getattr(fnx, name)(fg, *args, weight=weight, cutoff=cutoff)
    )
    expected = getattr(nx, name)(ng, *args, weight=weight, cutoff=cutoff)
    assert _private_weighted_result_contract(actual) == _private_weighted_result_contract(expected)
    _private_weighted_node_identity(actual, expected)
    if name == "dijkstra_predecessor_and_distance":
        distances = actual[1]
    elif name == "multi_source_dijkstra":
        distances = actual[0]
    else:
        distances = actual
    nodes = [3, 2, 0] if view == "reverse" else [0, 2, 3]
    increments = [1, 1] if weight is None else [2, 4] if weight == "weight" else [3, 5]
    if view == "reverse":
        increments.reverse()
    literal = {source: [source] if name.endswith("_path") else 0}
    for depth, distance in enumerate((increments[0], sum(increments)), 1):
        if cutoff is None or distance <= cutoff:
            literal[nodes[depth]] = nodes[:depth + 1] if name.endswith("_path") else distance
    assert list(distances.items()) == list(literal.items())
    assert witnesses == [], "Private weighted rows cannot fabricate native witnesses"


@pytest.mark.parametrize("kind,view", _PRIVATE_ALL_PAIRS_VIEWS)
@pytest.mark.parametrize("name", _PRIVATE_WEIGHTED_SURFACES)
def test_private_weighted_ordinary_routes_keep_real_native_calls(kind, view, name, monkeypatch):
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(4))
        graph.add_edges_from([(0, 2, {"weight": 2}), (2, 3, {"weight": 4})])
    fg, ng = [_private_all_pairs_view(module, graph, view)
              for module, graph in zip((fnx, nx), graphs)]
    source = 3 if view == "reverse" else 0
    args = (source,) if name == "dijkstra_predecessor_and_distance" else ([source],)
    calls = []
    if name == "dijkstra_predecessor_and_distance":
        owner, raw_name = fnx, "_raw_dijkstra_predecessor_and_distance"
    elif name == "multi_source_dijkstra_path_length":
        owner, raw_name = fnx._fnx, "multi_source_dijkstra_path_length"
    else:
        owner, raw_name = fnx, "_raw_multi_source_dijkstra"
    raw = getattr(owner, raw_name)

    def observed_raw(*raw_args, **raw_kwargs):
        calls.append(raw_args[0])
        return raw(*raw_args, **raw_kwargs)

    monkeypatch.setattr(owner, raw_name, observed_raw)
    actual = getattr(fnx, name)(fg, *args, weight="weight")
    expected = getattr(nx, name)(ng, *args, weight="weight")
    assert _private_weighted_result_contract(actual) == _private_weighted_result_contract(expected)
    if kind in ("Graph", "DiGraph") and view in ("plain", "reverse"):
        assert len(calls) == 1, "Ordinary simple graphs must retain their native kernel"


@pytest.mark.parametrize("kind,view", [(kind, "plain") for kind in
                         ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")] +
                         [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")])
@pytest.mark.parametrize("name", _PRIVATE_WEIGHTED_SURFACES)
@pytest.mark.parametrize("case", ["missing_source", "malformed_later_row", "negative_cycle", "hidden_callback"])
def test_private_weighted_errors_and_callback_order(kind, view, name, case):
    graphs = _private_all_pairs_twins(kind)
    source = float(3 if view == "reverse" else 0)
    if case == "malformed_later_row":
        for graph in graphs:
            rows = graph._pred if view == "reverse" else graph._adj
            rows[2] = None
    elif case == "negative_cycle":
        for graph in graphs:
            _private_all_pairs_add_edge(graph, 2, 2, weight=-1)
    if case == "missing_source":
        source = 99
    args = (source,) if name == "dijkstra_predecessor_and_distance" else ([source],)

    def outcome(module, graph):
        graph = _private_all_pairs_view(module, graph, view)
        calls = []

        def hidden_weight(u, v, data):
            calls.append((u, type(u), v, type(v), list(data)))
            return None if v == 2 else 1

        weight = hidden_weight if case == "hidden_callback" else "weight"
        try:
            result = getattr(module, name)(graph, *args, weight=weight)
        except Exception as error:
            return "error", type(error).__name__, str(error), calls
        return "result", _private_weighted_result_contract(result), calls

    assert outcome(fnx, graphs[0]) == outcome(nx, graphs[1])


@pytest.mark.parametrize("kind,view", _PRIVATE_ALL_PAIRS_VIEWS)
@pytest.mark.parametrize("case", ["two_sources", "target_alias", "source_is_target", "unreachable_target", "empty_sources"])
def test_private_weighted_multi_source_target_and_source_order(kind, view, case):
    graphs = _private_all_pairs_twins(kind)
    source = float(3 if view == "reverse" else 0)
    target = float(0 if view == "reverse" else 3)
    sources = [source]
    if case == "two_sources":
        sources = [1, source]
        target = None
    elif case == "source_is_target":
        target = source
    elif case == "unreachable_target":
        target = 1
    elif case == "empty_sources":
        sources = []

    def outcome(module, graph):
        graph = _private_all_pairs_view(module, graph, view)
        try:
            result = module.multi_source_dijkstra(graph, sources, target=target)
        except Exception as error:
            return "error", type(error).__name__, str(error)
        if target is not None:
            assert result[1][-1] is target
        return "result", _private_weighted_result_contract(result)

    assert outcome(fnx, graphs[0]) == outcome(nx, graphs[1])


@pytest.mark.parametrize("kind,view", _PRIVATE_ALL_PAIRS_VIEWS)
@pytest.mark.parametrize("name", _PRIVATE_TARGET_SURFACES)
@pytest.mark.parametrize("cutoff", [None, 0, 1.5, -1, float("nan")])
def test_private_target_order_identity_cutoff_and_literal(kind, view, name, cutoff):
    from franken_networkx._fnx import cgse

    graphs = _private_all_pairs_twins(kind)
    fg, ng = [_private_all_pairs_view(module, graph, view)
              for module, graph in zip((fnx, nx), graphs)]
    target = float(0 if view == "reverse" else 3)
    actual, witnesses = cgse.collect_witnesses(
        lambda: getattr(fnx, name)(fg, target, cutoff=cutoff)
    )
    expected = getattr(nx, name)(ng, target, cutoff=cutoff)
    assert _private_all_pairs_contract([(target, actual)], name) == \
        _private_all_pairs_contract([(target, expected)], name)
    assert all(a is e for a, e in zip(actual, expected))
    if name == "single_target_shortest_path":
        for node in expected:
            assert all(a is e for a, e in zip(actual[node], expected[node]))
            assert actual[node][-1] is target
    nodes = [0, 2, 3] if view == "reverse" else [3, 2, 0]
    literal = {target: [target] if name.endswith("_path") else 0}
    for depth, node in enumerate(nodes[1:], 1):
        if cutoff is None or cutoff > depth - 1:
            literal[node] = list(reversed(nodes[:depth + 1])) if name.endswith("_path") else depth
    assert list(actual.items()) == list(literal.items())
    assert witnesses == [], "Private target rows cannot fabricate native witnesses"


@pytest.mark.parametrize("kind,view", _PRIVATE_ALL_PAIRS_VIEWS)
@pytest.mark.parametrize("name", _PRIVATE_TARGET_SURFACES)
def test_private_target_ordinary_native_controls(kind, view, name):
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(4))
        graph.add_edges_from([(0, 2), (2, 3)])
    fg, ng = [_private_all_pairs_view(module, graph, view)
              for module, graph in zip((fnx, nx), graphs)]
    target = 0 if view == "reverse" else 3
    actual = getattr(fnx, name)(fg, target, cutoff=2)
    expected = getattr(nx, name)(ng, target, cutoff=2)
    assert _private_all_pairs_contract([(target, actual)], name) == \
        _private_all_pairs_contract([(target, expected)], name)


@pytest.mark.parametrize("kind,view", [(kind, "plain") for kind in
                         ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")] +
                         [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")])
@pytest.mark.parametrize("name", _PRIVATE_TARGET_SURFACES)
@pytest.mark.parametrize("case", ["missing_row", "invalid_row", "later_invalid", "all_seen_invalid"])
def test_private_target_malformed_rows_match_live_oracle(kind, view, name, case):
    graphs = _private_all_pairs_twins(kind)
    target = float(0 if view == "reverse" else 3)
    for graph in graphs:
        rows = graph._adj if view == "reverse" or not graph.is_directed() else graph._pred
        if case == "missing_row":
            rows.pop(target)
        elif case == "invalid_row":
            rows[target] = None
        elif case == "later_invalid":
            rows[2] = None
        else:
            rows[target] = {float(node): {} for node in range(4) if node != target}
            rows[1] = None  # Both walks stop once all nodes were seen, before reading this row.

    def outcome(module, graph):
        graph = _private_all_pairs_view(module, graph, view)
        try:
            result = getattr(module, name)(graph, target)
        except Exception as error:
            return "error", type(error).__name__, str(error)
        return "result", _private_all_pairs_contract([(target, result)], name)

    assert outcome(fnx, graphs[0]) == outcome(nx, graphs[1])


_PRIVATE_DIJKSTRA_PAIRS = (
    "all_pairs_dijkstra", "all_pairs_dijkstra_path", "all_pairs_dijkstra_path_length",
)
_PRIVATE_BELLMAN_PAIRS = (
    "all_pairs_bellman_ford_path", "all_pairs_bellman_ford_path_length",
)
_PRIVATE_PAIRS_SURFACES = (
    *_PRIVATE_UNWEIGHTED_PAIRS, *_PRIVATE_DIJKSTRA_PAIRS,
    *_PRIVATE_BELLMAN_PAIRS, "shortest_path", "shortest_path_length",
)
_PRIVATE_PAIRS_CONFIGS = [
    (name, {"cutoff": cutoff})
    for name in _PRIVATE_UNWEIGHTED_PAIRS for cutoff in (None, -1, 1, 1.5)
] + [
    (name, {"weight": weight, "cutoff": cutoff})
    for name in _PRIVATE_DIJKSTRA_PAIRS
    for weight in (None, "weight", "cost") for cutoff in (None, 1, 5)
] + [
    (name, {"weight": weight})
    for name in _PRIVATE_BELLMAN_PAIRS for weight in (None, "weight", "cost")
] + [
    (name, {"weight": weight, "method": method})
    for name in ("shortest_path", "shortest_path_length")
    for weight in (None, "weight", "cost") for method in ("dijkstra", "bellman-ford")
]


def _private_all_pairs_twins(kind):
    aliases = [float(node) for node in range(4)]
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(4))
        graph.add_edges_from([(0, 1), (1, 3)])  # Deliberately stale native topology.
        first, second = {"weight": 2, "cost": 3}, {"weight": 4, "cost": 5}
        edge = {0: first} if graph.is_multigraph() else first
        other = {0: second} if graph.is_multigraph() else second
        rows = {0: {aliases[2]: edge}, 1: {}, 2: {aliases[3]: other}, 3: {}}
        if graph.is_directed():
            graph._succ = rows
            graph._pred = {0: {}, 1: {}, 2: {aliases[0]: edge}, 3: {aliases[2]: other}}
        else:
            rows[2][aliases[0]] = edge
            rows[3][aliases[2]] = other
        graph._adj = rows
    return graphs


def _private_all_pairs_view(module, graph, view):
    if view == "subgraph":
        return graph.subgraph(range(4))
    if view == "restricted":
        return module.restricted_view(graph, [], [])
    if view == "conversion":
        return graph.to_undirected(as_view=True) if graph.is_directed() else graph.to_directed(as_view=True)
    if view == "edge_subgraph":
        edges = [(0, 2, 0), (2, 3, 0)] if graph.is_multigraph() else [(0, 2), (2, 3)]
        return graph.edge_subgraph(edges)
    if view == "reverse":
        return graph.reverse(copy=False)
    return graph


def _private_all_pairs_contract(pairs, name):
    def row_contract(row, paths):
        return [
            (key, type(key), [(node, type(node)) for node in value] if paths else (value, type(value)))
            for key, value in row.items()
        ]

    if name == "all_pairs_dijkstra":
        return [(source, type(source), row_contract(value[0], False), row_contract(value[1], True))
                for source, value in pairs]
    paths = name.endswith("_path") or name == "shortest_path"
    return [(source, type(source), row_contract(value, paths)) for source, value in pairs]


@pytest.mark.parametrize("kind,view", _PRIVATE_ALL_PAIRS_VIEWS)
@pytest.mark.parametrize("name,kwargs", _PRIVATE_PAIRS_CONFIGS)
def test_private_all_pairs_order_types_identity_and_literal(kind, view, name, kwargs):
    from franken_networkx._fnx import cgse

    fg, ng = _private_all_pairs_twins(kind)
    fg, ng = _private_all_pairs_view(fnx, fg, view), _private_all_pairs_view(nx, ng, view)
    expected_iterator = getattr(nx, name)(ng, **kwargs)
    actual_iterator = getattr(fnx, name)(fg, **kwargs)
    assert isinstance(actual_iterator, types.GeneratorType)
    assert isinstance(expected_iterator, types.GeneratorType)
    actual, witnesses = cgse.collect_witnesses(lambda: list(actual_iterator))
    expected = list(expected_iterator)
    assert _private_all_pairs_contract(actual, name) == _private_all_pairs_contract(expected, name)
    assert [source for source, _ in actual] == list(ng)
    paths = name.endswith("_path") or name == "shortest_path"
    for (source, value), (oracle_source, oracle_value) in zip(actual, expected):
        assert source is oracle_source
        rows = zip(value, oracle_value) if name == "all_pairs_dijkstra" else [(value, oracle_value)]
        for index, (row, oracle_row) in enumerate(rows):
            assert all(a is e for a, e in zip(row, oracle_row))
            if paths or name == "all_pairs_dijkstra" and index == 1:
                for node in oracle_row:
                    assert all(a is e for a, e in zip(row[node], oracle_row[node]))
    nodes = [3, 2, 0] if view == "reverse" else [0, 2, 3]
    weight = kwargs.get("weight")
    increments = [1, 1] if weight is None else [2, 4] if weight == "weight" else [3, 5]
    if view == "reverse":
        increments.reverse()
    cutoff = kwargs.get("cutoff")
    literal_distances, literal_paths = {nodes[0]: 0}, {nodes[0]: [nodes[0]]}
    unweighted = name in _PRIVATE_UNWEIGHTED_PAIRS
    for depth, distance in enumerate((increments[0], sum(increments)), 1):
        admitted = cutoff is None or (cutoff > depth - 1 if unweighted else distance <= cutoff)
        if admitted:
            literal_distances[nodes[depth]] = distance
            literal_paths[nodes[depth]] = nodes[:depth + 1]
    anchor = dict(actual)[nodes[0]]
    if name == "all_pairs_dijkstra":
        assert list(anchor[0].items()) == list(literal_distances.items())
        assert list(anchor[1].items()) == list(literal_paths.items())
    else:
        assert list(anchor.items()) == list((literal_paths if paths else literal_distances).items())
    assert witnesses == [], "Private-row traversal cannot fabricate native witnesses"


def _private_all_pairs_add_edge(graph, source, target, weight=1):
    attrs = {"weight": weight, "cost": weight}
    edge = {0: attrs} if graph.is_multigraph() else attrs
    graph._adj[source][target] = edge
    if graph.is_directed():
        graph._pred[target][source] = edge
    else:
        graph._adj[target][source] = edge


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_PAIRS_SURFACES)
@pytest.mark.parametrize("case", ["before_first_next", "between_yields", "later_row_error"])
def test_private_all_pairs_lazy_live_rows_and_error_timing(kind, name, case):
    fg, ng = _private_all_pairs_twins(kind)
    kwargs = {} if name in _PRIVATE_UNWEIGHTED_PAIRS else {"weight": "weight"}
    iterators = [getattr(module, name)(graph, **kwargs) for module, graph in ((fnx, fg), (nx, ng))]
    assert all(isinstance(iterator, types.GeneratorType) for iterator in iterators)
    if case == "before_first_next":
        for graph in (fg, ng):
            _private_all_pairs_add_edge(graph, 0, 3)
        actual, expected = [list(iterator) for iterator in iterators]
        assert _private_all_pairs_contract(actual, name) == _private_all_pairs_contract(expected, name)
        return
    first = [next(iterator) for iterator in iterators]
    assert _private_all_pairs_contract([first[0]], name) == _private_all_pairs_contract([first[1]], name)
    saved = repr(first)
    if case == "between_yields":
        for graph in (fg, ng):
            _private_all_pairs_add_edge(graph, 1, 3)
        actual, expected = [list(iterator) for iterator in iterators]
        assert _private_all_pairs_contract(actual, name) == _private_all_pairs_contract(expected, name)
        assert len(actual[0][1][0] if name == "all_pairs_dijkstra" else actual[0][1]) > 1
    else:
        for graph in (fg, ng):
            graph._adj[1] = None
        outcomes = []
        for iterator in iterators:
            try:
                row = next(iterator)
            except Exception as error:
                outcomes.append(("error", type(error), str(error)))
            else:
                outcomes.append(("ok", _private_all_pairs_contract([row], name)))
        assert outcomes[1][0] == "error"
        assert outcomes[0] == outcomes[1]
        for iterator in iterators:
            iterator.close()
    assert repr(first) == saved, "Later graph reads must not mutate yielded results"


_PRIVATE_PAIRS_CALLBACKS = [
    (name, {}) for name in (*_PRIVATE_DIJKSTRA_PAIRS, *_PRIVATE_BELLMAN_PAIRS)
] + [
    (name, {"method": method})
    for name in ("shortest_path", "shortest_path_length")
    for method in ("dijkstra", "bellman-ford")
]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name,kwargs", _PRIVATE_PAIRS_CALLBACKS)
@pytest.mark.parametrize("consume", ["one", "all"])
def test_private_all_pairs_callbacks_are_cold_and_only_visit_consumed_sources(kind, name, kwargs, consume):
    graphs = _private_all_pairs_twins(kind)
    observations = []
    for module, graph in zip((fnx, nx), graphs):
        calls = []

        def weight(source, target, data):
            calls.append((source, target, list(data.items())))
            return min(attrs["weight"] for attrs in data.values()) if graph.is_multigraph() else data["weight"]

        iterator = getattr(module, name)(graph, weight=weight, **kwargs)
        assert calls == [], "Constructing an all-pairs iterator must not call a weight callback"
        rows = list(iterator) if consume == "all" else [next(iterator)]
        assert calls, "The consumed positive source must perform real traversal"
        prior_calls = list(calls)
        iterator.close()
        assert calls == prior_calls
        observations.append((_private_all_pairs_contract(rows, name), calls))
    assert observations[0] == observations[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["shortest_path", "shortest_path_length"])
def test_private_all_pairs_invalid_method_precedes_malformed_view_rows(kind, name):
    graphs = _private_all_pairs_twins(kind)
    outcomes = []
    for module, graph in zip((fnx, nx), graphs):
        graph._adj[0] = None
        view = graph.subgraph(range(4))
        with pytest.raises(Exception) as error:
            getattr(module, name)(view, method="invalid")
        outcomes.append((type(error.value), str(error.value)))
    assert outcomes[1] == (ValueError, "method not supported: invalid")
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name,kwargs", [
    (name, {}) for name in _PRIVATE_BELLMAN_PAIRS
] + [(name, {"method": "bellman-ford"}) for name in ("shortest_path", "shortest_path_length")])
def test_private_all_pairs_later_negative_cycle_does_not_poison_first_source(kind, name, kwargs):
    fg, ng = _private_all_pairs_twins(kind)
    for graph in (fg, ng):
        _private_all_pairs_add_edge(graph, 1, 1, weight=-1)
    iterators = [getattr(module, name)(graph, weight="weight", **kwargs)
                 for module, graph in ((fnx, fg), (nx, ng))]
    first = [next(iterator) for iterator in iterators]
    assert _private_all_pairs_contract([first[0]], name) == _private_all_pairs_contract([first[1]], name)
    outcomes = []
    for iterator in iterators:
        with pytest.raises(nx.NetworkXUnbounded) as error:
            next(iterator)
        outcomes.append(str(error.value))
        with pytest.raises(StopIteration):
            next(iterator)
    assert outcomes[0] == outcomes[1] == "Negative cycle detected."
