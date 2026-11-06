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
    # At node 1 the outgoing 1->0 entry wins over incoming 0->1's weight 9.
    assert dict(entry) == {0: {}, 7: {"weight": 3}}
    assert view.adj[0][1][0]["weight"] == 9
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


def _assert_view_mapping_copy(original, copied, depth):
    """Copy mapping layers, but leave values inside attribute dicts shallow."""
    assert type(copied) is dict
    assert copied is not original
    assert list(copied) == list(original)
    if depth > 1:
        for key in original:
            _assert_view_mapping_copy(original[key], copied[key], depth - 1)
    else:
        assert copied["payload"] is original["payload"]
        copied["copy_only"] = True
        assert "copy_only" not in original


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("conversion", ["to_directed", "to_undirected"])
@pytest.mark.parametrize("filtered", [False, True])
def test_conversion_row_copy_matches_networkx(graph_type, conversion, filtered):
    """br-r37-c1-o1z03: row/entry copies are dicts, ordered and independent."""
    views = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)()
        graph.add_nodes_from([0, 1, 2, "isolated"])
        for u, v, key in ((0, 1, 1024), (0, 1, 5), (1, 0, 0),
                          (1, 0, 5), (1, 2, 7), (2, 2, 0)):
            attrs = {"weight": key + 0.5, "payload": [u, v, key]}
            if graph.is_multigraph():
                graph.add_edge(u, v, key=key, **attrs)
            else:
                graph.add_edge(u, v, **attrs)
        if filtered:
            graph = graph.subgraph(list(graph))
        views.append(getattr(graph, conversion)(as_view=True))
    for name in ("adj", "succ", "pred") if views[0].is_directed() else ("adj",):
        actual_mapping, expected_mapping = getattr(views[0], name), getattr(views[1], name)
        actual, expected = actual_mapping.copy(), expected_mapping.copy()
        assert _exact(actual) == _exact(expected), name
        depth = 4 if views[0].is_multigraph() else 3
        _assert_view_mapping_copy(actual_mapping, actual, depth)
        _assert_view_mapping_copy(expected_mapping, expected, depth)
    actual_rows = dict(_rows("copy", views[0]))
    expected_rows = dict(_rows("copy", views[1]))
    assert list(actual_rows) == list(expected_rows)
    for where, expected_row in expected_rows.items():
        actual_row = actual_rows[where]
        actual, expected = actual_row.copy(), expected_row.copy()
        assert _exact(actual) == _exact(expected), where
        depth = 3 if views[0].is_multigraph() and len(where) == 2 else 2
        _assert_view_mapping_copy(actual_row, actual, depth)
        _assert_view_mapping_copy(expected_row, expected, depth)


@pytest.mark.parametrize("filtered", [False, True])
@pytest.mark.parametrize("missing", [7, "missing", ("absent", 7)])
def test_union_multi_row_missing_pair_keyerror(filtered, missing):
    """Union rows preserve their backing mapping's exact KeyError args."""
    errors = []
    predecessor_errors = []
    for lib in (fnx, nx):
        graph = lib.MultiDiGraph([(0, 1), (1, 0), (1, 2)])
        if filtered:
            graph = graph.subgraph(list(graph))
        # A nested public adjacency wrapper must not erase filtered wording
        # before a conversion view gets a chance to propagate it.
        with pytest.raises(KeyError) as predecessor_error:
            graph.pred[1][missing]
        predecessor_errors.append(predecessor_error.value.args)
        view = graph.to_undirected(as_view=True)
        with pytest.raises(KeyError) as error:
            view.adj[1][missing]
        errors.append(error.value.args)
    assert errors[0] == errors[1]
    assert predecessor_errors[0] == predecessor_errors[1]
    if not filtered:
        assert errors[1] == (missing,)


