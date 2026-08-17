"""br-r37-c1-wv3cu: the batch add methods write INTO the assigned mapping.

networkx defines add_edges_from and add_weighted_edges_from in terms of add_edge,
so fixing add_edge fixed them there for free. fnx's are native kernels that never
reach the corrected path — the same asymmetry add_nodes_from showed. Each batch
method therefore needs its own shadow, and "the singular is fixed so the plural
is too" is exactly the assumption that would have left these broken.

The fixture shares the inner row object between both directions of an undirected
edge, because that is networkx's own invariant (``_adj[u][v] is _adj[v][u]``).
Building them separately produces a mapping no real networkx graph holds and
manufactures a divergence that is the fixture's, not the code's.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]


def pair(cls):
    out = []
    multi = cls.startswith("Multi")
    for mod in (nx, fnx):
        g = getattr(mod, cls)()
        g.add_edge("a", "b")
        shared = {0: {}} if multi else {}
        m = {"a": {"b": shared}, "b": {"a": shared}}
        g._adj = m
        out.append((g, m))
    return out


def state(g):
    return (
        sorted(map(str, g.nodes)),
        sorted(str(tuple(map(str, e[:2]))) for e in g.edges),
        sorted(map(str, g.adj)),
    )


@pytest.mark.parametrize("cls", ALL)
def test_add_edges_from_reaches_the_callers_object(cls):
    (gnx, mnx), (gfx, mfx) = pair(cls)
    for g in (gnx, gfx):
        g.add_edges_from([("p", "q"), ("q", "r")])
    assert sorted(map(str, mfx)) == sorted(map(str, mnx))
    assert state(gfx) == state(gnx)


@pytest.mark.parametrize("cls", ALL)
def test_add_edges_from_with_data_dicts(cls):
    (gnx, _), (gfx, _) = pair(cls)
    for g in (gnx, gfx):
        g.add_edges_from([("p", "q", {"w": 1})], tag="t")
    assert state(gfx) == state(gnx)
    assert gfx.get_edge_data("p", "q") == gnx.get_edge_data("p", "q")


@pytest.mark.parametrize("cls", ALL)
def test_add_weighted_edges_from(cls):
    (gnx, mnx), (gfx, mfx) = pair(cls)
    for g in (gnx, gfx):
        g.add_weighted_edges_from([("x", "y", 3), ("y", "z", 4.5)])
    assert sorted(map(str, mfx)) == sorted(map(str, mnx))
    assert state(gfx) == state(gnx)
    assert gfx.get_edge_data("x", "y") == gnx.get_edge_data("x", "y")


@pytest.mark.parametrize("cls", ALL)
def test_a_custom_weight_key_is_honoured(cls):
    (gnx, _), (gfx, _) = pair(cls)
    for g in (gnx, gfx):
        g.add_weighted_edges_from([("x", "y", 2)], weight="cost")
    assert gfx.get_edge_data("x", "y") == gnx.get_edge_data("x", "y")


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_key_arity_forms(cls):
    """The 3-tuple is ambiguous on a multigraph: a KEY if it is not a mapping."""
    (gnx, _), (gfx, _) = pair(cls)
    for g in (gnx, gfx):
        g.add_edges_from([("p", "q", "mykey"), ("r", "s", {"w": 1})])
    assert state(gfx) == state(gnx)
    assert sorted(map(str, gfx.edges(keys=True))) == sorted(map(str, gnx.edges(keys=True)))


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, so no shadow is installed."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edges_from([("a", "b", {"w": 1}), ("b", "c")])
        g.add_weighted_edges_from([("c", "d", 7)])
    assert state(gfx) == state(gnx)
    assert gfx.get_edge_data("c", "d") == gnx.get_edge_data("c", "d")
    assert not {"add_edges_from", "add_weighted_edges_from"} & set(vars(gfx))
