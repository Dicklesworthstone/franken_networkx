"""Differential + golden parity for labeled DFS and BFS/DFS pred/succ maps.

Covers ``dfs_labeled_edges`` (yields ``(u, v, direction)`` where direction
is forward/reverse/nontree) and the ``bfs_predecessors`` /
``bfs_successors`` / ``dfs_successors`` / ``dfs_predecessors`` maps. None
had a dedicated test file. All are order-deterministic.

br-r37-c1-w7wwr
"""

from __future__ import annotations

import random
import types

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_dfs_labeled_edges_matches_networkx(directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert list(fnx.dfs_labeled_edges(fg, 0)) == list(nx.dfs_labeled_edges(ng, 0))


@pytest.mark.parametrize(
    "fn", ["bfs_predecessors", "bfs_successors", "dfs_successors", "dfs_predecessors"]
)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_pred_succ_maps_match_networkx(fn, directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert dict(getattr(fnx, fn)(fg, 0)) == dict(getattr(nx, fn)(ng, 0))


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("edges", [[(0, 1), (1, 2)], []], ids=["path", "null"])
@pytest.mark.parametrize("depth_limit", [None, 1])
def test_dfs_labeled_edges_missing_source_raises_like_networkx(cls, edges, depth_limit):
    # br-r37-c1-750hp: nx yields (s, s, 'forward') and then G.neighbors(s)
    # raises NetworkXError("The node s is not in the graph." / "digraph."); fnx
    # raised KeyError from its adjacency snapshot.
    def outcome(lib):
        it = lib.dfs_labeled_edges(getattr(lib, cls)(edges), source=9, depth_limit=depth_limit)
        seen = []
        try:
            for event in it:
                seen.append(event)
        except Exception as exc:  # noqa: BLE001 - the raise is the answer
            return seen, type(exc).__name__, str(exc)
        return seen, None, None

    assert outcome(fnx) == outcome(nx)


# br-r37-c1-qnj0n: nx reads a node's row from G.neighbors when the walk
# reaches it - a LIVE row, and only the rows the walk reaches. The whole-graph
# to_dict_of_lists snapshot fnx took per call (156 ms for a depth-3 walk beside
# a 64k-node component) missed a mid-walk mutation and, on a subclass, read
# every node's row.


@pytest.mark.parametrize("directed", [False, True])
def test_dfs_labeled_edges_row_is_live_like_networkx(directed):
    def outcome(lib):
        G = (lib.DiGraph if directed else lib.Graph)([(0, 1), (1, 2), (0, 3), (3, 4)])
        walk = lib.dfs_labeled_edges(G, 0)
        seen = [next(walk), next(walk)]  # paused inside row 0, after child 1
        G.add_edge(0, 9)
        try:
            seen.extend(walk)
        except RuntimeError as exc:
            return seen, str(exc)
        return seen, None

    fnx_outcome, nx_outcome = outcome(fnx), outcome(nx)
    assert nx_outcome[1] is not None
    assert fnx_outcome == nx_outcome


@pytest.mark.parametrize("depth_limit", [None, 1, 2])
def test_dfs_labeled_edges_reads_only_reached_rows_like_networkx(depth_limit):
    def rows_read(lib):
        class Recording(lib.Graph):
            def neighbors(self, n):
                reads.append(n)
                return super().neighbors(n)

        reads = []
        G = Recording([(0, 1), (1, 2), (0, 3), (5, 6), (6, 7), (7, 5)])
        events = list(lib.dfs_labeled_edges(G, 0, depth_limit=depth_limit))
        return events, reads

    fnx_rows, nx_rows = rows_read(fnx), rows_read(nx)
    assert 5 not in nx_rows[1]
    assert fnx_rows == nx_rows


def test_goldens():
    g = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    assert list(fnx.dfs_labeled_edges(g, 0)) == list(nx.dfs_labeled_edges(ng, 0))
    assert dict(fnx.bfs_successors(g, 0)) == {0: [1], 1: [2]}
    assert dict(fnx.dfs_predecessors(g, 0)) == {1: 0, 2: 1}


_PRIVATE_TRAVERSAL_VIEWS = [
    (kind, view)
    for kind in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("plain", "subgraph", "restricted", "conversion", "edge_subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")]
_PRIVATE_TRAVERSAL_LIVE_VIEWS = [
    (kind, view) for kind, view in _PRIVATE_TRAVERSAL_VIEWS
    if view in ("plain", "subgraph", "reverse")
]
_PRIVATE_TRAVERSAL_BFS = ("bfs_edges", "bfs_tree", "bfs_predecessors", "bfs_successors")
_PRIVATE_TRAVERSAL_DFS = (
    "dfs_edges", "dfs_tree", "dfs_predecessors", "dfs_successors",
    "dfs_preorder_nodes", "dfs_postorder_nodes", "dfs_labeled_edges",
)
_PRIVATE_TRAVERSAL_NAMES = (*_PRIVATE_TRAVERSAL_BFS, *_PRIVATE_TRAVERSAL_DFS)
_PRIVATE_TRAVERSAL_GENERATORS = (
    "bfs_edges", "bfs_predecessors", "bfs_successors", "dfs_edges",
    "dfs_preorder_nodes", "dfs_postorder_nodes", "dfs_labeled_edges",
)
_PRIVATE_TRAVERSAL_CONFIGS = [
    (name, depth, reverse, False, sort)
    for name in _PRIVATE_TRAVERSAL_BFS
    for depth in (None, 0, 1.5, -1, float("nan"))
    for reverse in ((False, True) if name in ("bfs_edges", "bfs_tree") else (False,))
    for sort in (False, True)
] + [
    (name, depth, False, all_sources, sort)
    for name in _PRIVATE_TRAVERSAL_DFS
    for depth in (None, 0, 1.5, -1, float("nan"))
    for all_sources in (False, True) for sort in (False, True)
]


def _private_traversal_twins(kind, private=True):
    aliases = [float(node) for node in range(5)]
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(5))
        graph.add_edges_from([(0, 1), (1, 3)])  # Native topology is deliberately wrong.
        if not private:
            continue
        rows = {node: {} for node in range(5)}
        pred = {node: {} for node in range(5)}
        for source, target in ((0, 2), (0, 4), (2, 3), (4, 3)):
            attrs = {}
            edge = {0: attrs} if graph.is_multigraph() else attrs
            rows[source][aliases[target]] = edge
            pred[target][aliases[source]] = edge
            if not graph.is_directed():
                rows[target][aliases[source]] = edge
        graph._adj = rows
        if graph.is_directed():
            graph._succ, graph._pred = rows, pred
    return graphs


def _private_traversal_view(module, graph, view):
    if view == "subgraph":
        return graph.subgraph(range(5))
    if view == "restricted":
        return module.restricted_view(graph, [], [])
    if view == "conversion":
        return graph.to_undirected(as_view=True) if graph.is_directed() else graph.to_directed(as_view=True)
    if view == "edge_subgraph":
        edges = [(0, 2), (0, 4), (2, 3), (4, 3)]
        return graph.edge_subgraph([(*edge, 0) for edge in edges] if graph.is_multigraph() else edges)
    if view == "reverse":
        return graph.reverse(copy=False)
    return graph


def _private_traversal_typed(value):
    if isinstance(value, dict):
        return (dict, [(_private_traversal_typed(k), _private_traversal_typed(v)) for k, v in value.items()])
    if isinstance(value, (list, tuple)):
        return (type(value), [_private_traversal_typed(item) for item in value])
    return type(value), value


def _private_traversal_result(value, name):
    if name.endswith("_tree"):
        assert value.is_directed() and not value.is_multigraph()
        return _private_traversal_typed((list(value.nodes(data=True)), list(value.edges(data=True)), value.graph))
    return _private_traversal_typed(value)


def _private_traversal_finish(iterator):
    events = []
    try:
        events.extend(iterator)
    except Exception as error:
        failure = type(error), str(error)
    else:
        failure = None
    try:
        next(iterator)
    except Exception as error:
        terminal = type(error), str(error)
    else:
        raise AssertionError("Finished traversal unexpectedly resumed")
    return _private_traversal_typed(events), failure, terminal


def _private_traversal_outcome(module, graph, name, **kwargs):
    try:
        value = getattr(module, name)(graph, **kwargs)
    except Exception as error:
        return "call", type(error), str(error)
    if name in _PRIVATE_TRAVERSAL_GENERATORS:
        assert isinstance(value, types.GeneratorType)
        return "iterator", _private_traversal_finish(value)
    return "result", _private_traversal_result(value, name)


@pytest.mark.parametrize("kind,view", _PRIVATE_TRAVERSAL_VIEWS)
@pytest.mark.parametrize("name,depth,reverse,all_sources,sort", _PRIVATE_TRAVERSAL_CONFIGS)
def test_private_traversal_views_depth_order_types_and_no_native_witness(kind, view, name, depth, reverse, all_sources, sort):
    from franken_networkx._fnx import cgse

    fg, ng = _private_traversal_twins(kind)
    fg, ng = _private_traversal_view(fnx, fg, view), _private_traversal_view(nx, ng, view)
    kwargs = {"source": None if all_sources else 3 if view == "reverse" else 0, "depth_limit": depth}
    if name in ("bfs_edges", "bfs_tree"):
        kwargs["reverse"] = reverse
    if sort:
        kwargs["sort_neighbors"] = lambda neighbors: sorted(neighbors, reverse=True)
    expected = _private_traversal_outcome(nx, ng, name, **kwargs)
    actual, witnesses = cgse.collect_witnesses(lambda: _private_traversal_outcome(fnx, fg, name, **kwargs))
    assert actual == expected
    assert expected[0] != "call"
    if expected[0] == "iterator":
        assert expected[1][1] is None
    assert witnesses == [], "Private traversal must not fabricate native witnesses"
    if name == "bfs_edges" and depth is None and not reverse and not sort and view != "reverse":
        assert list(nx.bfs_edges(ng, 0)) == [(0, 2), (0, 4), (2, 3)]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_TRAVERSAL_NAMES)