@pytest.mark.parametrize("graph_type,kind", [
    ("Graph", "filtered"), ("DiGraph", "filtered"),
    ("MultiGraph", "filtered"), ("MultiDiGraph", "filtered"),
    ("DiGraph", "reverse"), ("MultiDiGraph", "reverse"),
])
def test_partial_view_constructor_cycle_is_collected(graph_type, kind):
    """An error before the first setattr must not hide the view's GC edges."""
    import gc
    import weakref

    parent_class = getattr(fnx, graph_type)
    ordinary_parent = parent_class()
    if kind == "reverse":
        view_class = type(ordinary_parent.reverse(copy=False))
    else:
        view_class = type(fnx.subgraph_view(ordinary_parent))
    refs = []

    class InterruptedParent(parent_class):
        @property
        def graph(self):
            if "partial_view" in self.__dict__:
                raise ValueError("injected graph attribute access failure")
            return super().graph

    class InterruptedView(view_class):
        def __new__(cls, parent):
            view = super().__new__(cls)
            # A real parent/view cycle exists before graph.graph can fail.
            # The parent's canonical initializer has registered its dict.
            parent.__dict__["partial_view"] = view
            refs.extend((weakref.ref(parent), weakref.ref(view)))
            return view

    def construct():
        parent = InterruptedParent()
        with pytest.raises(ValueError, match="injected graph attribute access failure"):
            InterruptedView(parent)

    construct()
    assert len(refs) == 2
    gc.collect()
    assert all(ref() is None for ref in refs)


