"""A graph VIEW handed to a native kernel computes on the graph the view shows.

br-r37-c1-4rhw0: `subgraph`, `edge_subgraph`, `restricted_view`, `reverse(copy=False)`
and `to_directed` / `to_undirected(as_view=True)` return Python subclasses of the four
graph classes whose own Rust storage is EMPTY - the view answers from its parent in
Python. Wrappers that coerce first were right, but every native function reached
without coercion computed on a graph with no nodes: `is_empty(view)` was True,
`is_regular` raised "Graph has no nodes.", `bidirectional_dijkstra` raised
NodeNotFound, and the matrix exporters returned all-zero matrices. fnx-python's
`extract_graph` now swaps a view for the concrete graph it shows.

Each row calls the function on an fnx view and on the networkx view built the same
way. A kernel that read the PARENT instead of the view would fail too: every view
here drops nodes or edges, or turns them around.
"""

import random

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx
from franken_networkx import _materialize_view

# A weighted 4x4 grid with two chords and one weight-1 edge per row, so shortest
# paths depend on the weights and the views below drop different pieces of it.
EDGES = [
    (0, 1, 1.5), (1, 2, 2.5), (2, 3, 1.0), (4, 5, 2.0), (5, 6, 1.0), (6, 7, 3.5),
    (8, 9, 1.0), (9, 10, 2.25), (10, 11, 1.75), (12, 13, 2.0), (13, 14, 1.0),
    (14, 15, 2.5), (0, 4, 2.0), (4, 8, 1.25), (8, 12, 3.0), (1, 5, 1.0), (5, 9, 2.5),
    (9, 13, 1.5), (2, 6, 2.75), (6, 10, 1.0), (10, 14, 2.0), (3, 7, 1.0), (7, 11, 2.5),
    (11, 15, 1.0), (0, 15, 9.0), (3, 12, 7.5),
]


def _parent(lib, directed):
    G = (lib.DiGraph if directed else lib.Graph)()
    G.add_weighted_edges_from(EDGES)
    return G


def _view(lib, directed, kind):
    G = _parent(lib, directed)
    if kind == "subgraph":
        return G.subgraph([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12])
    if kind == "edge_subgraph":
        return G.edge_subgraph([(u, v) for u, v, _ in EDGES[::2]] + [(0, 1), (1, 5)])
    if kind == "restricted":
        return lib.restricted_view(G, [11], [(0, 1), (9, 13)])
    if kind == "reverse":
        return G.reverse(copy=False)
    if kind == "to_undirected":
        return G.to_undirected(as_view=True)
    if kind == "to_directed":
        return G.to_directed(as_view=True)
    raise ValueError(kind)


VIEWS = [
    (False, "subgraph"),
    (False, "edge_subgraph"),
    (False, "restricted"),
    (False, "to_directed"),
    (True, "subgraph"),
    (True, "edge_subgraph"),
    (True, "restricted"),
    (True, "reverse"),
    (True, "to_undirected"),
]


def _dict_close(a, b):
    return a.keys() == b.keys() and all(np.isclose(a[k], b[k]) for k in a)


def _matrix(M):
    return M.toarray() if hasattr(M, "toarray") else np.asarray(M)


def _outcome(call, lib, G):
    try:
        return "ok", call(lib, G)
    except Exception as exc:  # noqa: BLE001 - the exception IS the outcome compared
        return "raise", type(exc).__name__, str(exc)


