"""br-r37-c1-vbe1o: has_edge / get_edge_data must ask the ADJACENCY.

networkx is ``v in self._adj[u]`` with the KeyError caught, so the adjacency is
the sole authority on whether ``u`` exists. fnx's private-storage shadow probed
``u not in self`` -- the node view -- and returned False for a node carried only
by an assigned ``_adj``. A SILENT wrong boolean: no exception, just the wrong
answer. ``get_edge_data`` inherited it through its ``self.has_edge(...)``
delegation, answering ``None`` where networkx answers ``{}``.

These functions are instance shadows installed only on graphs carrying private
storage, so ordinary graphs never execute them.

THE TRAP THIS FILE ALSO GUARDS: there are two families of wrapper here, and one
is dead. ``_private_aware_has_edge_simple`` is defined and never referenced; the
live path is the ``_assigned_private_has_edge_*`` instance shadow. The first
attempt at this fix edited the dead one and changed nothing.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}

CASES = [
    ("Graph", "_adj", ADJ),
    ("MultiGraph", "_adj", ADJ),
    ("DiGraph", "_adj", ADJ),
    ("DiGraph", "_succ", SUCC),
    ("MultiDiGraph", "_adj", ADJ),
    ("MultiDiGraph", "_succ", SUCC),
]


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


@pytest.mark.parametrize("cls,attr,mapping", CASES)
def test_has_edge_sees_an_edge_only_in_assigned_storage(cls, attr, mapping):
    expected = build(nx, cls, attr, mapping).has_edge("ZZ", "b")
    got = build(fnx, cls, attr, mapping).has_edge("ZZ", "b")
    assert expected is True, "nx contract moved; update this file"
    assert got == expected


@pytest.mark.parametrize("cls,attr,mapping", CASES)
def test_get_edge_data_sees_an_edge_only_in_assigned_storage(cls, attr, mapping):
    expected = build(nx, cls, attr, mapping).get_edge_data("ZZ", "b")
    got = build(fnx, cls, attr, mapping).get_edge_data("ZZ", "b")
    assert expected is not None, "nx contract moved; update this file"
    assert got == expected


@pytest.mark.parametrize("cls,attr,mapping", CASES)
def test_absent_edges_are_still_absent(cls, attr, mapping):
    """The fix must not turn has_edge into a rubber stamp."""
    for u, v in (("ZZ", "nope"), ("nope", "b"), ("nope", "nope"), ("a", "ZZ")):
        expected = build(nx, cls, attr, mapping).has_edge(u, v)
        got = build(fnx, cls, attr, mapping).has_edge(u, v)
        assert got == expected, f"has_edge({u!r}, {v!r})"
        exp_d = build(nx, cls, attr, mapping).get_edge_data(u, v)
        got_d = build(fnx, cls, attr, mapping).get_edge_data(u, v)
        assert got_d == exp_d


@pytest.mark.parametrize("cls,attr,mapping", CASES)
def test_unhashable_endpoints_still_raise(cls, attr, mapping):
    """The hash checks above the fix must survive it."""
    g = build(fnx, cls, attr, mapping)
    n = build(nx, cls, attr, mapping)
    for u, v in ((["x"], "b"), ("a", ["x"])):
        with pytest.raises(TypeError):
            n.has_edge(u, v)
        with pytest.raises(TypeError):
            g.has_edge(u, v)


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"])
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, so the shadow is never installed."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_node("iso")
    for u, v in (("a", "b"), ("b", "a"), ("a", "iso"), ("nope", "b"), ("a", "nope")):
        assert gfx.has_edge(u, v) == gnx.has_edge(u, v)
        assert gfx.get_edge_data(u, v) == gnx.get_edge_data(u, v)