_CONSTRUCTOR_CASES = [
    (graph_type, kind)
    for graph_type in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for kind in ("subgraph", "restricted")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")]


def _constructor_view(lib, graph, kind):
    if kind == "subgraph":
        return graph.subgraph(list(graph))
    if kind == "restricted":
        return lib.restricted_view(graph, [], [])
    return graph.reverse(copy=False)


def _constructor_reads(view):
    names = ("adj", "succ", "pred") if view.is_directed() else ("adj",)
    degree_names = ("degree", "in_degree", "out_degree") if view.is_directed() else ("degree",)
    return (
        list(view.nodes(data=True)),
        list(view.edges(keys=True, data=True)) if view.is_multigraph() else list(view.edges(data=True)),
        [(name, [(u, list(row)) for u, row in getattr(view, name).items()]) for name in names],
        [(name, list(getattr(view, name)(weight="weight"))) for name in degree_names],
        [(u, v, view.get_edge_data(u, v)) for u in view for v in view],
    )


@pytest.mark.parametrize("graph_type,kind", _CONSTRUCTOR_CASES)
def test_fresh_view_constructor_preserves_live_storage_and_accessors(graph_type, kind):
    pairs = []
    for lib in (fnx, nx):
        graph = getattr(lib, graph_type)()
        graph.add_nodes_from(["a", 2, ("c", 3), "isolated"])
        graph.add_edge("a", 2, weight=2.5)
        graph.add_edge(2, ("c", 3), weight=3)
        graph.add_edge(2, 2, weight=4)
        if graph.is_multigraph():
            graph.add_edge("a", 2, key="parallel", weight=7)
        view = _constructor_view(lib, graph, kind)
        assert view.graph is graph.graph
        for name in ("nodes", "edges", "adj", "degree"):
            assert getattr(view, name) is getattr(view, name)
        if view.is_directed():
            assert view.adj is not view.succ
        pairs.append((graph, view))
    assert _constructor_reads(pairs[0][1]) == _constructor_reads(pairs[1][1])
    for graph, view in pairs:
        edge = ("a", 2, 0) if graph.is_multigraph() else ("a", 2)
        graph.edges[edge]["weight"] = 11
        graph.nodes[2]["payload"] = ["live"]
        graph.graph["live"] = True
        graph.remove_edge(2, ("c", 3))
        graph.add_edge("isolated", 2, weight=1.25)
        assert view.graph["live"] is True
    assert _constructor_reads(pairs[0][1]) == _constructor_reads(pairs[1][1])


@pytest.mark.parametrize("graph_type,kind", _CONSTRUCTOR_CASES)
@pytest.mark.parametrize("warm", [False, True])
def test_fresh_view_constructor_cycles_are_collected(graph_type, kind, warm):
    import gc
    import weakref

    def references(lib):
        graph = getattr(lib, graph_type)()
        graph.add_edge("a", "b", weight=2)
        view = _constructor_view(lib, graph, kind)
        graph.graph["view_cycle"] = view
        if warm:
            _constructor_reads(view)
        return weakref.ref(graph), weakref.ref(view)

    for lib in (nx, fnx):
        refs = references(lib)
        gc.collect()
        assert all(ref() is None for ref in refs)


@pytest.mark.parametrize("graph_type,kind", _CONSTRUCTOR_CASES)
def test_view_constructor_keeps_subclass_setattr_hooks(graph_type, kind):
    graph = getattr(fnx, graph_type)()
    graph.add_edge("a", "b")
    base = type(_constructor_view(fnx, graph, kind))
    assignments = []

    class CustomView(base):
        def __setattr__(self, name, value):
            assignments.append(name)
            return super().__setattr__(name, value)

    view = CustomView(graph)
    assert "frozen" in assignments
    assert fnx._PRIVATE_ADJ_OVERRIDE in assignments
    if kind != "reverse":
        assert "nodes" in assignments
    if graph.is_directed():
        assert fnx._PRIVATE_SUCC_OVERRIDE in assignments
        assert fnx._PRIVATE_PRED_OVERRIDE in assignments
    assert view.number_of_nodes() == 2


@pytest.mark.parametrize("graph_type,kind", _CONSTRUCTOR_CASES)
def test_reinitialized_view_constructor_invalidates_cached_storage(graph_type, kind):
    first = getattr(fnx, graph_type)()
    first.add_edge("old", "node", weight=3)
    view = _constructor_view(fnx, first, kind)
    _constructor_reads(view)
    old_degree = view.degree
    supplied_method = lambda *args, **kwargs: "user-owned"
    view.get_edge_data = supplied_method
    second = getattr(fnx, graph_type)()
    second.add_edge("new", "target", weight=7)
    second.add_edge("target", "target", weight=2)
    view.__init__(second)
    assert view._graph is second
    assert view.graph is second.graph
    assert view.degree is not old_degree
    assert view.get_edge_data is supplied_method
    del view.get_edge_data
    # Reinstall mapping-aware shadows after intentionally removing the user's
    # method; the constructor itself must never replace it.
    fnx._install_private_method_shadows(view, view.__dict__)
    expected = getattr(nx, graph_type)()
    expected.add_edge("new", "target", weight=7)
    expected.add_edge("target", "target", weight=2)
    # Reinitialization without filters makes a filtered view unfiltered.
    reference = expected.reverse(copy=False) if kind == "reverse" else nx.subgraph_view(expected)
    assert _constructor_reads(view) == _constructor_reads(reference)


def _materialization_source(lib, graph_type):
    graph = getattr(lib, graph_type)()
    shared = ["shared"]
    graph.graph.update(payload=shared, alias=shared)
    graph.add_nodes_from(["a", "b", "c", "isolated", "hidden"])
    graph.nodes["a"].update({"payload": shared, "alias": shared, 17: "node-value"})
    edges = [
        ("a", "b", ("road", 0), {"weight": 2, "forward_only": True, "payload": shared, "alias": shared}),
        ("b", "a", ("road", 0), {"weight": 7, "backward_only": True, 17: "edge-value"}),
        ("b", "c", "road", {"weight": 3}),
        ("a", "c", "shortcut", {"weight": 8}),
        ("b", "b", "loop", {"weight": 5}),
        ("hidden", "c", "hidden", {"weight": 23}),
    ]
    if graph.is_multigraph():
        graph.add_edges_from(edges)
        graph.add_edge("a", "b", key=1024, weight=19)
    else:
        graph.add_edges_from((u, v, attrs) for u, v, _, attrs in edges)
    return graph


def _materialized_graph_state(graph):
    edges = list(graph.edges(keys=True, data=True)) if graph.is_multigraph() else list(graph.edges(data=True))
    rows = [(node, list(graph.adj[node])) for node in graph]
    predecessors = [(node, list(graph.pred[node])) for node in graph] if graph.is_directed() else None
    return dict(graph.graph), list(graph.nodes(data=True)), edges, rows, predecessors


def _materialization_view(lib, source, outer):
    view = source.to_undirected(as_view=True)
    if outer == "filtered":
        return view.subgraph(["a", "b", "c", "isolated"])
    if outer == "edge_subgraph":
        edges = list(view.edges(keys=True)) if view.is_multigraph() else list(view.edges())
        return view.edge_subgraph([edge for edge in edges if "hidden" not in edge[:2]])
    if outer == "restricted":
        return lib.restricted_view(view, ["hidden"], [])
    if outer == "nested":
        return lib.restricted_view(view, ["hidden"], []).subgraph(["a", "b", "c"])
    return view


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("outer", ["conversion", "filtered", "edge_subgraph", "restricted", "nested"])
def test_conversion_copy_merges_reciprocal_attributes_in_adjacency_order(graph_type, outer):
    results = []
    for lib in (fnx, nx):
        source = _materialization_source(lib, graph_type)
        view = _materialization_view(lib, source, outer)
        before = _materialized_graph_state(source)
        copied = view.copy()
        assert not lib.is_frozen(copied)
        assert _materialized_graph_state(source) == before
        assert copied.graph is not source.graph
        assert copied.graph["payload"] is source.graph["payload"]
        assert copied.nodes["a"] is not source.nodes["a"]
        assert copied.nodes["a"]["payload"] is source.nodes["a"]["payload"]
        attrs = copied["a"]["b"][("road", 0)] if copied.is_multigraph() else copied["a"]["b"]
        assert attrs["payload"] is source.graph["payload"]
        assert attrs["forward_only"] and attrs["backward_only"]
        assert attrs["weight"] == 7
        assert attrs[17] == "edge-value"
        # The overwritten weight changes a real routing decision, not just
        # the spelling of the copied attribute dictionary.
        assert lib.shortest_path(copied, "a", "c", weight="weight") == ["a", "c"]
        results.append(_materialized_graph_state(copied))
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("conversion", ["to_directed", "to_undirected"])
def test_conversion_copy_as_view_keeps_a_frozen_live_graph(graph_type, conversion):
    results = []
    for lib in (fnx, nx):
        source = _materialization_source(lib, graph_type)
        view = getattr(source, conversion)(as_view=True)
        copied = view.copy(as_view=True)
        assert copied._graph is view
        assert copied.graph is source.graph
        assert copied.nodes["a"] is source.nodes["a"]
        assert lib.is_frozen(copied)
        with pytest.raises(lib.NetworkXError, match="Frozen graph can't be modified"):
            copied.add_edge("forbidden", "write")
        source.add_edge("a", "late", weight=29)
        copied.nodes["a"]["through_view"] = True
        assert source.nodes["a"]["through_view"] is True
        results.append(_materialized_graph_state(copied))
        source.clear()
        assert len(copied) == copied.number_of_edges() == 0
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("parent_kind", ["directed", "union"])
def test_conversion_reverse_copy_deepcopies_attributes_and_preserves_row_order(graph_type, parent_kind):
    results = []
    for lib in (fnx, nx):
        source = _materialization_source(lib, graph_type)
        parent = source if parent_kind == "directed" else source.to_undirected(as_view=True)
        view = parent.to_directed(as_view=True)
        before = _materialized_graph_state(source)
        copied = view.reverse()
        assert not lib.is_frozen(copied)
        assert copied.graph["payload"] is not source.graph["payload"]
        assert copied.graph["payload"] is copied.graph["alias"]
        assert copied.nodes["a"]["payload"] is not source.nodes["a"]["payload"]
        assert copied.nodes["a"]["payload"] is copied.nodes["a"]["alias"]
        assert copied.nodes["a"]["payload"] is not copied.graph["payload"]
        attrs = copied["b"]["a"][("road", 0)] if copied.is_multigraph() else copied["b"]["a"]
        assert attrs["payload"] is attrs["alias"]
        assert attrs["payload"] is not source.graph["payload"]
        assert attrs["payload"] is not copied.nodes["a"]["payload"]
        attrs["payload"].append("copy-only")
        assert _materialized_graph_state(source) == before
        results.append(_materialized_graph_state(copied))
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_conversion_reverse_copy_observes_deepcopy_callback_mutation(graph_type):
    results = []
    for lib in (fnx, nx):
        source = getattr(lib, graph_type)([("a", "b")])
        calls = []

        class AddEdgeOnCopy:
            def __deepcopy__(self, memo):
                calls.append("graph-data")
                source.add_edge("b", "late", weight=5)
                return "copied"

        source.graph["payload"] = AddEdgeOnCopy()
        view = source.to_directed(as_view=True)
        copied = view.reverse(copy=True)
        assert calls == ["graph-data"]
        assert copied.has_edge("late", "b")
        assert copied.graph["payload"] == "copied"
        results.append(_materialized_graph_state(copied))
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("outer", ["conversion", "filtered", "edge_subgraph", "nested"])
@pytest.mark.parametrize("input_kind", ["native", "networkx"])
def test_conversion_weighted_queries_keep_directional_union_rows(graph_type, outer, input_kind):
    source_lib = fnx if input_kind == "native" else nx
    actual = _materialization_view(source_lib, _materialization_source(source_lib, graph_type), outer)
    expected = _materialization_view(nx, _materialization_source(nx, graph_type), outer)
    for source, target, distance in (("a", "b", 2), ("b", "a", 7)):
        for name in (
            "shortest_path_length", "dijkstra_path_length",
            "bellman_ford_path_length", "astar_path_length",
        ):
            assert getattr(fnx, name)(actual, source, target, weight="weight") == distance
            assert getattr(nx, name)(expected, source, target, weight="weight") == distance
        for name in ("shortest_path", "dijkstra_path", "bellman_ford_path", "astar_path", "bidirectional_dijkstra"):
            assert getattr(fnx, name)(actual, source, target, weight="weight") == getattr(nx, name)(expected, source, target, weight="weight")
        for name in (
            "single_source_dijkstra", "single_source_dijkstra_path",
            "single_source_dijkstra_path_length", "single_source_bellman_ford",
            "single_source_bellman_ford_path", "single_source_bellman_ford_path_length",
            "dijkstra_predecessor_and_distance", "bellman_ford_predecessor_and_distance",
        ):
            assert getattr(fnx, name)(actual, source, weight="weight") == getattr(nx, name)(expected, source, weight="weight")
    for name in ("all_pairs_dijkstra_path_length", "all_pairs_bellman_ford_path_length"):
        assert list(getattr(fnx, name)(actual, weight="weight")) == list(getattr(nx, name)(expected, weight="weight"))
    for method in (None, "dijkstra", "bellman-ford"):
        assert fnx.average_shortest_path_length(actual.subgraph(["a", "b", "c"]), weight="weight", method=method) == nx.average_shortest_path_length(expected.subgraph(["a", "b", "c"]), weight="weight", method=method)


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["native", "networkx"])
def test_conversion_weighted_callback_reads_and_changes_original_attributes(graph_type, input_kind):
    results = []
    for lib, source_lib in ((fnx, fnx if input_kind == "native" else nx), (nx, nx)):
        source = _materialization_source(source_lib, graph_type)
        view = _materialization_view(source_lib, source, "nested")
        calls = []

        def weight(u, v, data):
            edge_data = data.items() if view.is_multigraph() else [(None, data)]
            values = []
            for key, attrs in edge_data:
                args = (u, v, key) if view.is_multigraph() else (u, v)
                original = source.get_edge_data(*args)
                if original is None:
                    args = (v, u, key) if view.is_multigraph() else (v, u)
                    original = source.get_edge_data(*args)
                assert attrs is original
                values.append(attrs.get("weight", 1))
            calls.append((u, v, tuple(values)))
            if (u, v) == ("a", "b"):
                future = source["b"]["c"]["road"] if view.is_multigraph() else source["b"]["c"]
                future["weight"] = 1
            return min(values)

        result = lib.single_source_dijkstra(view, "a", weight=weight)
        assert result[0]["c"] == 3
        results.append((result, calls))
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_conversion_weighted_iterator_observes_live_filter_and_arc_changes(graph_type):
    results = []
    for lib in (fnx, nx):
        source = _materialization_source(lib, graph_type)
        allowed = {frozenset(("a", "b")), frozenset(("b", "c"))}
        view = lib.subgraph_view(
            source.to_undirected(as_view=True),
            filter_node=lambda node: node in {"a", "b", "c"},
            filter_edge=lambda u, v, *keys: frozenset((u, v)) in allowed,
        )
        iterator = lib.all_pairs_dijkstra_path_length(view, weight="weight")
        attrs = source["b"]["a"][("road", 0)] if view.is_multigraph() else source["b"]["a"]
        attrs["weight"] = 9
        first = next(iterator)
        assert first[1]["c"] == 5
        allowed.remove(frozenset(("a", "b")))
        allowed.add(frozenset(("a", "c")))
        rest = list(iterator)
        assert dict(rest)["b"]["a"] == 11
        if view.is_multigraph():
            source.add_edge("c", "a", key="shortcut", weight=1)
        else:
            source.add_edge("c", "a", weight=1)
        assert lib.dijkstra_path_length(view, "b", "a", weight="weight") == 4
        results.append((first, rest))
    assert results[0] == results[1]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("outer", ["conversion", "nested"])