# (name, call, compare, applies-to(view is directed)) - compare(fnx_result, nx_result).
CALLS = [
    ("is_empty", lambda L, G: L.is_empty(G), None, None),
    ("is_regular", lambda L, G: L.is_regular(G), None, None),
    ("number_of_nodes", lambda L, G: L.number_of_nodes(G), None, None),
    ("non_neighbors", lambda L, G: sorted(L.non_neighbors(G, 0)), None, None),
    ("bidirectional_dijkstra", lambda L, G: L.bidirectional_dijkstra(G, 0, 10), None, None),
    (
        "single_target_shortest_path_length",
        lambda L, G: dict(L.single_target_shortest_path_length(G, 10)),
        None,
        None,
    ),
    ("to_numpy_array", lambda L, G: L.to_numpy_array(G), np.array_equal, None),
    (
        "to_scipy_sparse_array(dtype=float)",
        lambda L, G: _matrix(L.to_scipy_sparse_array(G, dtype=float)),
        np.array_equal,
        None,
    ),
    ("floyd_warshall_numpy", lambda L, G: L.floyd_warshall_numpy(G), np.array_equal, None),
    ("google_matrix", lambda L, G: np.asarray(L.google_matrix(G)), np.allclose, None),
    ("katz_centrality_numpy", lambda L, G: L.katz_centrality_numpy(G, alpha=0.05), _dict_close, None),
    ("percolation_centrality", lambda L, G: L.percolation_centrality(G), _dict_close, None),
    ("bethe_hessian_matrix", lambda L, G: _matrix(L.bethe_hessian_matrix(G)), np.allclose, False),
    ("estrada_index", lambda L, G: L.estrada_index(G), np.isclose, False),
    ("subgraph_centrality", lambda L, G: L.subgraph_centrality(G), _dict_close, False),
    ("triadic_census", lambda L, G: L.triadic_census(G), None, True),
]


@pytest.mark.parametrize(("directed", "kind"), VIEWS, ids=[f"{'di' if d else 'un'}-{k}" for d, k in VIEWS])
@pytest.mark.parametrize(("name", "call", "compare", "applies"), CALLS, ids=[c[0] for c in CALLS])
def test_native_function_on_a_view_computes_on_the_view(directed, kind, name, call, compare, applies):
    fnx_view = _view(fnx, directed, kind)
    nx_view = _view(nx, directed, kind)
    if applies is not None and fnx_view.is_directed() != applies:
        pytest.skip(f"{name} is defined for {'directed' if applies else 'undirected'} graphs")
    expected = _outcome(call, nx, nx_view)
    actual = _outcome(call, fnx, fnx_view)
    if compare is None or expected[0] == "raise" or actual[0] == "raise":
        assert actual == expected
    else:
        assert compare(actual[1], expected[1]), (actual, expected)


@pytest.mark.parametrize(("directed", "kind"), VIEWS, ids=[f"{'di' if d else 'un'}-{k}" for d, k in VIEWS])
def test_a_native_call_follows_the_parent_after_it_gains_an_edge(directed, kind):
    # The concrete graph is cached on the view; growing the parent must refresh it.
    results = []
    for lib in (fnx, nx):
        view = _view(lib, directed, kind)
        parent = view._graph
        before = (lib.is_empty(view), lib.number_of_edges(view), sorted(lib.non_neighbors(view, 0)))
        parent.add_edge(0, 2, weight=1.0)
        parent.add_edge(2, 0, weight=1.0)
        after = (lib.is_empty(view), lib.number_of_edges(view), sorted(lib.non_neighbors(view, 0)))
        results.append((before, after))
    assert results[0] == results[1]
    if kind != "edge_subgraph":  # an edge subgraph shows only the edges it was given
        assert results[0][0] != results[0][1]


def test_a_view_of_a_view_reaches_the_kernel_as_the_innermost_graph():
    fnx_view = _parent(fnx, True).reverse(copy=False).subgraph([0, 1, 2, 4, 5, 8, 9, 12])
    nx_view = _parent(nx, True).reverse(copy=False).subgraph([0, 1, 2, 4, 5, 8, 9, 12])
    for call in (
        lambda L, G: L.is_empty(G),
        lambda L, G: sorted(L.non_neighbors(G, 0)),
        lambda L, G: L.bidirectional_dijkstra(G, 12, 0),
        lambda L, G: L.triadic_census(G),
    ):
        assert call(fnx, fnx_view) == call(nx, nx_view)


