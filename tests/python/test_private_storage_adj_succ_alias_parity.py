"""br-r37-c1-vbe1o: on a directed graph, assigning `_adj` assigns the SUCCESSOR side.

In networkx both ``_adj`` and ``_succ`` on DiGraph/MultiDiGraph are bound to
``_CachedPropertyResetterAdjAndSucc``, whose ``__set__`` writes both names. So
they are one mapping: ``g._adj is g._succ`` is True before any assignment, and
assigning either makes a node visible through both.

fnx tracked them as two independent override keys. The read side was already
asymmetric in the right direction -- the adjacency reader consulted the succ
override, so ``_succ``-then-read-``_adj`` worked -- but the mirror was missing, so
``_adj``-then-read-``_succ`` did not. Everything that reads the successor side
then reported a node the assigned ``_adj`` plainly carried as absent.

That one gap accounted for 14 divergences in the sweep across successors,
has_successor, out_degree, len(G.succ), neighbors and G.succ.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
DIRECTED = ["DiGraph", "MultiDiGraph"]


def build(mod, cls, attr="_adj", mapping=ADJ):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def out(call):
    try:
        r = call()
        return ("ok", sorted(map(str, r)) if hasattr(r, "__iter__") and not isinstance(r, str) else r)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__,)


@pytest.mark.parametrize("cls", DIRECTED)
def test_assigning_adj_is_visible_through_succ(cls):
    assert ("ZZ" in build(nx, cls)._succ) is True, "nx contract moved"
    assert ("ZZ" in build(fnx, cls)._succ) == ("ZZ" in build(nx, cls)._succ)


@pytest.mark.parametrize("cls", DIRECTED)
@pytest.mark.parametrize(
    "label,call",
    [
        ("successors", lambda g: list(g.successors("ZZ"))),
        ("neighbors", lambda g: list(g.neighbors("ZZ"))),
        ("has_successor", lambda g: g.has_successor("ZZ", "b")),
        ("out_degree", lambda g: g.out_degree("ZZ")),
        ("len(succ)", lambda g: len(g.succ)),
        ("succ keys", lambda g: list(g.succ)),
    ],
)
def test_successor_side_reads_the_assigned_adj(cls, label, call):
    expected = out(lambda: call(build(nx, cls)))
    got = out(lambda: call(build(fnx, cls)))
    assert got == expected, label


@pytest.mark.parametrize("cls", DIRECTED)
def test_the_reverse_direction_still_works(cls):
    """`_succ`-then-read-`_adj` already worked and must keep working."""
    succ = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
    expected = "ZZ" in build(nx, cls, "_succ", succ)._adj
    got = "ZZ" in build(fnx, cls, "_succ", succ)._adj
    assert got == expected


@pytest.mark.parametrize("cls", DIRECTED)
def test_an_assigned_pred_does_not_leak_into_succ(cls):
    """Only `_adj`/`_succ` are aliases; `_pred` is a separate mapping."""
    pred = {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}}
    expected = "ZZ" in build(nx, cls, "_pred", pred)._succ
    got = "ZZ" in build(fnx, cls, "_pred", pred)._succ
    assert expected is False, "nx contract moved"
    assert got == expected


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph"])
def test_undirected_graphs_have_no_succ_alias(cls):
    """The alias is a directed-graph property; undirected classes have no succ."""
    g = build(fnx, cls)
    n = build(nx, cls)
    assert hasattr(g, "succ") == hasattr(n, "succ")
    assert ("ZZ" in g._adj) == ("ZZ" in n._adj)


@pytest.mark.parametrize("cls", DIRECTED)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: with no assignment nothing about the succ side moves."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_node("iso")
    assert sorted(map(str, gfx.succ)) == sorted(map(str, gnx.succ))
    assert len(gfx.succ) == len(gnx.succ)
    for n in ("a", "b", "c", "iso"):
        assert sorted(map(str, gfx.successors(n))) == sorted(map(str, gnx.successors(n)))
        assert gfx.out_degree(n) == gnx.out_degree(n)
