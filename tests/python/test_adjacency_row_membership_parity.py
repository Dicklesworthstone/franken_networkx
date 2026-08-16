"""Parity lock for br-r37-c1-hcn5w — membership on an adjacency row.

``AdjacencyView`` defined no ``__contains__``, so ``v in G.adj[u]`` fell through
to the ``Mapping`` ABC, whose implementation is ``try: self[key]``. A membership
test therefore built the whole inner keydict view and discarded it — worse than
the ``len()`` sitting next to it on the same object.

A real ``__contains__`` answers from the row instead. What needs pinning is the
CONTRACT it has to carry, because delegating alone got it wrong:

* an UNHASHABLE key is networkx's TypeError, not False. The native atlas's own
  ``__contains__`` answers False, so ``return node in self._atlas()`` REGRESSED
  the multigraphs — they had been raising only as a side effect of the ABC
  calling ``__getitem__``, which hashed on the way to building the value. An
  explicit ``hash()`` restores br-r37-c1-i9whv's contract;
* present, missing, and exotic-but-hashable keys must answer exactly as
  networkx does, on every class and on both ``G.adj[u]`` and ``G[u]``.

KNOWN RESIDUE, filed as br-r37-c1-espyz and excluded by name below: a simple
Graph's row is a NATIVE AtlasView rather than this Python class, so it never
reaches the guard and still answers False for an unhashable key. That is the
last class diverging on this contract and needs a Rust-side fix.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
# Graph's row is the native AtlasView — see br-r37-c1-espyz.
UNHASHABLE_FIXED = ["DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("a", "c")
    graph.add_edge("c", "d")
    graph.add_edge("a", "a")  # self-loop
    graph.add_node("iso")
    return graph


ROWS = {
    "G.adj[u]": lambda g, u: g.adj[u],
    "G[u]": lambda g, u: g[u],
}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("row_name", list(ROWS))
@pytest.mark.parametrize(
    "key", ["b", "c", "a", "zz", 99, (1, 2), frozenset({1})], ids=str
)
def test_membership_matches_networkx(cls_name, row_name, key):
    """Present, missing, self-loop and exotic-but-hashable keys."""
    row = ROWS[row_name]
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    assert (key in row(gfx, "a")) == (key in row(gnx, "a"))


@pytest.mark.parametrize("cls_name", UNHASHABLE_FIXED)
@pytest.mark.parametrize("row_name", list(ROWS))
@pytest.mark.parametrize("bad", [["u"], {"u": 1}, {1, 2}], ids=["list", "dict", "set"])
def test_unhashable_key_raises_typeerror(cls_name, row_name, bad):
    """The guard, on both row spellings. Graph is excluded: br-r37-c1-espyz."""
    row = ROWS[row_name]
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        with pytest.raises(TypeError):
            bad in row(graph, "a")


@pytest.mark.parametrize("row_name", list(ROWS))
def test_simple_graph_unhashable_is_the_known_residue(row_name):
    """Pins the OPEN divergence so it cannot go quiet.

    Deliberately an assertion about a bug: when br-r37-c1-espyz is fixed this
    fails and says to fold Graph back into the test above.
    """
    row = ROWS[row_name]
    graph = _build(fnx, "Graph")
    assert (["u"] in row(graph, "a")) is False
    reference = _build(nx, "Graph")
    with pytest.raises(TypeError):
        ["u"] in row(reference, "a")


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_agrees_with_iteration_and_len(cls_name):
    """`in` must not drift from the row's own contents."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for row_name, row in ROWS.items():
        rnx, rfx = row(gnx, "a"), row(gfx, "a")
        assert sorted(map(str, rfx)) == sorted(map(str, rnx)), row_name
        assert len(rfx) == len(rnx), row_name
        for nbr in rnx:
            assert nbr in rfx, (row_name, nbr)
        assert ("zz" in rfx) == ("zz" in rnx), row_name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_is_live_across_mutation(cls_name):
    """The row is captured (br-r37-c1-znpkv); membership must still be live."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    for graph in (gnx, gfx):
        graph.add_edge("a", "zz")
        graph.remove_edge("a", "b")
    assert ("zz" in rfx) == ("zz" in rnx) is True
    assert ("b" in rfx) == ("b" in rnx) is False
    assert len(rfx) == len(rnx)
