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

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx

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