def test_a_view_of_a_view_follows_the_root_after_it_gains_an_edge():
    # The concrete graph is cached on the ROOT graph's counters: the inner view's
    # own counters are its empty base's and never move.
    results = []
    for lib in (fnx, nx):
        root = _parent(lib, True)
        view = root.reverse(copy=False).subgraph([0, 1, 2, 4, 5, 8, 9, 12])
        before = (lib.number_of_edges(view), sorted(lib.non_neighbors(view, 0)), lib.triadic_census(view))
        root.add_edge(0, 9, weight=1.0)
        root.add_edge(12, 2, weight=1.0)
        after = (lib.number_of_edges(view), sorted(lib.non_neighbors(view, 0)), lib.triadic_census(view))
        results.append((before, after))
    assert results[0] == results[1]
    assert results[0][0] != results[0][1]


def test_a_user_subclass_of_a_graph_class_still_runs_on_its_own_storage():
    # Not a view: no materialisation hook, so the kernel reads the instance itself.
    class Mine(fnx.Graph):
        pass

    G = Mine()
    G.add_weighted_edges_from(EDGES)
    H = nx.Graph()
    H.add_weighted_edges_from(EDGES)
    assert fnx.is_empty(G) is False
    assert sorted(fnx.non_neighbors(G, 0)) == sorted(nx.non_neighbors(H, 0))
    assert fnx.bidirectional_dijkstra(G, 0, 10) == nx.bidirectional_dijkstra(H, 0, 10)


# br-r37-c1-36v6r: the concrete graph a view reaches a kernel as has the VIEW's
# rows. networkx's kernels walk the view, whose rows are its root's rows with
# entries filtered out (swapped through a reverse view); fnx's concrete graph
# came from view.copy(), which fills each row in edge-walk order, so bfs / dfs
# order on an undirected view and every predecessor walk on a directed one
# followed the copy. The parent's edges are inserted in shuffled order so no row
# happens to be in walk order.
def _shuffled(lib, directed):
    rng = random.Random(3)
    edges = [(u, v) for u in range(40) for v in range(40) if u != v and rng.random() < 0.12]
    rng.shuffle(edges)
    G = (lib.DiGraph if directed else lib.Graph)()
    G.add_nodes_from(range(40))
    G.add_edges_from(edges)
    return G, edges


def _row_view(lib, directed, kind):
    G, edges = _shuffled(lib, directed)
    keep = [n for n in range(40) if n % 7 != 3]
    if kind == "subgraph":
        return G.subgraph(keep)
    if kind == "small_subgraph":  # iterates the keep set, not the parent
        return G.subgraph([31, 4, 22, 9, 17, 0, 26, 13])
    if kind == "restricted":
        return lib.restricted_view(G, [5, 17], edges[::6])
    if kind == "edge_subgraph":
        return G.edge_subgraph(edges[::2])
    if kind == "reverse":
        return G.reverse(copy=False)
    if kind == "reverse_of_subgraph":
        return G.subgraph(keep).reverse(copy=False)
    if kind == "subgraph_of_reverse":
        return G.reverse(copy=False).subgraph(keep)
    # networkx's to_undirected view iterates set(succ) | set(pred): no graph
    # holds that order, so these rows are handed over as the view reads them.
    if kind == "to_undirected":
        return G.to_undirected(as_view=True)
    if kind == "subgraph_of_to_undirected":
        return G.to_undirected(as_view=True).subgraph(keep)
    if kind == "to_directed":
        return G.to_directed(as_view=True)
    raise ValueError(kind)


ROW_VIEWS = [
    (directed, kind)
    for directed in (False, True)
    for kind in ("subgraph", "small_subgraph", "restricted", "edge_subgraph")
] + [
    (True, "reverse"),
    (True, "reverse_of_subgraph"),
    (True, "subgraph_of_reverse"),
    (True, "to_undirected"),
    (True, "subgraph_of_to_undirected"),
    (False, "to_directed"),
]
ROW_IDS = [f"{'di' if d else 'un'}-{k}" for d, k in ROW_VIEWS]


