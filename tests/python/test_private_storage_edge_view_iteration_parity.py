"""br-r37-c1-vbe1o: iterating a multigraph edge view is not the same as calling it.

networkx's ``MultiEdgeView.__iter__`` yields KEYED ``(u, v, k)`` tuples, while
``G.edges(...)`` with the default ``keys=False`` yields ``(u, v)``. That
asymmetry is real and easy to miss — I checked it against an ORDINARY networkx
multigraph before treating the difference as a bug, because "iterating a view
gives what calling it gives" is the natural assumption and it is wrong here.

fnx's ordinary multigraph edge view already matched networkx. Only the
private-storage view diverged, because it implemented ``__iter__`` by delegating
to the CALL form.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

NODE = {"a": {}, "b": {}, "ZZ": {}}
MULTI = ["MultiGraph", "MultiDiGraph"]


def build(mod, cls, parallel=1, assign=True):
    g = getattr(mod, cls)()
    for _ in range(parallel):
        g.add_edge("a", "b")
    if assign:
        g._node = dict(NODE)
    return g


@pytest.mark.parametrize("cls", MULTI)
def test_iterating_the_view_yields_keyed_tuples(cls):
    want = list(build(nx, cls).edges)
    got = list(build(fnx, cls).edges)
    assert all(len(e) == 3 for e in want), "nx contract moved; update this file"
    assert got == want


@pytest.mark.parametrize("cls", MULTI)
def test_calling_the_view_still_yields_pairs(cls):
    """The other half of the asymmetry must NOT change."""
    want = list(build(nx, cls).edges())
    got = list(build(fnx, cls).edges())
    assert all(len(e) == 2 for e in want), "nx contract moved; update this file"
    assert got == want


@pytest.mark.parametrize("cls", MULTI)
def test_parallel_edges_are_counted_individually(cls):
    """len() must not collapse parallel edges, which the keys=False form does."""
    want = build(nx, cls, parallel=3)
    got = build(fnx, cls, parallel=3)
    assert len(got.edges) == len(want.edges) == 3
    assert list(got.edges) == list(want.edges)


@pytest.mark.parametrize("cls", MULTI)
def test_ordinary_multigraphs_were_already_right(cls):
    """Negative control: this view is only used under private storage."""
    want = build(nx, cls, parallel=2, assign=False)
    got = build(fnx, cls, parallel=2, assign=False)
    assert list(got.edges) == list(want.edges)
    assert len(got.edges) == len(want.edges)
    assert list(got.edges()) == list(want.edges())


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_simple_graphs_are_unaffected(cls):
    """Simple graphs have no keys; iterating and calling agree there."""
    want = build(nx, cls)
    got = build(fnx, cls)
    assert list(got.edges) == list(want.edges)
    assert list(got.edges()) == list(want.edges())
    assert len(got.edges) == len(want.edges)
