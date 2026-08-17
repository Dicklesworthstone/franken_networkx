"""br-r37-c1-wv3cu: add_node writes INTO the assigned mapping, as networkx does.

The design question this bead was filed with — does the assigned dict receive
writes? — is settled by observation, not preference. networkx mutates the
caller's own object:

    assigned = {"a": {"b": {}}, "b": {"a": {}}}
    G._adj = assigned
    G.add_edge("p", "q")     ->  nx: assigned now holds a, b, p, q

Because the caller still holds a reference, no amount of read-side consistency
can hide it. So fnx must write there too.

fnx can have a SPLIT store — ``G._adj = {...}`` leaves ``_node`` native and not
writable as a dict — so the port is not verbatim: the native store gains the node
through the raw method, and each assigned mapping gains its own row.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}}
NODE = {"a": {}, "b": {}}
ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


@pytest.mark.parametrize("cls", ALL)
@pytest.mark.parametrize("attr,mapping", [("_adj", ADJ), ("_node", NODE)])
def test_add_node_is_visible_through_the_caller_s_own_object(cls, attr, mapping):
    """The sharpest form: the caller still holds the dict and must see the write."""
    want_map = dict(mapping)
    gnx = getattr(nx, cls)()
    gnx.add_edge("a", "b")
    setattr(gnx, attr, want_map)
    gnx.add_node("QQ")

    got_map = dict(mapping)
    gfx = getattr(fnx, cls)()
    gfx.add_edge("a", "b")
    setattr(gfx, attr, got_map)
    gfx.add_node("QQ")

    assert sorted(map(str, got_map)) == sorted(map(str, want_map))


@pytest.mark.parametrize("cls", ALL)
def test_add_node_state_matches_networkx(cls):
    want = build(nx, cls, "_adj", ADJ)
    got = build(fnx, cls, "_adj", ADJ)
    for g in (want, got):
        g.add_node("QQ")
    assert sorted(map(str, got.nodes)) == sorted(map(str, want.nodes))
    assert sorted(map(str, got.adj)) == sorted(map(str, want.adj))


@pytest.mark.parametrize("cls", ALL)
def test_attributes_follow_networkx_semantics(cls):
    """New node takes attr; existing node has attr MERGED, not replaced."""
    want = build(nx, cls, "_node", NODE)
    got = build(fnx, cls, "_node", NODE)
    for g in (want, got):
        g.add_node("QQ", color="red")
        g.add_node("QQ", size=2)
        g.add_node("a", tag=1)
    assert dict(got.nodes["QQ"]) == dict(want.nodes["QQ"])
    assert dict(got.nodes["a"]) == dict(want.nodes["a"])


@pytest.mark.parametrize("cls", ALL)
def test_none_is_still_rejected(cls):
    """The None-rejecting contract must survive the shadow."""
    g = build(fnx, cls, "_adj", ADJ)
    n = build(nx, cls, "_adj", ADJ)
    with pytest.raises(ValueError):
        n.add_node(None)
    with pytest.raises(ValueError):
        g.add_node(None)


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: the shadow is installed only under private storage."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_node("iso", w=1)
        g.add_node("iso", z=2)
    assert sorted(map(str, gfx.nodes)) == sorted(map(str, gnx.nodes))
    assert dict(gfx.nodes["iso"]) == dict(gnx.nodes["iso"])
    assert "add_node" not in vars(gfx)