@pytest.mark.parametrize(("directed", "kind"), ROW_VIEWS, ids=ROW_IDS)
def test_the_concrete_graph_of_a_view_has_the_views_rows(directed, kind):
    fnx_view = _row_view(fnx, directed, kind)
    nx_view = _row_view(nx, directed, kind)
    concrete = _materialize_view(fnx_view)
    assert list(concrete) == list(nx_view)
    assert {n: list(concrete[n]) for n in nx_view} == {n: list(nx_view[n]) for n in nx_view}
    if nx_view.is_directed():
        assert {n: list(concrete.pred[n]) for n in nx_view} == {
            n: list(nx_view.pred[n]) for n in nx_view
        }
    assert list(concrete.edges()) == list(nx_view.edges())


ROW_CALLS = [
    ("bfs_edges", lambda L, G, s: list(L.bfs_edges(G, s))),
    ("dfs_edges", lambda L, G, s: list(L.dfs_edges(G, s))),
    ("dfs_postorder_nodes", lambda L, G, s: list(L.dfs_postorder_nodes(G, s))),
    ("bfs_predecessors", lambda L, G, s: list(L.bfs_predecessors(G, s))),
    ("single_source_shortest_path", lambda L, G, s: list(L.single_source_shortest_path(G, s).items())),
    ("bfs_edges(reverse=True)", lambda L, G, s: list(L.bfs_edges(G, s, reverse=True)) if G.is_directed() else None),
    ("edge_dfs(reverse)", lambda L, G, s: list(L.edge_dfs(G, s, orientation="reverse")) if G.is_directed() else None),
]


@pytest.mark.parametrize(("directed", "kind"), ROW_VIEWS, ids=ROW_IDS)
@pytest.mark.parametrize(("name", "call"), ROW_CALLS, ids=[c[0] for c in ROW_CALLS])
def test_traversal_order_on_a_view_is_networkxs(directed, kind, name, call):
    fnx_view = _row_view(fnx, directed, kind)
    nx_view = _row_view(nx, directed, kind)
    for source in list(nx_view)[:3]:
        assert _outcome(lambda L, G: call(L, G, source), fnx, fnx_view) == _outcome(
            lambda L, G: call(L, G, source), nx, nx_view
        ), (name, source)


def test_rows_are_reordered_only_while_nobody_holds_a_row_mirror():
    # The reorder runs on the graph _materialize_view has just built; a graph
    # that already handed out a row mirror (a row's key mirror, made by
    # iterating it or by neighbors(); the dict-of-dicts cache) is left as it
    # is rather than reordered under its holder. A G[u] row that was taken but
    # not yet read reads the native row, so it follows.
    source = fnx.Graph([("x", "c"), ("x", "a"), ("x", "b")])

    def built():
        graph = fnx.Graph()
        graph.add_nodes_from("abcx")
        graph.add_edges_from([("a", "x"), ("b", "x"), ("c", "x")])
        return graph

    graph = built()
    row = graph["x"]
    assert graph._fnx_reorder_rows_like(source) is True
    assert list(row) == list(graph["x"]) == ["c", "a", "b"]
    assert list(graph.edges()) == [("a", "x"), ("b", "x"), ("c", "x")]

    for hand_out in (lambda g: list(g["x"]), lambda g: g.neighbors("x"), fnx.to_dict_of_dicts):
        held = built()
        hand_out(held)
        assert held._fnx_reorder_rows_like(source) is False
        assert list(held["x"]) == ["a", "b", "c"]


# br-r37-c1-u9a13: the concrete graph is cached on the view, keyed on the root's
# structure counters - which do not move on an attribute write. Every native
# call on the view then computed on the copy's old weights. The key carries the
# root's edge-attribute epoch now (it moves on every write of an edge attr dict,
# through a held reference too, and on set_edge_attributes' native paths; not
# on reads), a MultiGraph root (whose dicts report no writes) is not cached,
# and the graph dict is refreshed on a hit.
U9_EDGES = [(0, 1, 1.0), (1, 2, 1.0), (0, 2, 5.0), (2, 3, 1.0), (3, 0, 2.0)]


