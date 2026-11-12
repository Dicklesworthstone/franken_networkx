"""br-r37-c1-2r06n: G[node] on the multigraph classes must read assigned storage.

`_graph_getitem_from_adj` (Graph, DiGraph) reads the private-aware
``self.adj[node]``, so it already honoured an assigned ``_adj``. The multigraph
paths read a NATIVE adjacency row instead, which cannot see assigned storage, so
``G['ZZ']`` raised KeyError for a node carried only by an assigned mapping while
networkx returns its row.

This was the layer under the conversion-view defect: fixing the view's membership
made ``'ZZ' in view.succ`` true, and the subscript one level down still refused
it. Both are fixed now, and the conversion-view MultiGraph cases pass as a
consequence rather than by separate work.

TWO PROPERTIES THE FIX DEPENDS ON, both tested here:

  * the private check sits AFTER the row cache probe, so a warm repeat lookup
    pays nothing for it — which is only sound because installing private storage
    DROPS that cache, forcing a miss (``test_a_row_cached_before_the_assignment``);
  * the private result is deliberately not cached, because the assigned mapping
    is an ordinary dict a caller may mutate and the cache is keyed on
    ``nodes_seq``, which such a mutation does not advance
    (``test_a_mutation_of_the_assigned_mapping_is_seen``).
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def keys(row):
    return sorted(map(str, row))


@pytest.mark.parametrize(
    "cls,attr,mapping",
    [
        ("Graph", "_adj", ADJ),
        ("MultiGraph", "_adj", ADJ),
        ("DiGraph", "_adj", ADJ),
        ("MultiDiGraph", "_adj", ADJ),
        ("DiGraph", "_succ", SUCC),
        ("MultiDiGraph", "_succ", SUCC),
    ],
)
def test_getitem_reads_a_node_only_in_assigned_storage(cls, attr, mapping):
    expected = keys(build(nx, cls, attr, mapping)["ZZ"])
    got = keys(build(fnx, cls, attr, mapping)["ZZ"])
    assert expected == ["b"], "nx contract moved; update this file"
    assert got == expected


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_getitem_still_refuses_a_node_in_neither_store(cls):
    """The fix must not turn the subscript into a rubber stamp."""
    gnx = build(nx, cls, "_adj", ADJ)
    gfx = build(fnx, cls, "_adj", ADJ)
    for g in (gnx, gfx):
        with pytest.raises(KeyError):
            g["nope"]


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_a_row_cached_before_the_assignment_is_not_served_after_it(cls):
    """The warm path skips the private check, so the assignment must force a miss."""
    gfx = getattr(fnx, cls)()
    gfx.add_edge("a", "b")
    gfx["a"]  # noqa: B018 - warm the row cache before any private storage exists
    gfx._adj = dict(ADJ)

    gnx = getattr(nx, cls)()
    gnx.add_edge("a", "b")
    gnx["a"]  # noqa: B018
    gnx._adj = dict(ADJ)

    assert keys(gfx["ZZ"]) == keys(gnx["ZZ"])
    assert keys(gfx["a"]) == keys(gnx["a"])


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_a_mutation_of_the_assigned_mapping_is_seen(cls):
    """The assigned dict is an ordinary dict; nodes_seq does not track it."""
    gfx = build(fnx, cls, "_adj", ADJ)
    gnx = build(nx, cls, "_adj", ADJ)
    for g in (gfx, gnx):
        g._adj["QQ"] = {"b": {}}
    assert keys(gfx["QQ"]) == keys(gnx["QQ"])


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"])
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: without any assignment the subscript is untouched."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_node("iso")
    for n in ("a", "b", "c", "iso"):
        assert keys(gfx[n]) == keys(gnx[n])
        assert keys(gfx[n]) == keys(gfx[n]), "repeat lookup must agree with itself"
    with pytest.raises(KeyError):
        gfx["nope"]
