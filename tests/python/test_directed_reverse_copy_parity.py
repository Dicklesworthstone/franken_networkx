"""Parity coverage for DiGraph.reverse(copy=...) / MultiDiGraph.reverse(copy=...).

Bead franken_networkx-b7fx: both directed graph classes must accept
the ``copy`` keyword matching upstream — copy=True materialises a
fresh reversed DiGraph, copy=False returns a frozen live reverse_view.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_copy_true_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fr = fg.reverse(copy=True)
    nr = ng.reverse(copy=True)

    assert sorted(fr.edges()) == sorted(nr.edges())
    # copy=True produces a materialised (mutable) graph.
    assert not fnx.is_frozen(fr)
    assert not nx.is_frozen(nr)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_copy_false_returns_frozen_view(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fr = fg.reverse(copy=False)
    nr = ng.reverse(copy=False)

    assert sorted(fr.edges()) == sorted(nr.edges())
    # copy=False produces a frozen live view.
    assert fnx.is_frozen(fr)
    assert nx.is_frozen(nr)
    assert isinstance(fr, fnx_ctor)
    assert isinstance(nr, nx_ctor)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_reverse_copy_false_returns_typed_frozen_view(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fr = fnx.reverse(fg, copy=False)
    nr = nx.reverse(ng, copy=False)

    assert sorted(fr.edges()) == sorted(nr.edges())
    assert fnx.is_frozen(fr)
    assert nx.is_frozen(nr)
    assert isinstance(fr, fnx_ctor)
    assert isinstance(nr, nx_ctor)


@pytest.mark.parametrize(
    "fnx_ctor",
    [fnx.DiGraph, fnx.MultiDiGraph],
)
def test_reverse_default_is_copy(fnx_ctor):
    """No-arg reverse() defaults to copy=True."""
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    r = fg.reverse()
    assert not fnx.is_frozen(r)
    assert sorted(r.edges()) == [(2, 1), (3, 2)]


def test_multidigraph_reverse_copy_preserves_keys_attrs_and_row_order():
    fg = fnx.MultiDiGraph()
    ng = nx.MultiDiGraph()
    edges = [
        ("a", "b", "k1", {"weight": 1}),
        ("c", "b", "k2", {"weight": 2}),
        ("a", "b", "k3", {"weight": 3}),
        ("b", "a", "k4", {"weight": 4}),
    ]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    fg["a"]["b"]["k1"]["weight"] = 11
    ng["a"]["b"]["k1"]["weight"] = 11

    fr = fg.reverse(copy=True)
    nr = ng.reverse(copy=True)

    assert list(fr.edges(keys=True, data="weight")) == list(
        nr.edges(keys=True, data="weight")
    )
    assert {
        node: {
            "succ": list(fr.succ[node]),
            "pred": list(fr.pred[node]),
        }
        for node in fr
    } == {
        node: {
            "succ": list(nr.succ[node]),
            "pred": list(nr.pred[node]),
        }
        for node in nr
    }
    fr["b"]["a"]["k1"]["weight"] = 101
    assert fg["a"]["b"]["k1"]["weight"] == 11


def test_multidigraph_reverse_copy_preserves_non_lossless_python_attrs():
    tuple_key = ("tuple-key", 1)
    facts = []
    for lib in (fnx, nx):
        g = lib.MultiDiGraph()
        payload = []
        g.add_edge("a", "b", key="k", payload=payload)
        g["a"]["b"]["k"][tuple_key] = "kept"

        r = g.reverse(copy=True)

        copied = r["b"]["a"]["k"]["payload"]
        r["b"]["a"]["k"]["new"] = 1
        facts.append(
            (
                copied == payload,
                copied is payload,  # br-r37-c1-uwvq4: networkx deep-copies it
                r["b"]["a"]["k"][tuple_key],
                "new" in g["a"]["b"]["k"],
            )
        )
    assert facts[0] == facts[1] == (True, False, "kept", False)


# br-r37-c1-uwvq4: networkx's reverse(copy=True) is
# H.graph.update(deepcopy(G.graph)), add_nodes_from((n, deepcopy(d)) ...),
# add_edges_from((v, u[, k], deepcopy(d)) ...): no value is shared with the
# original, and each dict is its own deepcopy call, so one object held by two
# dicts becomes two copies. fnx shared every value with the original.
def _identity_facts(lib, cls, store_only):
    shared = [1, 2]
    g = getattr(lib, cls)()
    g.graph["g"] = [9]
    g.graph["also_g"] = g.graph["g"]
    g.graph["s"] = "name"
    g.add_node(0, tag=[0], n=1)
    g.add_node(1, tag=shared)
    g.add_node(2, x=2.5)
    if store_only:
        g.add_edges_from([(0, 1, {"w": 3}), (1, 2, {"w": 4.5}), (2, 0, {"lab": "a"})])
    else:
        g.add_edge(0, 1, w=[1], sh=shared)
        g.add_edge(1, 2, w=[2], sh=shared)
        g.add_edge(2, 0, w=7, t=(1, [2]))
    r = g.reverse(copy=True)
    multi = g.is_multigraph()

    def data(graph, u, v):
        return graph[u][v][0] if multi else graph[u][v]

    facts = {
        "graph values copied": r.graph["g"] is not g.graph["g"],
        "one deepcopy for the graph dict": r.graph["also_g"] is r.graph["g"],
        "graph dict": dict(r.graph) == dict(g.graph),
        "nodes": list(r.nodes(data=True)) == list(g.nodes(data=True)),
        "node values copied": all(
            r.nodes[n][k] is not v
            for n, d in g.nodes(data=True)
            for k, v in d.items()
            if isinstance(v, list)
        ),
        "edges": sorted(map(repr, r.edges(data=True))) == sorted(repr((v, u, d)) for u, v, d in g.edges(data=True)),
    }
    for u, v in g.edges():
        for k, val in data(g, u, v).items():
            if isinstance(val, (list, tuple)):
                facts[f"edge {u}{v} {k} copied"] = data(r, v, u)[k] is not val
    if not store_only:
        facts["edge dicts copied apart"] = data(r, 1, 0)["sh"] is not data(r, 2, 1)["sh"]
        facts["node and edge dicts copied apart"] = r.nodes[1]["tag"] is not data(r, 1, 0)["sh"]
    r.graph["g"].append(1)
    r.nodes[0]["tag"].append(1)
    if not store_only:
        data(r, 1, 0)["w"].append(1)
    facts["original untouched"] = (
        g.graph["g"] == [9]
        and g.nodes[0]["tag"] == [0]
        and (store_only or data(g, 0, 1)["w"] == [1])
    )
    return facts


@pytest.mark.parametrize("store_only", [False, True])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_reverse_copy_deep_copies_attribute_values_as_networkx(cls, store_only):
    assert _identity_facts(fnx, cls, store_only) == _identity_facts(nx, cls, store_only)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_a_reverse_views_concrete_graph_shares_the_views_values(cls):
    # Only the public reverse(copy=True) deep-copies: the concrete graph a
    # reverse view reaches a kernel as (br-r37-c1-8xp4a) is the raw reverse,
    # holding the values the view itself shows.
    from franken_networkx import _materialize_view

    payload = [1]
    g = getattr(fnx, cls)()
    g.add_node(0, tag=payload)
    g.add_edge(0, 1, obj=payload)
    view = g.reverse(copy=False)
    concrete = _materialize_view(view)
    multi = g.is_multigraph()
    assert (view[1][0][0] if multi else view[1][0])["obj"] is payload
    assert (concrete[1][0][0] if multi else concrete[1][0])["obj"] is payload
    assert concrete.nodes[0]["tag"] is payload