def _u9_graph(lib, cls):
    G = getattr(lib, cls)()
    G.add_weighted_edges_from(U9_EDGES)
    G.graph["g"] = 1
    return G


def _u9_edge(G):
    return (0, 1, 0) if G.is_multigraph() else (0, 1)


U9_WRITERS = {
    "G[u][v][w] =": lambda L, G, held: (G[0][1][0] if G.is_multigraph() else G[0][1]).__setitem__("weight", 100.0),
    "held dict": lambda L, G, held: held.__setitem__("weight", 100.0),
    "held dict update": lambda L, G, held: held.update(weight=100.0),
    "G.edges[e][w] =": lambda L, G, held: G.edges[_u9_edge(G)].__setitem__("weight", 100.0),
    "set_edge_attributes scalar": lambda L, G, held: L.set_edge_attributes(G, 100.0, "weight"),
    "set_edge_attributes dict": lambda L, G, held: L.set_edge_attributes(G, {_u9_edge(G): 100.0}, "weight"),
    "graph attr": lambda L, G, held: G.graph.__setitem__("g", 2),
}
U9_VIEWS = {
    "subgraph": lambda L, G: G.subgraph([0, 1, 2, 3]),
    "restricted": lambda L, G: L.restricted_view(G, [], []),
    "reverse": lambda L, G: G.reverse(copy=False) if G.is_directed() else None,
    "conversion": lambda L, G: G.to_undirected(as_view=True) if G.is_directed() else G.to_directed(as_view=True),
}


def _u9_reads(L, V):
    return (
        L.shortest_path_length(V, 0, 2, weight="weight"),
        dict(L.relabel_nodes(V, {}, copy=True).graph),
    )


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("view_kind", list(U9_VIEWS))
@pytest.mark.parametrize("writer", list(U9_WRITERS), ids=list(U9_WRITERS))
def test_a_view_sees_an_attribute_write_on_its_parent(cls, view_kind, writer, request):
    if cls == "MultiGraph" and writer != "graph attr":
        # Still open: rebuilding a MultiGraph view per call instead cost 26 ms a
        # call, so its cache stays keyed on structure until its dicts report.
        request.applymarker(
            pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-u9a13: a MultiGraph's edge attr dicts report no writes",
            )
        )
    results = []
    for L in (fnx, nx):
        G = _u9_graph(L, cls)
        V = U9_VIEWS[view_kind](L, G)
        if V is None:
            pytest.skip("reverse views are directed only")
        held = G[0][1][0] if G.is_multigraph() else G[0][1]
        before = _u9_reads(L, V)
        U9_WRITERS[writer](L, G, held)
        results.append((before, _u9_reads(L, V)))
    assert results[0] == results[1]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiDiGraph"])
def test_the_cache_still_hits_across_reads_and_misses_after_a_write(cls):
    G = _u9_graph(fnx, cls)
    V = G.subgraph([0, 1, 2, 3])
    first = _materialize_view(V)
    # Reads - an exposed dict, a data walk, a native call on the parent - do
    # not move the epoch.
    _ = G[0][1]
    _ = list(G.edges(data=True))
    fnx.shortest_path_length(G, 0, 2, weight="weight")
    assert _materialize_view(V) is first
    (G[0][1][0] if G.is_multigraph() else G[0][1])["weight"] = 7.0
    second = _materialize_view(V)
    assert second is not first
    assert _materialize_view(V) is second


def test_a_reverse_view_shares_its_parents_graph_dict():
    for L in (fnx, nx):
        G = L.DiGraph([(0, 1)])
        G.graph["a"] = 1
        R = G.reverse(copy=False)
        G.graph["b"] = 2
        R.graph["c"] = 3
        assert R.graph is G.graph
        assert G.graph == {"a": 1, "b": 2, "c": 3}
