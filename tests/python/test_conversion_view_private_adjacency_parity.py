"""br-r37-c1-2r06n: a directed conversion view must read the wrapped graph's ADJACENCY.

`nx.Graph.to_directed(as_view=True)` builds a view whose `_succ` IS the source
graph's `_adj`, so a node carried only by an assigned `_adj` is present in the
view's succ/pred. fnx asked the wrapped graph's NODE view instead, at two layers
at once:

  * `_ConversionAdjacencyView.__getitem__` gated on `node not in self._view._graph`,
    and since `_Mapping.__contains__` routes through the subscript, that also made
    `u in view.succ` answer False;
  * `has_successor` / `has_predecessor` asked `u in self._graph`.

Fixing only the second was a measured NO-OP -- recorded on the bead at the time --
because the first still refused the node. Both layers are needed, which is the
point worth keeping: a wrong-authority bug can sit at more than one level of the
same lookup.

The MultiGraph half of this is NOT fixed here and is deliberately not asserted:
`MultiGraph.__getitem__` reads a native adjacency row that cannot see an assigned
`_adj`, so the conversion view over it still fails one layer further down. That is
tracked separately.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}


def build(mod, cls, adj=None):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    if adj is not None:
        g._adj = dict(adj)
    return g.to_directed(as_view=True)


def test_conversion_view_succ_contains_a_node_only_in_assigned_adj():
    expected = "ZZ" in build(nx, "Graph", ADJ).succ
    got = "ZZ" in build(fnx, "Graph", ADJ).succ
    assert expected is True, "nx contract moved; update this file"
    assert got == expected


def test_conversion_view_has_successor_for_a_node_only_in_assigned_adj():
    expected = build(nx, "Graph", ADJ).has_successor("ZZ", "b")
    got = build(fnx, "Graph", ADJ).has_successor("ZZ", "b")
    assert expected is True, "nx contract moved; update this file"
    assert got == expected


def test_conversion_view_has_predecessor_for_a_node_only_in_assigned_adj():
    expected = build(nx, "Graph", ADJ).has_predecessor("ZZ", "b")
    got = build(fnx, "Graph", ADJ).has_predecessor("ZZ", "b")
    assert got == expected


def test_conversion_view_still_refuses_a_node_in_neither_store():
    """The fix must not turn the view into a rubber stamp."""
    for u, v in (("nope", "b"), ("ZZ", "nope")):
        expected = build(nx, "Graph", ADJ).has_successor(u, v)
        got = build(fnx, "Graph", ADJ).has_successor(u, v)
        assert expected is False
        assert got == expected


def test_conversion_view_subscript_matches_networkx():
    expected = dict(build(nx, "Graph", ADJ).succ["ZZ"])
    got = dict(build(fnx, "Graph", ADJ).succ["ZZ"])
    assert sorted(map(str, got)) == sorted(map(str, expected))


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"])
def test_ordinary_conversion_views_are_unchanged(cls):
    """Negative control: with no assignment nothing about the view moves."""
    vnx = build(nx, cls)
    vfx = build(fnx, cls)
    assert sorted(map(str, vfx.succ)) == sorted(map(str, vnx.succ))
    assert len(vfx.succ) == len(vnx.succ)
    for u, v in (("a", "b"), ("b", "a"), ("a", "nope"), ("nope", "a")):
        assert vfx.has_successor(u, v) == vnx.has_successor(u, v)
        assert vfx.has_predecessor(u, v) == vnx.has_predecessor(u, v)
    assert sorted(map(str, vfx.succ["a"])) == sorted(map(str, vnx.succ["a"]))
    for missing in ("nope",):
        try:
            vnx.succ[missing]
            nx_raised = False
        except KeyError:
            nx_raised = True
        try:
            vfx.succ[missing]
            fnx_raised = False
        except KeyError:
            fnx_raised = True
        assert fnx_raised == nx_raised
