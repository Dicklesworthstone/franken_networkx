"""A view's public methods answer from the view, not its empty Rust base.

br-r37-c1-fabqo: the view classes sit in front of a PyO3 graph class whose own
storage is EMPTY (br-r37-c1-pgfd2, q131o, y2b8t). A public method the view class
never overrode ran on that empty storage:

  * a filtered DiGraph / MultiDiGraph view's ``reverse()`` returned an empty graph;
  * a ``to_directed`` / ``to_undirected(as_view=True)`` view answered
    ``get_edge_data`` None and ``order()`` 0, its ``degree`` / ``in_degree`` /
    ``out_degree`` were plain methods (``dict(view.degree)`` raised TypeError),
    and ``to_scipy_sparse_array`` / ``johnson`` / ``bellman_ford`` read an
    adjacency fallback bound to the empty storage - a zero matrix, KeyError;
  * a reverse view's ``number_of_edges(u, v)`` raised TypeError.

Each row calls the same thing on an fnx view and on the networkx view built the
same way, and compares the value or the exception (type and message).
"""

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx

EDGES = [(0, 1, 1.5), (1, 2, 2.0), (2, 0, 1.0), (2, 3, 4.0), (3, 4, 1.0), (1, 1, 0.5)]


def _views(lib):
    g = lib.Graph()
    g.add_weighted_edges_from(EDGES)
    dg = lib.DiGraph()
    dg.add_weighted_edges_from(EDGES)
    mg = lib.MultiGraph(g)
    mg.add_edge(0, 1, weight=3.0)
    mdg = lib.MultiDiGraph(dg)
    mdg.add_edge(0, 1, weight=3.0)
    return {
        "G.sub": g.subgraph([0, 1, 2, 3]),
        "G.to_directed": g.to_directed(as_view=True),
        "D.sub": dg.subgraph([0, 1, 2, 3]),
        "D.edge_sub": dg.edge_subgraph([(0, 1), (1, 2), (2, 3)]),
        "D.reverse": dg.reverse(copy=False),
        "D.to_undirected": dg.to_undirected(as_view=True),
        "MG.sub": mg.subgraph([0, 1, 2, 3]),
        "MG.to_directed": mg.to_directed(as_view=True),
        "MDG.sub": mdg.subgraph([0, 1, 2, 3]),
        "MDG.restricted": lib.restricted_view(mdg, [4], [(0, 1, 0)]),
        "MDG.reverse": mdg.reverse(copy=False),
        "MDG.to_undirected": mdg.to_undirected(as_view=True),
    }


KINDS = list(_views(nx))
CONVERSION = [k for k in KINDS if "to_" in k]
DIRECTED_FILTERED = ["D.sub", "D.edge_sub", "MDG.sub", "MDG.restricted"]
REVERSE = ["D.reverse", "MDG.reverse"]


def _norm(x):
    if hasattr(x, "edges") and callable(getattr(x, "is_directed", None)):
        return (
            "graph",
            type(x).__name__,
            x.is_directed(),
            x.is_multigraph(),
            sorted(map(repr, x.nodes(data=True))),
            sorted(map(repr, x.edges(data=True))),
        )
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (str, int, float, bool, type(None), tuple)):
        return x
    if hasattr(x, "items"):
        return sorted((repr(k), repr(v)) for k, v in x.items())
    return list(x)


def _outcome(call, lib, G):
    try:
        return "ok", _norm(call(lib, G))
    except Exception as exc:  # noqa: BLE001 - the exception IS the outcome compared
        return "raise", type(exc).__name__, str(exc)


def _check(kind, call):
    fnx_view = _views(fnx)[kind]
    nx_view = _views(nx)[kind]
    assert _outcome(call, fnx, fnx_view) == _outcome(call, nx, nx_view)


