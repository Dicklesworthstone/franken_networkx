"""br-r37-c1-vbe1o: nbunch_iter must read the ADJACENCY, as networkx does.

networkx's `nbunch_iter` uses `self._adj` twice — it iterates it when
``nbunch is None`` and filters a sequence against it — while testing a SINGLE
node against `self` (the node view). fnx used the node view for all three.

On an ordinary graph the node set and the adjacency are the same set, which is
why this went unnoticed and why the cheap container `br-r37-c1-oaamq` chose is
still correct there. Under assigned private storage they differ, and fnx was
wrong in BOTH directions: a node carried only by an assigned ``_adj`` was
filtered out, and one carried only by an assigned ``_node`` was let through.

That mattered beyond nbunch_iter itself — it feeds subgraph, degree(nbunch) and
much of the algorithm surface.

The single-node branch is deliberately NOT changed: nx really does test the node
view there, and a test below pins that asymmetry so a future "cleanup" does not
collapse the two rules.
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
        return ("ok", sorted(map(str, call())))
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__,)


@pytest.mark.parametrize("cls", ALL)
@pytest.mark.parametrize("attr,mapping", [("_adj", ADJ), ("_node", NODE)])
def test_nbunch_iter_none_matches_networkx(cls, attr, mapping):
    """The None branch iterates the ADJACENCY in nx, not the node view."""
    expected = out(lambda: list(build(nx, cls, attr, mapping).nbunch_iter()))
    got = out(lambda: list(build(fnx, cls, attr, mapping).nbunch_iter()))
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
@pytest.mark.parametrize("attr,mapping", [("_adj", ADJ), ("_node", NODE)])
def test_nbunch_iter_sequence_filters_on_the_adjacency(cls, attr, mapping):
    expected = out(lambda: list(build(nx, cls, attr, mapping).nbunch_iter(["a", "ZZ"])))
    got = out(lambda: list(build(fnx, cls, attr, mapping).nbunch_iter(["a", "ZZ"])))
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
def test_the_single_node_branch_still_uses_the_NODE_view(cls):
    """nx's asymmetry, pinned deliberately.

    With ``_node`` assigned, 'ZZ' is a node but has no adjacency row. nx's
    single-node branch tests ``nbunch in self`` and yields it; its SEQUENCE
    branch filters on ``_adj`` and drops it. The two rules genuinely differ and a
    future simplification that unifies them would be a regression.
    """
    single = out(lambda: list(build(nx, cls, "_node", NODE).nbunch_iter("ZZ")))
    seq = out(lambda: list(build(nx, cls, "_node", NODE).nbunch_iter(["ZZ"])))
    assert single != seq, "nx contract moved; this test no longer pins anything"

    got_single = out(lambda: list(build(fnx, cls, "_node", NODE).nbunch_iter("ZZ")))
    got_seq = out(lambda: list(build(fnx, cls, "_node", NODE).nbunch_iter(["ZZ"])))
    assert got_single == single
    assert got_seq == seq


@pytest.mark.parametrize("cls", ALL)
def test_unhashable_elements_still_raise(cls):
    """The chosen container must keep raising, not answer False.

    br-r37-c1-oaamq picked `self.nodes` partly because it raises TypeError on an
    unhashable element the way nx's plain-dict membership does, which let an
    explicit per-node hash() go. The private-storage container must not lose
    that.
    """
    for assignment in ((None, None), ("_adj", ADJ)):
        attr, mapping = assignment
        gnx = getattr(nx, cls)()
        gnx.add_edge("a", "b")
        gfx = getattr(fnx, cls)()
        gfx.add_edge("a", "b")
        if attr:
            setattr(gnx, attr, dict(mapping))
            setattr(gfx, attr, dict(mapping))
        want = out(lambda: list(gnx.nbunch_iter([["unhashable"]])))
        got = out(lambda: list(gfx.nbunch_iter([["unhashable"]])))
        assert got == want


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, so the private container is never taken."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_node("iso")
    assert sorted(map(str, gfx.nbunch_iter())) == sorted(map(str, gnx.nbunch_iter()))
    assert sorted(map(str, gfx.nbunch_iter(["a", "nope"]))) == sorted(
        map(str, gnx.nbunch_iter(["a", "nope"]))
    )
    assert sorted(map(str, gfx.nbunch_iter("a"))) == sorted(map(str, gnx.nbunch_iter("a")))


@pytest.mark.parametrize("cls", ALL)
def test_the_generator_stays_lazy(cls):
    """br-r37-c1-oaamq: nx returns a lazy generator over the LIVE graph."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
    inx, ifx = gnx.nbunch_iter(["a", "b", "later"]), gfx.nbunch_iter(["a", "b", "later"])
    for g in (gnx, gfx):
        g.add_node("later")
    assert sorted(map(str, ifx)) == sorted(map(str, inx))
