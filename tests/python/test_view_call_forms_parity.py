"""A view's edges() / nodes() CALLED return networkx's views, not lists.

br-r37-c1-77tw1: on every fnx view kind (subgraph, restricted_view,
edge_subgraph, reverse, to_directed / to_undirected(as_view=True)) the call
forms V.edges(), V.edges(data=...), V.edges(nbunch), V.nodes(),
V.nodes(data=...) returned plain lists - no networkx class name, no set
algebra, no .data(), a snapshot rather than live - and the module functions
fnx.edges / fnx.nodes / fnx.to_edgelist inherited it. networkx returns the
view itself for a plain call (a multigraph edge view only with keys=True) and
a live EdgeDataView / NodeDataView otherwise.

Each row builds the same view in both libraries and compares the type name,
the contents, membership by networkx's rules (an undirected edge in either
orientation; a multiedge by key; a (node, data) pair), repr and len - then
mutates the parent and compares again (liveness).
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _views(lib):
    dg = lib.DiGraph()
    dg.add_edge(0, 1, w=1)
    dg.add_edge(1, 2, w=2)
    dg.add_edge(2, 0)
    dg.nodes[0]["c"] = "r"
    g = lib.Graph()
    g.add_edge(0, 1, w=1)
    g.add_edge(1, 2)
    g.add_edge(2, 3, w=4)
    mdg = lib.MultiDiGraph()
    mdg.add_edge(0, 1, w=1)
    mdg.add_edge(0, 1, w=5)
    mdg.add_edge(1, 2)
    mg = lib.MultiGraph()
    mg.add_edge(0, 1, w=1)
    mg.add_edge(0, 1)
    mg.add_edge(1, 2)
    return {
        "D.sub": (dg, dg.subgraph([0, 1, 2])),
        "D.reverse": (dg, dg.reverse(copy=False)),
        "G.sub": (g, g.subgraph([0, 1, 2, 3])),
        "G.restricted": (g, lib.restricted_view(g, [], [(1, 2)])),
        "G.edge_sub": (g, g.edge_subgraph([(0, 1), (2, 3)])),
        "G.to_directed": (g, g.to_directed(as_view=True)),
        "MDG.sub": (mdg, mdg.subgraph([0, 1, 2])),
        "MDG.reverse": (mdg, mdg.reverse(copy=False)),
        "MG.sub": (mg, mg.subgraph([0, 1, 2])),
        "MG.to_directed": (mg, mg.to_directed(as_view=True)),
    }


KINDS = list(_views(nx))

CALLS = {
    "edges()": lambda V: V.edges(),
    "edges(data=True)": lambda V: V.edges(data=True),
    "edges(data='w', default)": lambda V: V.edges(data="w", default=-1),
    "edges(nbunch)": lambda V: V.edges([0]),
    "edges(node, data)": lambda V: V.edges(1, data=True),
    "edges.data('w')": lambda V: V.edges.data("w"),
    "nodes()": lambda V: V.nodes(),
    "nodes(data=True)": lambda V: V.nodes(data=True),
    "nodes(data='c', default)": lambda V: V.nodes(data="c", default="x"),
    "nodes.data()": lambda V: V.nodes.data(),
    "fnx.edges / nx.edges": None,
}
MULTI_CALLS = {
    "edges(keys=True)": lambda V: V.edges(keys=True),
    "edges(keys=True, data=True)": lambda V: V.edges(keys=True, data=True),
    "edges([1], keys=True)": lambda V: V.edges([1], keys=True),
}

# Membership probes a data view answers by lookup. (Malformed tuples against
# the EDGE view itself - networkx raises ValueError, fnx answers False - and a
# 3-tuple against fnx's NodeDataView are not this change.)
EDGE_PROBES = [(1, 0), (0, 1), (0, 1, 0), (0, 1, 1), (1, 0, 1), (0, 1, {"w": 1}), (1, 0, {"w": 1}), (0, 1, 0, {"w": 1})]
NODE_PROBES = [0, 7, (0, "r"), (1, "x"), (0, {"c": "r"})]


def _outcome(f):
    try:
        return "ok", f()
    except Exception as exc:  # noqa: BLE001 - the exception IS the outcome compared
        return "raise", type(exc).__name__


def _describe(result, probes):
    return (
        type(result).__name__,
        _outcome(lambda: list(result)),
        [_outcome(lambda p=p: p in result) for p in probes],
        _outcome(lambda: repr(result)),
        _outcome(lambda: len(result)),
    )


def _rows(view):
    rows = {k: v for k, v in CALLS.items() if v is not None}
    if view.is_multigraph():
        rows.update(MULTI_CALLS)
    return rows


@pytest.mark.parametrize("kind", KINDS)
def test_view_call_forms_are_networkxs_views(kind):
    fparent, fview = _views(fnx)[kind]
    nparent, nview = _views(nx)[kind]
    held = {name: (call(fview), call(nview)) for name, call in _rows(nview).items()}
    for name, (fres, nres) in held.items():
        probes = NODE_PROBES if name.startswith("nodes") else EDGE_PROBES
        if name in ("edges()", "edges(keys=True)"):
            # The edge view itself: compare everything but malformed-tuple
            # membership (see EDGE_PROBES).
            assert type(fres).__name__ == type(nres).__name__, name
            assert list(fres) == list(nres), name
            assert repr(fres) == repr(nres), name
            continue
        assert _describe(fres, probes) == _describe(nres, probes), name
    fparent.add_edge(0, 2, w=9)
    nparent.add_edge(0, 2, w=9)
    for name, (fres, nres) in held.items():
        assert list(fres) == list(nres), f"{name} after the parent gained an edge"


@pytest.mark.parametrize("kind", KINDS)
def test_plain_call_returns_the_view_itself(kind):
    _, fview = _views(fnx)[kind]
    _, nview = _views(nx)[kind]
    assert (fview.edges() is fview.edges) == (nview.edges() is nview.edges) or (
        type(fview.edges()).__name__ == type(nview.edges()).__name__
    )
    assert type(fview.nodes()).__name__ == type(nview.nodes()).__name__ == "NodeView"
    # set algebra and .data() on what the plain call returns, as on networkx's
    # (a multigraph edge view's plain call is edges(keys=True))
    if nview.is_multigraph():
        fplain, nplain, probe = fview.edges(keys=True), nview.edges(keys=True), {(0, 1, 0)}
    else:
        fplain, nplain, probe = fview.edges(), nview.edges(), {(0, 1)}
    assert (fplain & probe) == (nplain & probe)
    assert list(fview.nodes().data("c")) == list(nview.nodes().data("c"))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("name", ["edges", "nodes", "to_edgelist"])
def test_module_functions_on_a_view(kind, name):
    _, fview = _views(fnx)[kind]
    _, nview = _views(nx)[kind]
    fres, nres = getattr(fnx, name)(fview), getattr(nx, name)(nview)
    assert type(fres).__name__ == type(nres).__name__
    assert list(fres) == list(nres)


def test_a_data_views_nbunch_is_resolved_at_the_call():
    # networkx resolves nbunch through nbunch_iter when the data view is made:
    # a missing node raises then, a repeated node counts once.
    for lib in (fnx, nx):
        view = lib.DiGraph([(0, 1), (1, 2)]).subgraph([0, 1, 2])
        with pytest.raises(lib.NetworkXError):
            view.edges(9, data=True)
        assert list(view.edges([0, 0, 1])) == [(0, 1), (1, 2)]


# A view is true when it has a node: its truthiness came from the PyO3 graph
# class's native __bool__, which read the view's EMPTY Rust base, so every view
# was false - `if view:` took the empty branch, and networkx code handed a view
# did too (read_graphml(view) got past ElementTree's `if file:` and failed on an
# empty tree instead of raising networkx's TypeError).
def _bool_views(lib):
    dg = lib.DiGraph([(0, 1), (1, 2)])
    g = lib.Graph([(0, 1)])
    return [
        dg.subgraph([0, 1]),
        dg.subgraph([]),
        dg.reverse(copy=False),
        lib.DiGraph().reverse(copy=False),
        dg.to_undirected(as_view=True),
        g.to_directed(as_view=True),
        lib.Graph().to_directed(as_view=True),
        lib.restricted_view(g, [], []),
        lib.restricted_view(g, [0, 1], []),
        g.edge_subgraph([(0, 1)]),
        lib.MultiGraph([(0, 1)]).subgraph([0]),
        lib.MultiDiGraph([(0, 1)]).reverse(copy=False),
        dg.subgraph([0, 1]).reverse(copy=False),
    ]


def test_a_view_is_true_when_it_has_a_node():
    assert [bool(v) for v in _bool_views(fnx)] == [bool(v) for v in _bool_views(nx)]
    assert [bool(v) for v in _bool_views(fnx)].count(False) == 4


def test_read_graphml_of_a_view_raises_networkxs_type_error():
    outcomes = []
    for lib in (fnx, nx):
        with pytest.raises(TypeError) as err:
            lib.read_graphml(lib.DiGraph([(0, 1)]).subgraph([0]))
        outcomes.append(str(err.value))
    assert outcomes[0] == outcomes[1]


def test_a_views_repr_counts_the_view():
    # fnx's graph repr is its own (networkx prints the default object repr);
    # a view's must count the view - the inherited native __repr__ read the
    # empty base and printed nodes=0, edges=0 for every view.
    for view in _bool_views(fnx):
        assert repr(view) == repr(view.copy())
