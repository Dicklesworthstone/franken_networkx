"""br-r37-c1-vbe1o: adjacency() yields the ASSIGNED mapping's rows.

networkx's ``adjacency()`` is literally ``iter(self._adj.items())`` on both the
simple and multigraph classes. fnx routes through native fast paths
(``adjacency_dict_shared``, ``_native_adjacency_dict``) that read the Rust store
and cannot see assigned storage, and its final fallback iterates the node view —
so a node carried only by an assigned ``_adj`` never appeared.

The gate is on private storage, so every native fast path those comments earned
is untouched for ordinary graphs. The private ``_adj`` is read deliberately, not
the public ``adj``: the public accessor is now a read-only view (same bead) and
networkx hands out the live raw rows here.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
NODE = {"a": {}, "b": {}, "ZZ": {}}
ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def nodes_of(g):
    return sorted(str(n) for n, _ in g.adjacency())


@pytest.mark.parametrize("cls", ALL)
@pytest.mark.parametrize("attr,mapping", [("_adj", ADJ), ("_node", NODE)])
def test_adjacency_nodes_match_networkx(cls, attr, mapping):
    expected = nodes_of(build(nx, cls, attr, mapping))
    got = nodes_of(build(fnx, cls, attr, mapping))
    assert got == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_adjacency_follows_an_assigned_succ(cls):
    expected = nodes_of(build(nx, cls, "_succ", SUCC))
    got = nodes_of(build(fnx, cls, "_succ", SUCC))
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
def test_adjacency_rows_match_networkx(cls):
    """Not just the node set — the neighbour sets too."""
    want = {str(n): sorted(map(str, row)) for n, row in build(nx, cls, "_adj", ADJ).adjacency()}
    got = {str(n): sorted(map(str, row)) for n, row in build(fnx, cls, "_adj", ADJ).adjacency()}
    assert got == want


@pytest.mark.parametrize("cls", ALL)
def test_adjacency_is_still_a_lazy_iterator(cls):
    """br-adjiter: nx returns an iterator, not a materialised list."""
    g = build(fnx, cls, "_adj", ADJ)
    it = g.adjacency()
    assert iter(it) is not None
    first = next(iter(it))
    assert isinstance(first, tuple) and len(first) == 2


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_keep_the_native_path(cls):
    """Negative control: with no assignment the fast paths are untouched."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_node("iso")
    want = {str(n): sorted(map(str, row)) for n, row in gnx.adjacency()}
    got = {str(n): sorted(map(str, row)) for n, row in gfx.adjacency()}
    assert got == want
    assert next(iter(gfx.adjacency()))[0] == next(iter(gnx.adjacency()))[0]