@pytest.mark.parametrize("kind", DIRECTED_FILTERED + CONVERSION + REVERSE)
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda L, G: G.reverse() if G.is_directed() else None, id="reverse"),
        pytest.param(lambda L, G: G.get_edge_data(0, 1), id="get_edge_data"),
        pytest.param(lambda L, G: G.get_edge_data(0, 9, default="d"), id="get_edge_data-missing"),
        pytest.param(lambda L, G: G.order(), id="order"),
        pytest.param(lambda L, G: G.number_of_edges(0, 1), id="number_of_edges-0-1"),
        pytest.param(lambda L, G: G.number_of_edges(1, 0), id="number_of_edges-1-0"),
        pytest.param(lambda L, G: G.number_of_edges(0, 9), id="number_of_edges-0-9"),
        pytest.param(lambda L, G: G.number_of_edges(), id="number_of_edges"),
        pytest.param(lambda L, G: list(G.degree), id="degree"),
        pytest.param(lambda L, G: dict(G.degree(weight="weight")), id="degree-weighted"),
        pytest.param(lambda L, G: G.degree[1], id="degree-item"),
        pytest.param(lambda L, G: G.degree(1, weight="weight"), id="degree-node-weighted"),
        pytest.param(lambda L, G: list(G.degree([0, 1])), id="degree-nbunch"),
        pytest.param(lambda L, G: len(G.degree), id="degree-len"),
        pytest.param(lambda L, G: repr(G.degree), id="degree-repr"),
        pytest.param(lambda L, G: type(G.degree).__name__, id="degree-type"),
        pytest.param(lambda L, G: G.size(weight="weight"), id="size-weighted"),
    ],
)
def test_public_method_on_a_view_answers_like_networkx(kind, call):
    _check(kind, call)


@pytest.mark.parametrize("kind", CONVERSION)
@pytest.mark.parametrize(
    "call",
    [
        # The degree-view contract on the conversion views, whose degree was a
        # plain method. (Filtered and reverse views' str() / missing-nbunch
        # rows are br-r37-c1-dvvme.)
        pytest.param(lambda L, G: str(G.degree), id="degree-str"),
        pytest.param(lambda L, G: G.degree[9], id="degree-missing-item"),
        pytest.param(lambda L, G: G.degree[[1]], id="degree-unhashable-item"),
        pytest.param(lambda L, G: list(G.degree(9)), id="degree-missing-nbunch"),
        pytest.param(lambda L, G: G.number_of_edges(9, 0), id="number_of_edges-missing"),
        pytest.param(lambda L, G: hasattr(G, "reverse"), id="has-reverse"),
        pytest.param(lambda L, G: L.to_scipy_sparse_array(G).toarray(), id="to_scipy_sparse_array"),
        pytest.param(lambda L, G: L.laplacian_matrix(G).toarray(), id="laplacian"),
        pytest.param(lambda L, G: L.bellman_ford_predecessor_and_distance(G, 0), id="bellman_ford"),
        pytest.param(lambda L, G: L.describe(G), id="describe"),
    ],
)
def test_conversion_view_answers_like_networkx(kind, call):
    _check(kind, call)


@pytest.mark.parametrize("kind", [k for k in CONVERSION if k.startswith(("G.", "D."))])
def test_johnson_on_a_conversion_view(kind):
    _check(kind, lambda L, G: L.johnson(G))


@pytest.mark.parametrize("kind", [k for k in CONVERSION if not k.endswith("to_undirected")])
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda L, G: list(G.in_degree), id="in_degree"),
        pytest.param(lambda L, G: dict(G.in_degree(weight="weight")), id="in_degree-weighted"),
        pytest.param(lambda L, G: G.out_degree[0], id="out_degree-item"),
        pytest.param(lambda L, G: type(G.in_degree).__name__, id="in_degree-type"),
        pytest.param(lambda L, G: type(G.out_degree).__name__, id="out_degree-type"),
    ],
)
def test_directed_conversion_view_in_out_degree(kind, call):
    _check(kind, call)


