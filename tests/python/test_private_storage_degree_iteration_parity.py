"""br-r37-c1-2r06n: degree-view ITERATION, and a view whose len disagreed with itself.

Two defects, found by probing what the earlier call/subscript fix did NOT reach.

1. The degree views iterated and measured the NODE VIEW. nx's DiDegreeView sets
   ``_nodes = self._succ`` -- for the in-degree view as much as the out-degree
   one -- so under an assigned ``_succ`` iteration dropped a node the mapping
   carries, and ``len()`` answered the wrong count in both directions: too high
   with ``_node`` assigned, too low with ``_succ`` assigned. The per-node values
   came from native bulk paths that cannot see assigned storage at all.

2. ``MultiAdjacencyView.__len__`` answered ``owner.number_of_nodes()``, which is
   SHADOWED on instances carrying private storage, while ``__iter__`` kept
   yielding the adjacency's own keys. That made ``len(view) != len(list(view))``
   on the same object -- for MultiGraph.adj and all three of MultiDiGraph's
   adj/succ/pred. The simple classes were already correct.

The self-consistency check is the sharper of the two: a mapping whose length
disagrees with its own iteration is broken regardless of what networkx does.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
PRED = {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}}
NODE = {"a": {}, "b": {}, "ZZ": {}}


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def outcome(call):
    try:
        return ("ok", call())
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__,)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("attr,mapping", [("_succ", SUCC), ("_pred", PRED), ("_node", NODE)])
def test_degree_view_iteration_matches_networkx(cls, attr, mapping):
    for view in ("out_degree", "in_degree"):
        expected = outcome(lambda: dict(getattr(build(nx, cls, attr, mapping), view)))
        got = outcome(lambda: dict(getattr(build(fnx, cls, attr, mapping), view)))
        assert got == expected, f"{cls}.{view} under assigned {attr}"


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("attr,mapping", [("_succ", SUCC), ("_pred", PRED), ("_node", NODE)])
def test_degree_view_len_matches_networkx(cls, attr, mapping):
    for view in ("out_degree", "in_degree"):
        expected = len(getattr(build(nx, cls, attr, mapping), view))
        got = len(getattr(build(fnx, cls, attr, mapping), view))
        assert got == expected, f"len({cls}.{view}) under assigned {attr}"


@pytest.mark.parametrize(
    "cls,attrs",
    [
        ("Graph", ("adj",)),
        ("DiGraph", ("adj", "succ", "pred")),
        ("MultiGraph", ("adj",)),
        ("MultiDiGraph", ("adj", "succ", "pred")),
    ],
)
def test_adjacency_view_len_agrees_with_its_own_iteration(cls, attrs):
    """A mapping whose len disagrees with its iteration is broken on its own terms."""
    for attr in attrs:
        g = getattr(fnx, cls)()
        g.add_edge("a", "b")
        g._node = dict(NODE)
        view = getattr(g, attr)
        assert len(view) == len(list(view)), f"{cls}.{attr}: len != len(list(...))"


@pytest.mark.parametrize(
    "cls,attrs",
    [
        ("Graph", ("adj",)),
        ("DiGraph", ("adj", "succ", "pred")),
        ("MultiGraph", ("adj",)),
        ("MultiDiGraph", ("adj", "succ", "pred")),
    ],
)
def test_adjacency_view_len_matches_networkx(cls, attrs):
    for attr in attrs:
        gnx = getattr(nx, cls)()
        gnx.add_edge("a", "b")
        gnx._node = dict(NODE)
        gfx = getattr(fnx, cls)()
        gfx.add_edge("a", "b")
        gfx._node = dict(NODE)
        assert len(getattr(gfx, attr)) == len(getattr(gnx, attr)), f"{cls}.{attr}"


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: without any assignment nothing about len or iteration moves."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_node("iso")
    assert len(gfx.adj) == len(gnx.adj)
    assert sorted(map(str, gfx.adj)) == sorted(map(str, gnx.adj))
    if cls in ("DiGraph", "MultiDiGraph"):
        assert dict(gfx.out_degree) == dict(gnx.out_degree)
        assert dict(gfx.in_degree) == dict(gnx.in_degree)
        assert len(gfx.out_degree) == len(gnx.out_degree)
        assert dict(gfx.out_degree(weight="weight")) == dict(gnx.out_degree(weight="weight"))
    else:
        assert dict(gfx.degree) == dict(gnx.degree)
