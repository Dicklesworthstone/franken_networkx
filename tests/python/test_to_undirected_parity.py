"""Parity coverage for `to_undirected(as_view=..., reciprocal=...)`.

Bead franken_networkx-5vyu: the core graph classes must accept
NetworkX's conversion keyword surface — as_view on all four families
and reciprocal on the directed pair.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_as_view_returns_frozen_view(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2)])

    fv = fg.to_undirected(as_view=True)
    nv = ng.to_undirected(as_view=True)

    # View must be frozen on both sides.
    assert fnx.is_frozen(fv)
    assert nx.is_frozen(nv)

    # Same edge set (sorted by endpoint pair for undirected comparison).
    f_edges = sorted(sorted(e) for e in fv.edges())
    n_edges = sorted(sorted(e) for e in nv.edges())
    assert f_edges == n_edges


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_reciprocal_keeps_only_bidirectional_edges(fnx_ctor, nx_ctor):
    """reciprocal=True: keep an undirected edge only when the original
    had edges in both directions.
    """
    fg = fnx_ctor()
    fg.add_edge(0, 1)   # single direction
    fg.add_edge(1, 0)   # reverse — pair
    fg.add_edge(2, 3)   # single direction only
    ng = nx_ctor()
    ng.add_edge(0, 1)
    ng.add_edge(1, 0)
    ng.add_edge(2, 3)

    fu = fg.to_undirected(reciprocal=True)
    nu = ng.to_undirected(reciprocal=True)

    # Both should have the bidirectional pair but not the single edge.
    assert sorted(sorted(e) for e in fu.edges()) == sorted(
        sorted(e) for e in nu.edges()
    )
    # Specifically: (0, 1) retained, (2, 3) dropped.
    fu_edges = {frozenset(e) for e in fu.edges()}
    assert frozenset((0, 1)) in fu_edges
    assert frozenset((2, 3)) not in fu_edges


# br-r37-c1-fiitj: reciprocal=True takes the native deep copy the plain form
# already used (it rebuilt in Python at 0.56-0.59x networkx). The result must be
# networkx's exactly: which arcs survive, how a pair's two dicts merge (the
# second direction's values win, its new keys go after the first's), node,
# row and edge order, keys of a multigraph, and a deep copy of every dict.

def _reciprocal_source(lib, cls, shape):
    G = getattr(lib, cls)()
    G.graph["tags"] = ["a", "b"]
    multi = cls == "MultiDiGraph"
    if shape == "mixed":
        G.add_node(9, z=1, a=2)
        G.add_edge(0, 1, weight=1, color="red")
        G.add_edge(2, 3, weight=5)  # one way
        G.add_edge(1, 0, cap=2.5, weight=4)  # the pair merges
        G.add_edge(4, 4, weight=7)  # a self-loop is its own reverse
        G.add_edge(3, 5)
        G.add_edge(5, 3, pos=(1, 2))  # a value the store cannot hold
        G.add_edge(6, 7, weight=1)
        G.add_edge(7, 6)
    elif shape == "str_nodes":
        G.add_edges_from([("b", "a", {"w": 1}), ("a", "b", {"w": 2, "k": 0}), ("a", "c", {})])
        G.add_edges_from([("c", "d", {"w": 3}), ("d", "c", {"w": 4})])
    elif shape == "keys" and multi:
        G.add_edge(0, 1, key="x", weight=1)
        G.add_edge(1, 0, key="x", weight=2)  # same key back: kept
        G.add_edge(0, 1, key="y")  # no 'y' back: dropped
        G.add_edge(1, 0, key="z")
        G.add_edge(2, 3, key=1, w=1)
        G.add_edge(3, 2, key=True, w=2)  # 1 == True as a dict key
        G.add_edge(2, 3, key=2.0)
        G.add_edge(3, 2, key=2)
        G.add_edge(0, 1)  # auto keys
        G.add_edge(0, 1)
        G.add_edge(1, 0)
    elif shape == "keys":
        return None
    else:  # bulk
        edges = [(u, (u * 7 + 3) % 40, {"weight": u % 5}) for u in range(40)]
        G.add_edges_from(edges)
        G.add_edges_from([(v, u, {"weight": d["weight"] + 1}) for u, v, d in edges[::3]])
    return G


def _undirected_shape(G):
    if G.is_multigraph():
        edges = [(repr(u), repr(v), repr(k), list(d.items())) for u, v, k, d in G.edges(keys=True, data=True)]
    else:
        edges = [(repr(u), repr(v), list(d.items())) for u, v, d in G.edges(data=True)]
    return (
        type(G).__name__,
        G.graph,
        [(repr(n), list(d.items())) for n, d in G.nodes(data=True)],
        [(repr(n), [repr(m) for m in G[n]]) for n in G],
        edges,
    )


@pytest.mark.parametrize("shape", ["mixed", "str_nodes", "keys", "bulk"])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_to_undirected_reciprocal_matches_networkx_exactly(cls, shape):
    fsrc = _reciprocal_source(fnx, cls, shape)
    if fsrc is None:
        pytest.skip("parallel keys need a multigraph")
    nsrc = _reciprocal_source(nx, cls, shape)
    fu = fsrc.to_undirected(reciprocal=True)
    nu = nsrc.to_undirected(reciprocal=True)
    assert _undirected_shape(fu) == _undirected_shape(nu)
    # A deep copy: writing the result leaves the source alone.
    fu.graph["tags"].append("c")
    for _, _, d in fu.edges(data=True):
        d["weight"] = -1
    assert fsrc.graph["tags"] == ["a", "b"]
    assert _undirected_shape(fsrc.to_undirected(reciprocal=True)) == _undirected_shape(nu)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_to_undirected_reciprocal_takes_the_native_copy(cls, monkeypatch):
    klass = getattr(fnx, cls)
    native = klass._native_to_undirected_deepcopy
    calls = []

    def counting(self, *args, **kwargs):
        calls.append(kwargs)
        return native(self, *args, **kwargs)

    monkeypatch.setattr(klass, "_native_to_undirected_deepcopy", counting)
    _reciprocal_source(fnx, cls, "mixed").to_undirected(reciprocal=True)
    assert calls == [{"reciprocal": True}]


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_directed", fnx.MultiGraph, nx.MultiGraph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
        ("to_undirected", fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_conversion_live_view_exposes_nbunch_iter(direction, fnx_ctor, nx_ctor):
    """Bead franken_networkx-veds: conversion live views expose
    nbunch_iter(bunch) that filters to nodes present in the view,
    matching upstream.
    """
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2)])

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    assert hasattr(fv, "nbunch_iter")

    # Subset + unknown node — only present nodes returned.
    assert list(fv.nbunch_iter([0, 99])) == list(nv.nbunch_iter([0, 99]))
    # None argument returns all nodes.
    assert sorted(fv.nbunch_iter(None)) == sorted(nv.nbunch_iter(None))
    # Single node.
    assert list(fv.nbunch_iter(1)) == list(nv.nbunch_iter(1))


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
    ],
)
def test_conversion_live_view_exposes_dict_factory_attributes(direction, fnx_ctor, nx_ctor):
    """Bead franken_networkx-i4b8: top-level to_undirected / to_directed
    conversion live views must expose NetworkX's dict-factory attribute
    surface — each materialising an empty dict by default.
    """
    fg = fnx_ctor()
    fg.add_edge(0, 1)
    ng = nx_ctor()
    ng.add_edge(0, 1)

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    factories = (
        "adjlist_inner_dict_factory",
        "adjlist_outer_dict_factory",
        "edge_attr_dict_factory",
        "graph_attr_dict_factory",
        "node_attr_dict_factory",
        "node_dict_factory",
    )
    for attr in factories:
        assert hasattr(fv, attr), f"fnx view missing {attr}"
        assert hasattr(nv, attr), f"nx view missing {attr}"
        f_factory = getattr(fv, attr)
        assert callable(f_factory)
        assert f_factory() == {}


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_reciprocal_false_matches_default(fnx_ctor, nx_ctor):
    """reciprocal=False keeps all undirected edges, matching the
    default behaviour.
    """
    fg = fnx_ctor()
    fg.add_edge(0, 1)
    fg.add_edge(2, 3)
    ng = nx_ctor()
    ng.add_edge(0, 1)
    ng.add_edge(2, 3)

    fu = fg.to_undirected(reciprocal=False)
    nu = ng.to_undirected(reciprocal=False)
    assert sorted(sorted(e) for e in fu.edges()) == sorted(
        sorted(e) for e in nu.edges()
    )


@pytest.mark.parametrize("reciprocal", [None, 0, 1, "true"])
@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_only_literal_true_filters_reciprocal_edges(
    reciprocal, fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    ng = nx_ctor()
    for graph in (fg, ng):
        if graph.is_multigraph():
            graph.add_edge("a", "b", key="ab")
            graph.add_edge("b", "a", key="other")
            graph.add_edge("c", "d", key="cd")
        else:
            graph.add_edge("a", "b")
            graph.add_edge("b", "a")
            graph.add_edge("c", "d")

    fu = fg.to_undirected(reciprocal=reciprocal)
    nu = ng.to_undirected(reciprocal=reciprocal)

    if fu.is_multigraph():
        assert list(fu.edges(keys=True)) == list(nu.edges(keys=True))
    else:
        assert list(fu.edges()) == list(nu.edges())