@pytest.mark.parametrize("sort", [False, True])
def test_private_traversal_ordinary_native_control_unchanged(kind, name, sort):
    fg, ng = _private_traversal_twins(kind, private=False)
    kwargs = {"source": 0}
    if sort:
        kwargs["sort_neighbors"] = lambda neighbors: sorted(neighbors, reverse=True)
    assert _private_traversal_outcome(fnx, fg, name, **kwargs) == _private_traversal_outcome(nx, ng, name, **kwargs)


def _private_traversal_add_edge(graph, source, target):
    edge = {0: {}} if graph.is_multigraph() else {}
    graph._adj[source][target] = edge
    if graph.is_directed():
        graph._pred[target][source] = edge
    else:
        graph._adj[target][source] = edge


@pytest.mark.parametrize("kind,view", _PRIVATE_TRAVERSAL_LIVE_VIEWS)
@pytest.mark.parametrize("name", _PRIVATE_TRAVERSAL_GENERATORS)
@pytest.mark.parametrize("case", ["before_first_next", "unreached_row_after_yield", "held_row_after_yield"])
def test_private_traversal_lazy_live_rows_and_exhaustion(kind, view, name, case):
    graphs = _private_traversal_twins(kind)
    views = [_private_traversal_view(module, graph, view) for module, graph in zip((fnx, nx), graphs)]
    source = 3 if view == "reverse" else 0
    iterators = [getattr(module, name)(graph, source=source) for module, graph in zip((fnx, nx), views)]
    assert all(isinstance(iterator, types.GeneratorType) for iterator in iterators)
    if case == "before_first_next":
        for graph in graphs:
            _private_traversal_add_edge(graph, 0, 3)
        assert _private_traversal_finish(iterators[0]) == _private_traversal_finish(iterators[1])
        return
    first = [next(iterator) for iterator in iterators]
    assert _private_traversal_typed(first[0]) == _private_traversal_typed(first[1])
    saved = repr(first)
    for graph in graphs:
        if case == "unreached_row_after_yield":
            graph._adj[4] = None
        else:
            _private_traversal_add_edge(graph, 0, 1)
    assert _private_traversal_finish(iterators[0]) == _private_traversal_finish(iterators[1])
    assert repr(first) == saved, "Later reads must not change an already yielded value"