def test_conversion_native_snapshot_keeps_edge_walk_separate_from_public_copy(graph_type, outer):
    source = _materialization_source(fnx, graph_type)
    view = _materialization_view(fnx, source, outer)
    snapshot = fnx._materialize_view(view)
    copied = view.copy()
    assert not snapshot.is_directed()
    if snapshot.is_multigraph():
        assert snapshot["a"]["b"][("road", 0)]["weight"] == 2
        assert copied["a"]["b"][("road", 0)]["weight"] == 7
    else:
        assert snapshot["a"]["b"]["weight"] == 2
        assert copied["a"]["b"]["weight"] == 7
    assert snapshot.graph is source.graph


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_conversion_named_weighted_algorithms_treat_none_as_an_attribute_key(graph_type):
    results = []
    for lib in (fnx, nx):
        source = getattr(lib, graph_type)()
        source.add_edges_from([
            ("a", "b", {None: 2, "weight": 20}),
            ("b", "a", {None: 7, "weight": 70}),
        ])
        view = source.to_undirected(as_view=True).subgraph(["a", "b"])
        lengths = []
        for u, v, distance in (("a", "b", 2), ("b", "a", 7)):
            for name in ("dijkstra_path_length", "bellman_ford_path_length"):
                value = getattr(lib, name)(view, u, v, weight=None)
                assert value == distance
                lengths.append(value)
            # Generic shortest-path APIs give None its separate unweighted
            # meaning; named weighted algorithms look up the None key.
            assert lib.shortest_path_length(view, u, v, weight=None) == 1
        for name in ("single_source_dijkstra_path_length", "single_source_bellman_ford_path_length"):
            values = getattr(lib, name)(view, "b", weight=None)
            assert values == {"b": 0, "a": 7}
            lengths.append(values)
        results.append(lengths)
    assert results[0] == results[1]
