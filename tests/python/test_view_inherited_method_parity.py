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


# br-r37-c1-dvvme: degree views and number_of_edges(u, v) on views, against
# networkx's. str() of a degree view is networkx's list, not its repr (the
# simple DegreeView had it - br-r37-c1-wu9dv - and its siblings did not, on
# concrete graphs too: DiGraph in/out, MultiGraph, MultiDiGraph); degree(n) of
# a node the view lacks raises networkx's NetworkXError at the call (it builds
# the node list eagerly); an unhashable subscript is networkx's dict-key
# TypeError; number_of_edges(u, v) is networkx's `v in self._adj[u]` on a
# simple view (the view adjacency's KeyError for an absent u) and 0 on a
# multigraph view for every KeyError.
DEGREE_CALLS = [
    ("str(degree)", lambda L, G: str(G.degree)),
    ("str(degree(weight))", lambda L, G: str(G.degree(weight="weight"))),
    ("str(degree(nbunch))", lambda L, G: str(G.degree([0, 1]))),
    ("str(in_degree)", lambda L, G: str(G.in_degree) if G.is_directed() else None),
    ("str(out_degree)", lambda L, G: str(G.out_degree) if G.is_directed() else None),
    ("degree(missing)", lambda L, G: list(G.degree(9))),
    ("degree[unhashable]", lambda L, G: G.degree[[1]]),
    ("number_of_edges(missing, v)", lambda L, G: G.number_of_edges(9, 0)),
    ("number_of_edges(missing)", lambda L, G: G.number_of_edges(9)),
    ("number_of_edges(u)", lambda L, G: G.number_of_edges(0)),
    ("number_of_edges(u, v)", lambda L, G: G.number_of_edges(0, 1)),
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(("name", "call"), DEGREE_CALLS, ids=[c[0] for c in DEGREE_CALLS])
def test_degree_views_and_edge_counts_on_a_view(kind, name, call):
    _check(kind, call)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_str_of_a_concrete_graphs_degree_views(cls):
    outs = []
    for lib in (fnx, nx):
        G = getattr(lib, cls)([(0, 1), (1, 2), (2, 0)])
        outs.append(
            [
                str(getattr(G, attr))
                for attr in ("degree", "in_degree", "out_degree")
                if hasattr(G, attr)
            ]
        )
    assert outs[0] == outs[1]


MISSING_ON_UNDIRECTED = [
    (kind, name)
    for kind in CONVERSION
    for name in (
        ("in_degree", "out_degree", "reverse", "pred", "no_such_thing")
        if kind.endswith("to_undirected")
        else ("no_such_thing",)
    )
]


@pytest.mark.parametrize(("kind", "name"), MISSING_ON_UNDIRECTED)
def test_a_conversion_views_missing_attribute_reads_like_networkx(kind, name):
    # The miss is probed on the VIEW's class (a to_undirected view is a Graph):
    # probing the parent's DiGraph let in_degree / out_degree / reverse through
    # to the concrete copy, whose native class named itself
    # 'franken_networkx.Graph'.
    _check(kind, lambda L, G: getattr(G, name))


def _rows(kind, view):
    """Every row a conversion view hands out, with each multigraph row's key
    dicts: networkx's are AtlasView / AdjacencyView over the source row, or
    over UnionAtlas / UnionMultiInner of the succ and pred rows."""
    accessors = ["adj", "__getitem__"]
    if view.is_directed():
        accessors += ["succ", "pred"]
    for node in view:
        for name in accessors:
            row = view[node] if name == "__getitem__" else getattr(view, name)[node]
            yield (node, name), row
            if view.is_multigraph():
                for nbr in row:
                    yield (node, name, nbr), row[nbr]


@pytest.mark.parametrize("kind", CONVERSION)
def test_a_conversion_views_rows_read_and_print_like_networkx(kind):
    # br-r37-c1-u7szm: the rows were _ConversionNeighborMap objects with
    # object's repr, and a one-way MultiDiGraph pair's key dict was the
    # source's own; the union key dicts walked succ keys then pred keys where
    # networkx walks set(succ) | set(pred).
    fnx_rows = dict(_rows(kind, _views(fnx)[kind]))
    nx_rows = dict(_rows(kind, _views(nx)[kind]))
    assert list(fnx_rows) == list(nx_rows)
    for where, want in nx_rows.items():
        got = fnx_rows[where]
        assert type(got).__name__ == type(want).__name__, where
        assert repr(got) == repr(want), where
        assert str(got) == str(want), where
        assert list(got) == list(want), where
        assert len(got) == len(want), where


def test_union_key_dict_iterates_in_set_order():
    # Keys 1024 and 5 one way, 0 the other: networkx's set union iterates
    # [1024, 0, 5]; succ-then-pred gave [1024, 5, 0].
    views = []
    for lib in (fnx, nx):
        mdg = lib.MultiDiGraph()
        mdg.add_edge(0, 1, key=1024)
        mdg.add_edge(1, 0, key=0)
        mdg.add_edge(0, 1, key=5)
        views.append(mdg.to_undirected(as_view=True))
    assert list(views[0].adj[0][1]) == list(views[1].adj[0][1]) == [1024, 0, 5]


@pytest.mark.parametrize("seed", range(6))
def test_union_view_edges_list_keys_in_networkx_order(seed):
    # Each pair's keys come out of its UnionAtlas - set order - one-way pairs
    # included; the source's key dict order differed for every graph here.
    import random

    rng = random.Random(seed)
    edges = [
        (rng.randrange(30), rng.randrange(30), rng.choice([5, 1024, 0, 13, 2048, 77]))
        for _ in range(120)
    ]
    out = []
    for lib in (fnx, nx):
        mdg = lib.MultiDiGraph()
        for u, v, key in edges:
            mdg.add_edge(u, v, key=key)
        out.append(list(mdg.to_undirected(as_view=True).edges(keys=True)))
    assert out[0] == out[1]


# br-r37-c1-pgpg1: a to_undirected(as_view=True) view of a MultiDiGraph reads the
# source's rows in a few native crossings instead of a synthesized row per node.
# Every read must stay networkx's, value for value: each node's neighbours and
# each pair's keys in set order (one-way pairs too), weights summed in that
# order with their int / float type, the edges' live attr dicts handed out.

_UNION_WEIGHTS = [0.1, 0.2, 0.3, 1e16, -1e16, 3.0, 7, 2, 0.7, 1e-17]


def _union_views(seed):
    import random

    rng = random.Random(seed)
    if seed % 3 == 0:
        nodes = [f"n{i}" for i in range(9)]
    else:
        nodes = rng.sample(range(-50, 5000), 9)
    keys = [0, 5, 1024, 33, "a", "zz"] if seed % 2 else [None]
    ops = []
    for _ in range(45):
        u = rng.choice(nodes)
        v = u if rng.random() < 0.1 else rng.choice(nodes)
        attrs = {"weight": rng.choice(_UNION_WEIGHTS)} if rng.random() < 0.8 else {}
        ops.append((u, v, rng.choice(keys), attrs))
    views = []
    for lib in (fnx, nx):
        mdg = lib.MultiDiGraph()
        mdg.add_nodes_from(nodes)
        for u, v, key, attrs in ops:
            mdg.add_edge(u, v, key=key, **attrs)
        views.append(mdg.to_undirected(as_view=True))
    return nodes, views


def _exact(x):
    """x with every number tagged by its type and exact value."""
    if isinstance(x, bool):
        return ("bool", x)
    if isinstance(x, float):
        return ("float", x.hex())
    if isinstance(x, int):
        return ("int", x)
    if isinstance(x, (list, tuple)):
        return [_exact(item) for item in x]
    if hasattr(x, "items"):
        return [(key, _exact(value)) for key, value in x.items()]
    return x


UNION_VIEW_READS = {
    "edges": lambda V, nb: list(V.edges),
    "edges()": lambda V, nb: list(V.edges()),
    "edges(keys)": lambda V, nb: list(V.edges(keys=True)),
    "edges(data)": lambda V, nb: list(V.edges(data=True)),
    "edges(keys, data)": lambda V, nb: list(V.edges(keys=True, data=True)),
    "edges(data=weight)": lambda V, nb: list(V.edges(data="weight", default=-1)),
    "edges(nbunch, keys, data)": lambda V, nb: list(V.edges(nb, keys=True, data=True)),
    "edges(nbunch)": lambda V, nb: list(V.edges(nb)),
    "len(edges)": lambda V, nb: [len(V.edges), len(V.edges(data=True)), len(V.edges(nb))],
    "number_of_edges": lambda V, nb: V.number_of_edges(),
    "size": lambda V, nb: [V.size(), V.size(weight="weight")],
    "degree": lambda V, nb: list(V.degree),
    "degree(weight)": lambda V, nb: list(V.degree(weight="weight")),
    "degree(nbunch)": lambda V, nb: [list(V.degree(nb)), list(V.degree(nb, weight="weight"))],
    "degree[n]": lambda V, nb: [(V.degree[n], V.degree(n, weight="weight")) for n in V],
    "rows": lambda V, nb: [
        (list(V.adj[n]), list(V.adj[n].items()), list(V.adj[n].values()), len(V.adj[n]))
        for n in V
    ],
    "entries": lambda V, nb: [
        (list(V.adj[u][v].items()), repr(V.adj[u][v]), str(V.adj[u][v]))
        for u in V
        for v in V.adj[u]
    ],
    "row types": lambda V, nb: [
        type(row).__name__ for n in V for row in (V.adj[n], V.adj[n].items(), V.adj[n].values())
    ],
}


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("read", list(UNION_VIEW_READS))
def test_union_view_reads_match_networkx_exactly(seed, read):
    nodes, (fnx_view, nx_view) = _union_views(seed)
    nbunch = nodes[3:6] + nodes[3:4]  # networkx drops the duplicate
    call = UNION_VIEW_READS[read]
    assert _exact(call(fnx_view, nbunch)) == _exact(call(nx_view, nbunch))


@pytest.mark.parametrize("lib", [fnx, nx], ids=["fnx", "nx"])
def test_union_view_one_way_pair_weights_sum_in_set_order(lib):
    # Keys 1024, 5, 0 one way only. networkx's UnionAtlas over {} iterates the
    # key set, [1024, 0, 5], so the weights sum 1e16 - 1e16 + 1.0 = 1.0; summed
    # in the key dict's order [1024, 5, 0] the 1.0 is lost and it reads 0.0.
    mdg = lib.MultiDiGraph()
    mdg.add_edge(0, 1, key=1024, weight=1e16)
    mdg.add_edge(0, 1, key=5, weight=1.0)
    mdg.add_edge(0, 1, key=0, weight=-1e16)
    view = mdg.to_undirected(as_view=True)
    assert list(view.adj[0][1]) == [1024, 0, 5]
    assert view.degree(0, weight="weight") == 1.0
    assert list(view.degree(weight="weight")) == [(0, 1.0), (1, 1.0)]
    assert view.size(weight="weight") == 1.0


@pytest.mark.parametrize("lib", [fnx, nx], ids=["fnx", "nx"])
def test_union_view_reads_follow_the_source_and_hand_out_live_dicts(lib):
    mdg = lib.MultiDiGraph([(0, 1), (1, 0), (1, 2)])
    view = mdg.to_undirected(as_view=True)
    row = view.adj[1]
    entry = view.adj[1][0]
    assert view.number_of_edges() == 2
    mdg.add_edge(1, 0, key=7, weight=3)
    mdg.add_edge(1, 3)
    mdg.edges[0, 1, 0]["weight"] = 9
    assert list(row) == [0, 2, 3]
    assert dict(entry) == {0: {"weight": 9}, 7: {"weight": 3}}
    assert list(view.edges(keys=True, data=True)) == [
        (0, 1, 0, {"weight": 9}),
        (0, 1, 7, {"weight": 3}),
        (1, 2, 0, {}),
        (1, 3, 0, {}),
    ]
    assert view.number_of_edges() == len(view.edges(data=True)) == 4
    # Node 1's pair with 0 reads key 0 from its own out-edge (1, 0, 0): weight 1.
    assert list(view.degree(weight="weight")) == [(0, 12), (1, 6), (2, 1), (3, 1)]
    for _, _, attrs in view.edges(data=True):
        attrs["seen"] = True
    for _, keydict in view.adj[2].items():
        keydict[0]["row"] = True
    assert list(mdg.edges(keys=True, data=True)) == [
        (0, 1, 0, {"weight": 9, "seen": True}),
        (1, 0, 0, {}),
        (1, 0, 7, {"weight": 3, "seen": True}),
        (1, 2, 0, {"seen": True, "row": True}),
        (1, 3, 0, {"seen": True}),
    ]