@pytest.mark.parametrize("kind,view", _PRIVATE_TRAVERSAL_LIVE_VIEWS)
@pytest.mark.parametrize("name", _PRIVATE_TRAVERSAL_NAMES)
@pytest.mark.parametrize("source", [99, []], ids=["missing", "unhashable"])
def test_private_traversal_missing_and_unhashable_source_error_timing(kind, view, name, source):
    graphs = _private_traversal_twins(kind)
    views = [_private_traversal_view(module, graph, view) for module, graph in zip((fnx, nx), graphs)]
    actual = _private_traversal_outcome(fnx, views[0], name, source=source)
    expected = _private_traversal_outcome(nx, views[1], name, source=source)
    assert actual == expected
    if expected[0] == "iterator":
        assert expected[1][1] is not None
    else:
        assert expected[0] == "call"


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _PRIVATE_TRAVERSAL_GENERATORS)
@pytest.mark.parametrize("consume", ["one", "all"])
def test_private_traversal_sort_callback_coldness_and_partial_consumption(kind, name, consume):
    observations = []
    for module, graph in zip((fnx, nx), _private_traversal_twins(kind)):
        calls = []

        def sort_neighbors(neighbors):
            nodes = list(neighbors)
            calls.append(_private_traversal_typed(nodes))
            return sorted(nodes, reverse=True)

        iterator = getattr(module, name)(graph, source=0, sort_neighbors=sort_neighbors)
        assert calls == [], "Constructing a traversal must not invoke the sort callback"
        events = list(iterator) if consume == "all" else [next(iterator)]
        if consume == "one" and name in ("dfs_preorder_nodes", "dfs_labeled_edges"):
            assert calls == [], "The root event precedes the first neighbor lookup"
            assert events == ([0] if name == "dfs_preorder_nodes" else [(0, 0, "forward")])
        else:
            assert calls, "Consuming the traversal must perform real neighbor lookups"
        saved = list(calls)
        iterator.close()
        assert calls == saved
        observations.append((_private_traversal_typed(events), calls))
    assert observations[0] == observations[1]