@pytest.mark.parametrize("kind", REVERSE)
def test_reverse_view_counts_edges_between_two_nodes(kind):
    for u, v in ((0, 1), (1, 0), (1, 1), (4, 3), (0, 9)):
        _check(kind, lambda L, G, u=u, v=v: G.number_of_edges(u, v))
    _check(kind, lambda L, G: G.number_of_edges(9, 0))


def test_a_reversed_filtered_view_is_independent_of_the_view():
    # The reverse is a fresh graph: writing its edge data leaves the view (and
    # the concrete graph cached for it) untouched.
    dg = fnx.DiGraph()
    dg.add_weighted_edges_from(EDGES)
    view = dg.subgraph([0, 1, 2, 3])
    fnx.is_empty(view)  # materialise and cache the concrete graph first
    reversed_copy = view.reverse()
    reversed_copy[1][0]["weight"] = 99.0
    assert view[0][1]["weight"] == 1.5
    assert dg[0][1]["weight"] == 1.5
    assert fnx.to_numpy_array(view)[0][1] == 1.5


# br-r37-c1-ndro1: networkx's view classes ARE the graph classes
# (generic_graph_view builds G.__class__() and freezes it), so type(view)() is a
# fresh empty graph - relabel_nodes, intersection_all, the current-flow
# centralities (which relabel first) and user code build their output that way.
# fnx's view classes need their backing graph: every reverse and conversion view
# raised TypeError there. The missing-attribute and missing-key errors are
# networkx's wording too.
CLASS_CALLS = [
    (
        "type(view)()",
        lambda L, G: (lambda H: (type(H) is getattr(L, type(H).__name__), L.is_frozen(H), len(H)))(
            type(G)()
        ),
    ),
    ("view.__class__()", lambda L, G: G.__class__()),
    ("relabel_nodes", lambda L, G: L.relabel_nodes(G, {0: "zero"})),
    ("intersection_all", lambda L, G: L.intersection_all([G, G])),
    ("view['x']", lambda L, G: G["x"]),
    ("view.adj['x']", lambda L, G: G.adj["x"]),
    ("view.items", lambda L, G: G.items),
    ("from_dict_of_dicts(view)", lambda L, G: L.from_dict_of_dicts(G)),
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(("name", "call"), CLASS_CALLS, ids=[c[0] for c in CLASS_CALLS])
def test_a_view_class_builds_and_words_errors_like_networkx(kind, name, call):
    _check(kind, call)


@pytest.mark.parametrize("kind", ["G.sub", "D.to_undirected"])
@pytest.mark.parametrize(
    "name",
    [
        "information_centrality",
        "current_flow_closeness_centrality",
        "edge_current_flow_betweenness_centrality",
    ],
)
def test_current_flow_centrality_of_an_undirected_view(kind, name):
    def call(L, G):
        return {k: round(v, 9) for k, v in getattr(L, name)(G).items()}

    _check(kind, call)


@pytest.mark.parametrize("kind", CONVERSION + REVERSE)
def test_a_view_pickles_as_a_frozen_graph_of_its_content(kind):
    # networkx pickles a reverse or conversion view as a frozen graph of the
    # view's nodes and edges (a filtered view it cannot pickle at all).
    import pickle

    def call(L, G):
        H = pickle.loads(pickle.dumps(G))
        return L.is_frozen(H), _norm(H)

    _check(kind, call)


def test_a_filtered_view_over_a_reverse_view_still_views_its_graph():
    # One class carries both mixins (_FilteredGraphView over _ReverseDirectedView);
    # the first mixin's super().__new__(cls) reaches the second with no
    # arguments, which must build the view, not the empty graph type(view)()
    # makes.
    for kind in REVERSE:
        fnx_view = _views(fnx)[kind].subgraph([0, 1, 2, 3])
        nx_view = _views(nx)[kind].subgraph([0, 1, 2, 3])
        assert sorted(fnx_view.edges()) == sorted(nx_view.edges())
        assert fnx_view._graph is not None
        empty = type(fnx_view)()
        assert (type(empty).__name__, len(empty)) == (type(type(nx_view)()).__name__, 0)
