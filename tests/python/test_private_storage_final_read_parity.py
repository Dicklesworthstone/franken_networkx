"""br-r37-c1-vbe1o: the last two read divergences — out_degree(nbunch) and copy().

Two unrelated causes, both the same shape as the rest of this bead: a path that
trusts the Rust store on a graph that does not.

``out_degree('ZZ')`` under an assigned ``_node``: the native subset kernel
returns no pair for a node it cannot see, so the call yielded an EMPTY view.
networkx builds a view over that node and then raises KeyError from the degree
lookup. Every other native path in that class already carried the private-storage
gate; this one was missed.

``copy()`` under an assigned ``_adj``: networkx's copy does NOT go through the
edge view — it iterates the raw mapping. That matters because the undirected edge
view emits each edge once via a seen-set, so a one-sided row like
``{'ZZ': {'b': {}}}`` is skipped and the node never reaches the copy. Both
libraries report the SAME ``nodes(data=True)`` and ``edges(data=True)`` here; only
``copy()`` diverged, which is why the views could not be used to find it.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
NODE = {"a": {}, "b": {}, "ZZ": {}}
ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def out(call):
    try:
        return ("ok", call())
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__,)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_out_degree_of_a_node_only_in_assigned_node_matches_networkx(cls):
    expected = out(lambda: dict(build(nx, cls, "_node", NODE).out_degree("ZZ")))
    got = out(lambda: dict(build(fnx, cls, "_node", NODE).out_degree("ZZ")))
    assert expected[0] == "KeyError", "nx contract moved; update this file"
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
def test_copy_carries_nodes_from_the_assigned_adjacency(cls):
    want = sorted(map(str, build(nx, cls, "_adj", ADJ).copy()))
    got = sorted(map(str, build(fnx, cls, "_adj", ADJ).copy()))
    assert got == want


def test_copy_diverged_where_the_views_agreed():
    """Pins WHY the views could not have found this.

    Both libraries report the same nodes(data=True) and edges(data=True) on this
    graph; only copy() differed, because copy reads the raw mapping while the
    undirected edge view de-duplicates.
    """
    gnx = build(nx, "Graph", "_adj", ADJ)
    gfx = build(fnx, "Graph", "_adj", ADJ)
    assert sorted(str(n) for n, _ in gfx.nodes(data=True)) == sorted(
        str(n) for n, _ in gnx.nodes(data=True)
    )
    assert sorted(str(e[:2]) for e in gfx.edges(data=True)) == sorted(
        str(e[:2]) for e in gnx.edges(data=True)
    )
    assert sorted(map(str, gfx.copy())) == sorted(map(str, gnx.copy()))
    assert "ZZ" in sorted(map(str, gnx.copy())), "the case is only interesting if nx carries ZZ"


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, so both paths are the ordinary ones."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b", w=1)
        g.add_edge("b", "c")
        g.add_node("iso")
    assert sorted(map(str, gfx.copy())) == sorted(map(str, gnx.copy()))
    assert sorted(str(e) for e in gfx.copy().edges(data=True)) == sorted(
        str(e) for e in gnx.copy().edges(data=True)
    )
    if cls in ("DiGraph", "MultiDiGraph"):
        for n in ("a", "b", "c", "iso"):
            assert gfx.out_degree(n) == gnx.out_degree(n)
        assert dict(gfx.out_degree(["a", "b"])) == dict(gnx.out_degree(["a", "b"]))
