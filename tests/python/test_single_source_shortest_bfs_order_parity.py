"""Parity for ``single_source_shortest_path`` / ``_length`` BFS-order.

Bead br-r37-c1-tlrdu. fnx yielded dict keys in arbitrary Rust internal
order. nx returns the dict with keys in BFS-visit order from the
source (visiting neighbours in adjacency-dict order at each layer).
Drop-in code that iterates 'for tgt, path in single_source_shortest_path(G, src).items(): ...'
broke.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_str_graph(lib):
    g = lib.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
    return g


@needs_nx
@pytest.mark.parametrize("name", [
    "single_source_shortest_path",
    "single_source_shortest_path_length",
])
@pytest.mark.parametrize("source", ["c", "d", "a", "b", "e"])
def test_bfs_order_matches_networkx(name, source):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(getattr(fnx, name)(g, source).keys())
    n = list(getattr(nx, name)(gx, source).keys())
    assert f == n


@needs_nx
def test_path_graph_int_source_order():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.single_source_shortest_path(g, 2).keys())
    n = list(nx.single_source_shortest_path(gx, 2).keys())
    assert f == n == [2, 1, 3, 0, 4]


@needs_nx
def test_cutoff_truncates_in_bfs_order():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.single_source_shortest_path(g, "c", cutoff=1).keys())
    n = list(nx.single_source_shortest_path(gx, "c", cutoff=1).keys())
    assert f == n == ["c", "d", "b"]


@needs_nx
def test_disconnected_components_only_reachable_yielded():
    g = fnx.Graph([("a", "b"), ("c", "d")])
    gx = nx.Graph([("a", "b"), ("c", "d")])
    f = list(fnx.single_source_shortest_path(g, "a").keys())
    n = list(nx.single_source_shortest_path(gx, "a").keys())
    assert f == n == ["a", "b"]


@needs_nx
def test_values_unchanged():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.single_source_shortest_path(g, "c")
    n = nx.single_source_shortest_path(gx, "c")
    for target in n:
        assert f[target] == n[target]


@needs_nx
def test_multidigraph_successor_insertion_order_over_index_order():
    g = fnx.MultiDiGraph()
    gx = nx.MultiDiGraph()
    for graph in (g, gx):
        graph.add_nodes_from(["s", "a", "b", "c"])
        graph.add_edge("s", "b", key=0)
        graph.add_edge("s", "b", key=1)
        graph.add_edge("s", "a", key=0)
        graph.add_edge("b", "c", key=0)
        graph.add_edge("a", "c", key=0)

    f = fnx.single_source_shortest_path(g, "s")
    n = nx.single_source_shortest_path(gx, "s")
    assert list(f.items()) == list(n.items())
    assert f["c"] == ["s", "b", "c"]


@needs_nx
def test_missing_source_raises_node_not_found():
    """The fix must not regress the missing-source error path."""
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NodeNotFound):
        fnx.single_source_shortest_path(g, 99)
    with pytest.raises(fnx.NodeNotFound):
        fnx.single_source_shortest_path_length(g, 99)


# br-r37-c1-8xp4a: exact reverse views can consume the root's native BFS
# without a whole-graph copy. Ordered results and discovery object identity
# are part of the contract, not just the set of reachable nodes.
_REVERSE_SHORTEST_NAMES = (
    "single_source_shortest_path",
    "single_source_shortest_path_length",
    "single_target_shortest_path",
    "single_target_shortest_path_length",
)


def _reverse_shortest_twins(cls):
    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(["s", "a", "b", "t", "z", ("tuple", 1), 42, "isolated"])
        graph.add_edges_from([
            ("b", "s"), ("a", "s"), ("t", "b"), ("t", "a"),
            ("s", ("tuple", 1)), ("s", 42), (42, "z"),
            (("tuple", 1), "z"), ("z", "s"), ("s", "s"),
        ])
        if graph.is_multigraph():
            graph.add_edge("b", "s", key="parallel")
    return graphs


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
@pytest.mark.parametrize("cutoff", [None, 0, 1, 2, 5, -1, -5, float("inf"), float("nan")])
def test_reverse_shortest_order_cutoff_and_no_copy(cls, name, cutoff, monkeypatch):
    fg, ng = _reverse_shortest_twins(cls)
    materializations, bfs_calls = [], []
    original_materialize = fnx._materialize_view
    original_bfs = fnx._bfs_edges_raw

    def materialize(view):
        materializations.append(view)
        return original_materialize(view)

    def bfs(graph, source, **kwargs):
        bfs_calls.append((graph, source, kwargs))
        return original_bfs(graph, source, **kwargs)

    monkeypatch.setattr(fnx, "_materialize_view", materialize)
    monkeypatch.setattr(fnx, "_bfs_edges_raw", bfs)
    actual = getattr(fnx, name)(fg.reverse(copy=False), "s", cutoff=cutoff)
    expected = dict(getattr(nx, name)(ng.reverse(copy=False), "s", cutoff=cutoff))
    assert type(actual) is dict
    assert list(actual.items()) == list(expected.items())
    assert not materializations
    assert len(bfs_calls) == 1
    assert bfs_calls[0][0] is fg
    assert bfs_calls[0][2].get("reverse", False) == name.startswith("single_source")


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
def test_reverse_shortest_live_mutations_and_independent_results(cls, name):
    fg, ng = _reverse_shortest_twins(cls)
    fv, nv = fg.reverse(copy=False), ng.reverse(copy=False)
    for step in range(4):
        actual = getattr(fnx, name)(fv, "s")
        expected = dict(getattr(nx, name)(nv, "s"))
        assert list(actual.items()) == list(expected.items())
        if not name.endswith("_length"):
            assert len({id(path) for path in actual.values()}) == len(actual)
            actual["s"].append("not-a-node")
        actual.clear()
        assert list(getattr(fnx, name)(fv, "s").items()) == list(expected.items())
        for graph in (fg, ng):
            if step == 0:
                graph.remove_edge("b", "s")
                graph.add_edge("b", "s")
            elif step == 1:
                graph.remove_node("a")
                graph.add_edge("a", "s")
            elif step == 2:
                graph.add_edge("isolated", "s")
                graph.add_edge("z", "isolated")
    assert list(fg.edges()) == list(ng.edges())


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
def test_reverse_shortest_discovery_objects_match_networkx(cls, name):
    # These aliases coalesce in both graph stores but retain distinct objects
    # in their adjacency rows. Custom labels with different reprs currently
    # fail at storage, before this traversal's discovery-identity boundary.
    nodes = list(range(5))
    aliases = [float(i) for i in range(5)]
    source = float(0)
    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(nodes)
        graph.add_edges_from([(aliases[2], aliases[0]), (aliases[1], aliases[0]),
                              (aliases[3], aliases[2]), (aliases[3], aliases[1]),
                              (aliases[0], aliases[4]), (aliases[4], aliases[3])])
    actual = getattr(fnx, name)(graphs[0].reverse(copy=False), source)
    expected = dict(getattr(nx, name)(graphs[1].reverse(copy=False), source))
    assert list(actual.items()) == list(expected.items())
    assert all(a is e for a, e in zip(actual, expected))
    if not name.endswith("_length"):
        for key in expected:
            assert all(a is e for a, e in zip(actual[key], expected[key]))


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
@pytest.mark.parametrize("kind", ["filtered", "nested", "conversion", "subclass", "private"])
def test_reverse_shortest_ineligible_views_keep_semantics(cls, name, kind):
    fg, ng = _reverse_shortest_twins(cls)
    views = []
    for lib, graph in zip((fnx, nx), (fg, ng)):
        if kind == "filtered":
            graph = graph.subgraph(["s", "a", "t", "z", "isolated"])
        elif kind == "nested":
            graph = graph.reverse(copy=False)
        elif kind == "conversion":
            graph = graph.to_directed(as_view=True)
        elif kind == "private":
            # The root still has native edges, but its authoritative Python
            # rows now hide all of them. A raw-root walk would leak those edges.
            graph._succ = {node: {} for node in graph}
            graph._pred = {node: {} for node in graph}
            graph._adj = graph._succ
        else:
            subclass = type("CustomDirected", (getattr(lib, cls),), {})
            graph = subclass(graph)
        views.append(graph.reverse(copy=False))
    assert fnx._reverse_view_root(views[0]) is None
    actual = getattr(fnx, name)(views[0], "s")
    expected = dict(getattr(nx, name)(views[1], "s"))
    assert list(actual.items()) == list(expected.items())


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
@pytest.mark.parametrize("missing", ["absent", []])
def test_reverse_shortest_missing_node_error_parity(cls, name, missing):
    fg, ng = _reverse_shortest_twins(cls)
    with pytest.raises(Exception) as oracle:
        getattr(nx, name)(ng.reverse(copy=False), missing)
    with pytest.raises(Exception) as actual:
        getattr(fnx, name)(fg.reverse(copy=False), missing)
    assert type(actual.value).__name__ == type(oracle.value).__name__
    assert str(actual.value) == str(oracle.value)


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
@pytest.mark.parametrize("shape", ["isolated", "chain"])
def test_reverse_shortest_isolate_and_deep_paths(cls, name, shape):
    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(200))
        if shape == "chain":
            graph.add_edges_from((i, i + 1) for i in range(199))
    start = 199 if name.startswith("single_source") else 0
    actual = getattr(fnx, name)(graphs[0].reverse(copy=False), start)
    expected = dict(getattr(nx, name)(graphs[1].reverse(copy=False), start))
    assert list(actual.items()) == list(expected.items())
    assert len(actual) == (200 if shape == "chain" else 1)
    if shape == "chain" and not name.endswith("_length"):
        assert len({id(path) for path in actual.values()}) == 200
        actual[start].append("changed")
        assert all("changed" not in path for key, path in actual.items() if key != start)


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(8))
def test_reverse_shortest_random_tie_order_and_read_only_graph(cls, seed):
    import random

    rng = random.Random(seed + 7721)
    nodes = list(range(24))
    rng.shuffle(nodes)
    edges = [(rng.choice(nodes), rng.choice(nodes)) for _ in range(96)]
    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
        graph.graph["payload"] = {"nested": [seed]}
        graph.nodes[nodes[0]]["payload"] = [seed]
    fg, ng = graphs
    node_snapshot = list(fg.nodes(data=True))
    edge_snapshot = list(fg.edges(keys=True, data=True) if fg.is_multigraph()
                         else fg.edges(data=True))
    for name in _REVERSE_SHORTEST_NAMES:
        actual = getattr(fnx, name)(fg.reverse(copy=False), nodes[0], cutoff=seed % 4)
        expected = dict(getattr(nx, name)(ng.reverse(copy=False), nodes[0], cutoff=seed % 4))
        assert list(actual.items()) == list(expected.items())
    assert list(fg.nodes(data=True)) == node_snapshot
    assert list(fg.edges(keys=True, data=True) if fg.is_multigraph()
                else fg.edges(data=True)) == edge_snapshot
    assert fg.graph == ng.graph


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
def test_reverse_shortest_namespace_consumers_share_public_route(cls, name):
    import importlib

    fg, ng = _reverse_shortest_twins(cls)
    expected = dict(getattr(nx, name)(ng.reverse(copy=False), "s"))
    for namespace in ("franken_networkx.shortest_paths",
                      "franken_networkx.algorithms.shortest_paths",
                      "franken_networkx.algorithms.shortest_paths.unweighted"):
        routed = getattr(importlib.import_module(namespace), name)
        assert routed is getattr(fnx, name)
        assert list(routed(fg.reverse(copy=False), "s").items()) == list(expected.items())


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
def test_reverse_shortest_live_private_rows_do_not_reuse_native_cache(cls, name):
    fg, ng = _reverse_shortest_twins(cls)
    for graph in (fg, ng):
        graph._succ = {node: {} for node in graph}
        graph._pred = {node: {} for node in graph}
        graph._adj = graph._succ
    # NetworkX captures the current mapping objects when creating a view.
    # Install them first, then warm and mutate those same rows in place. Direct
    # row edits move neither native topology counters nor attribute epochs.
    fv, nv = fg.reverse(copy=False), ng.reverse(copy=False)
    getattr(fnx, name)(fv, "s")
    getattr(nx, name)(nv, "s")
    for step in range(3):
        actual = getattr(fnx, name)(fv, "s")
        expected = dict(getattr(nx, name)(nv, "s"))
        assert list(actual.items()) == list(expected.items())
        assert len(actual) == (2 if step == 1 else 1)
        for graph in (fg, ng):
            if step == 0:
                for u, v in (("s", "a"), ("a", "s")):
                    row = {"key": {"payload": [step]}} if graph.is_multigraph() else {"payload": [step]}
                    graph._succ[u][v] = row
                    graph._pred[v][u] = row
            elif step == 1:
                graph._succ["s"].clear()
                graph._succ["a"].clear()
                graph._pred["s"].clear()
                graph._pred["a"].clear()


def _private_shortest_twins(cls):
    # Native topology deliberately differs from the authoritative Python rows.
    # Shared alias objects let us check discovery identity, not merely equality.
    aliases = [float(i) for i in range(6)]
    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(6))
        graph.add_edges_from([(0, 5), (5, 0)])
        succ = {node: {} for node in graph}
        pred = {node: {} for node in graph}
        for index, (u, v) in enumerate([(0, 2), (0, 1), (2, 3), (1, 3), (3, 0), (4, 0)]):
            row = {("key", index): {"payload": [index]}} if graph.is_multigraph() else {"payload": [index]}
            succ[u][aliases[v]] = row
            if graph.is_directed():
                pred[v][aliases[u]] = row
            else:
                succ[v][aliases[u]] = row
        if graph.is_directed():
            graph._succ = succ
            graph._pred = pred
        graph._adj = succ
    return graphs


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
@pytest.mark.parametrize("cutoff", [None, 0, 1, 2, -1, -.5, .5, 1.5, float("inf"), float("nan")])
def test_private_shortest_authoritative_rows_cutoff_and_identity(cls, name, cutoff):
    import sys

    fg, ng = _private_shortest_twins(cls)
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "c_call" and getattr(arg, "__module__", None) == "franken_networkx._fnx":
            if "shortest_path" in getattr(arg, "__name__", "") or getattr(arg, "__name__", "") == "bfs_edges":
                calls.append(arg.__name__)

    expected = dict(getattr(nx, name)(ng, False, cutoff=cutoff))
    try:
        sys.setprofile(profile)
        actual = getattr(fnx, name)(fg, False, cutoff=cutoff)
    finally:
        sys.setprofile(previous)
    assert type(actual) is dict
    assert list(actual.items()) == list(expected.items())
    assert all(a is e for a, e in zip(actual, expected))
    assert next(iter(actual)) is False
    assert 5 not in actual
    assert not calls, calls
    if not name.endswith("_length"):
        for node in expected:
            assert all(a is e for a, e in zip(actual[node], expected[node]))
        assert len({id(path) for path in actual.values()}) == len(actual)


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
@pytest.mark.parametrize("scenario", ["missing_node", "missing_row", "extra_row", "bad_cutoff"])
def test_private_shortest_errors_and_adjacency_cardinality(cls, name, scenario):
    fg, ng = _private_shortest_twins(cls)
    start, cutoff = 0, None
    for graph in (fg, ng):
        rows = graph._pred if graph.is_directed() and name.startswith("single_target") else graph._adj
        if scenario == "missing_row":
            # The node exists but its row does not: preserve the oracle KeyError.
            del rows[0]
        elif scenario == "extra_row":
            # Lengths count adjacency rows, not native nodes. A foreign node
            # can be discovered through a row even if it is not in G._node.
            rows[0]["foreign"] = {}
            rows["foreign"] = {}
        elif scenario == "missing_node":
            start = "absent"
        else:
            cutoff = "not-a-depth"

    def observe(lib, graph):
        try:
            result = getattr(lib, name)(graph, start, cutoff=cutoff)
        except Exception as error:
            return ("error", type(error).__name__, str(error))
        return ("result", list(dict(result).items()))

    actual, expected = observe(fnx, fg), observe(nx, ng)
    assert actual == expected
    if scenario == "extra_row":
        assert actual[0] == "result"
        assert "foreign" in dict(actual[1])
    else:
        assert actual[0] == "error"


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
def test_private_shortest_live_rows_namespace_and_result_independence(cls, name):
    import importlib

    for namespace in ("franken_networkx", "franken_networkx.shortest_paths",
                      "franken_networkx.algorithms.shortest_paths",
                      "franken_networkx.algorithms.shortest_paths.unweighted"):
        fg, ng = _private_shortest_twins(cls)
        routed = getattr(importlib.import_module(namespace), name)
        assert routed is getattr(fnx, name)
        expected = dict(getattr(nx, name)(ng, 0))
        actual = routed(fg, 0)
        assert list(actual.items()) == list(expected.items())
        if not name.endswith("_length"):
            actual[0].append("mutated-result")
        actual.clear()
        assert list(routed(fg, 0).items()) == list(expected.items())
        for graph in (fg, ng):
            rows = graph._pred if graph.is_directed() and name.startswith("single_target") else graph._adj
            row = rows[0]
            first = next(iter(row))
            row[first] = row.pop(first)
        expected = dict(getattr(nx, name)(ng, 0))
        assert list(routed(fg, 0).items()) == list(expected.items())
        for graph in (fg, ng):
            # Direct edits do not move native topology epochs. Every call
            # must see the current mappings, including replacements.
            if graph.is_directed():
                graph._succ = {node: {} for node in graph}
                graph._pred = {node: {} for node in graph}
                graph._adj = graph._succ
            else:
                graph._adj = {node: {} for node in graph}
        assert list(routed(fg, 0).items()) == [(0, 0 if name.endswith("_length") else [0])]


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SHORTEST_NAMES)
def test_private_shortest_guard_keeps_ordinary_native_route(cls, name):
    import sys

    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(6))
        graph.add_edges_from([(0, 2), (0, 1), (2, 3), (1, 3), (3, 0), (4, 0)])
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "c_call" and getattr(arg, "__module__", None) == "franken_networkx._fnx":
            if "shortest_path" in getattr(arg, "__name__", ""):
                calls.append(arg.__name__)

    try:
        sys.setprofile(profile)
        actual = getattr(fnx, name)(graphs[0], 0)
    finally:
        sys.setprofile(previous)
    assert list(actual.items()) == list(dict(getattr(nx, name)(graphs[1], 0)).items())
    expected_native = name
    if not graphs[0].is_directed() and name == "single_target_shortest_path_length":
        expected_native = "single_source_shortest_path_length"
    assert calls == [expected_native]


# br-r37-c1-8xp4a: point-query consumers must obey the same authoritative
# private rows as the single-source/target walks above. A native graph can
# still contain an edge that the Python mappings hide, or lack visible edges.
_PRIVATE_POINT_NAMES = (
    "bidirectional_shortest_path", "shortest_path", "shortest_path_length", "has_path",
)


def _private_point_observe(lib, graph, name, source, target, **kwargs):
    try:
        result = getattr(lib, name)(graph, source, target, **kwargs)
    except Exception as error:
        return ("error", type(error).__name__, str(error))
    return ("result", type(result).__name__, result)


def _private_point_compare(fg, ng, name, source, target, **kwargs):
    actual = _private_point_observe(fnx, fg, name, source, target, **kwargs)
    expected = _private_point_observe(nx, ng, name, source, target, **kwargs)
    assert actual == expected
    if actual[0:2] == ("result", "list"):
        assert all(a is e for a, e in zip(actual[2], expected[2]))
    return actual


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
@pytest.mark.parametrize("source,target", [(False, 3.0), (4.0, False), (0, 5), (False, 0.0), (3, 2)])
def test_private_point_authoritative_rows_and_identity(cls, name, source, target):
    import sys

    fg, ng = _private_shortest_twins(cls)
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "c_call" and getattr(arg, "__module__", None) == "franken_networkx._fnx":
            if "shortest_path" in getattr(arg, "__name__", "") or getattr(arg, "__name__", "") == "has_path":
                calls.append(arg.__name__)

    try:
        sys.setprofile(profile)
        _private_point_compare(fg, ng, name, source, target)
    finally:
        sys.setprofile(previous)
    assert not calls, calls


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
def test_private_point_reverse_frontier_tie_order(cls, name):
    fg, ng = _private_shortest_twins(cls)
    for graph in (fg, ng):
        row = graph._pred[3]
        first = next(iter(row))
        row[first] = row.pop(first)
    actual = _private_point_compare(fg, ng, name, False, 3.0)
    if actual[1] == "list":
        # Forward-only BFS picks2. Bidirectional BFS expands the smaller
        # reverse frontier and picks1 in this current predecessor-row order.
        assert actual[2] == [False, 1.0, 3.0]


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
@pytest.mark.parametrize("scenario", ["missing_source_row", "missing_target_row", "foreign_bridge"])
def test_private_point_malformed_rows_preserve_exact_outcomes(cls, name, scenario):
    fg, ng = _private_shortest_twins(cls)
    for graph in (fg, ng):
        if scenario == "missing_source_row":
            del graph._adj[0]
        elif scenario == "missing_target_row":
            rows = graph._pred if graph.is_directed() else graph._adj
            del rows[3]
        else:
            row = {0: {}} if graph.is_multigraph() else {}
            graph._adj[0] = {"foreign": row}
            graph._adj["foreign"] = {3.0: row}
            if graph.is_directed():
                graph._pred["foreign"] = {False: row}
                graph._pred[3] = {"foreign": row}
            else:
                graph._adj["foreign"][False] = row
                graph._adj[3] = {"foreign": row}
    _private_point_compare(fg, ng, name, False, 3.0)


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["shortest_path", "shortest_path_length"])
@pytest.mark.parametrize("method", ["dijkstra", "bellman-ford"])
@pytest.mark.parametrize("source,target", [(False, 3.0), (0, 5), (99, 0), (0, 99), ([], 0)])
def test_private_point_unweighted_method_and_missing_nodes(cls, name, method, source, target):
    fg, ng = _private_shortest_twins(cls)
    _private_point_compare(fg, ng, name, source, target, method=method)


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
def test_private_point_live_row_edits_and_result_independence(cls, name):
    fg, ng = _private_shortest_twins(cls)
    for step in range(4):
        actual = _private_point_compare(fg, ng, name, False, 3.0)
        if actual[0:2] == ("result", "list"):
            actual[2].append("mutated-result")
            _private_point_compare(fg, ng, name, False, 3.0)
        for graph in (fg, ng):
            if step == 0:
                graph._adj[0].clear()
                if graph.is_directed():
                    graph._pred[1].pop(False)
                    graph._pred[2].pop(False)
                else:
                    graph._adj[1].pop(False)
                    graph._adj[2].pop(False)
            elif step == 1:
                row = {0: {}} if graph.is_multigraph() else {}
                graph._adj[0][3.0] = row
                reverse = graph._pred if graph.is_directed() else graph._adj
                reverse[3][False] = row
            elif step == 2:
                empty = {node: {} for node in graph}
                if graph.is_directed():
                    graph._succ = empty
                    graph._pred = {node: {} for node in graph}
                graph._adj = empty


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
def test_private_point_namespace_consumers(cls, name):
    import importlib

    fg, ng = _private_shortest_twins(cls)
    expected = _private_point_observe(nx, ng, name, False, 3.0)
    namespaces = ["franken_networkx.shortest_paths", "franken_networkx.algorithms.shortest_paths"]
    namespaces.append("franken_networkx.algorithms.shortest_paths." + (
        "unweighted" if name == "bidirectional_shortest_path" else "generic"
    ))
    for namespace in namespaces:
        result = getattr(importlib.import_module(namespace), name)(fg, False, 3.0)
        assert ("result", type(result).__name__, result) == expected
        if isinstance(result, list):
            assert all(a is e for a, e in zip(result, expected[2]))


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
@pytest.mark.parametrize("kind", ["filtered", "conversion"])
def test_private_point_view_consumers(cls, name, kind):
    fg, ng = _private_shortest_twins(cls)
    views = []
    for graph in (fg, ng):
        view = graph.subgraph([0, 1, 2, 3]) if kind == "filtered" else graph.to_directed(as_view=True)
        views.append(view)
    _private_point_compare(*views, name, False, 3.0)


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
def test_private_point_reverse_view_consumers(cls, name):
    fg, ng = _private_shortest_twins(cls)
    _private_point_compare(fg.reverse(copy=False), ng.reverse(copy=False), name, 3.0, False)


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
def test_private_point_guard_keeps_ordinary_native_route(cls, name):
    import sys

    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_edges_from([(0, 2), (0, 1), (2, 3), (1, 3)])
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "c_call" and getattr(arg, "__module__", None) == "franken_networkx._fnx":
            if "shortest_path" in getattr(arg, "__name__", "") or getattr(arg, "__name__", "") == "has_path":
                calls.append(arg.__name__)

    try:
        sys.setprofile(profile)
        _private_point_compare(*graphs, name, 0, 3)
    finally:
        sys.setprofile(previous)
    expected = "bidirectional_shortest_path" if name == "shortest_path" else name
    assert calls == [expected], calls


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
@pytest.mark.parametrize("kind", ["filtered", "conversion"])
def test_private_point_guard_keeps_ordinary_view_native_route(cls, name, kind):
    import sys

    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_edges_from([(0, 2), (0, 1), (2, 3), (1, 3)])
    views = [graph.subgraph([0, 1, 2, 3]) if kind == "filtered" else graph.to_directed(as_view=True)
             for graph in graphs]
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "c_call" and getattr(arg, "__module__", None) == "franken_networkx._fnx":
            if "shortest_path" in getattr(arg, "__name__", "") or getattr(arg, "__name__", "") == "has_path":
                calls.append(arg.__name__)

    try:
        sys.setprofile(profile)
        _private_point_compare(*views, name, 0, 3)
    finally:
        sys.setprofile(previous)
    expected = "bidirectional_shortest_path" if name == "shortest_path" else name
    assert calls == [expected], calls


@needs_nx
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_POINT_NAMES)
def test_private_point_guard_keeps_ordinary_reverse_view_native_route(cls, name):
    import sys

    graphs = [getattr(lib, cls)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_edges_from([(0, 2), (0, 1), (2, 3), (1, 3)])
    views = [graph.reverse(copy=False) for graph in graphs]
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "c_call" and getattr(arg, "__module__", None) == "franken_networkx._fnx":
            if "shortest_path" in getattr(arg, "__name__", "") or getattr(arg, "__name__", "") == "has_path":
                calls.append(arg.__name__)

    try:
        sys.setprofile(profile)
        _private_point_compare(*views, name, 3, 0)
    finally:
        sys.setprofile(previous)
    expected = "bidirectional_shortest_path" if name == "shortest_path" else name
    assert calls == [expected], calls
