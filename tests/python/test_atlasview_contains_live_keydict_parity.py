"""Row membership ``v in G.adj[u]`` stays live and matches networkx.

br-r37-c1-i44vx inlined a live-keydict fast path into the Python
``AtlasView.__contains__`` — a row cache held with no revision token, so if it
ever stopped tracking the graph, membership would answer from a stale row.
Every assertion below is differential against live networkx across a mutation
sequence, which is what locks that liveness.

The Python branch itself is gone: the only exact class whose row was the Python
``AtlasView`` was DiGraph, and its rows moved to the native ``AtlasView``, whose
own persistent row mirror is the same Rust-maintained dict. The differential
tests keep covering all four classes, and the scope test below fails if a
routing change ever brings an exact class back onto the Python row.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    for i in range(12):
        graph.add_edge(f"n{i}", f"n{(i * 5 + 1) % 12}")
    graph.add_node("iso")
    return graph


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_matches_networkx_on_a_fresh_row(cls_name):
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for u in list(gnx.nodes()):
        for v in list(gnx.nodes()) + ["absent", "iso"]:
            assert (v in gfx.adj[u]) == (v in gnx.adj[u]), (u, v)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_held_row_still_tracks_edge_mutation(cls_name):
    """The liveness contract the untokened cache could break.

    The row is captured ONCE and then read after each mutation, which is the
    only shape that can expose a stale keydict — re-fetching ``G.adj[u]`` every
    time would hide it.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    row_nx, row_fx = gnx.adj["n0"], gfx.adj["n0"]

    def agree(label):
        for v in ("n1", "n5", "n6", "n7", "fresh", "iso"):
            assert (v in row_fx) == (v in row_nx), (cls_name, label, v)

    agree("initial")
    for graph in (gnx, gfx):
        graph.add_edge("n0", "fresh")
    agree("after add_edge")
    for graph in (gnx, gfx):
        graph.remove_edge("n0", "fresh")
    agree("after remove_edge")
    for graph in (gnx, gfx):
        graph.add_edge("n0", "n7")
    agree("after add_edge to existing node")
    for graph in (gnx, gfx):
        graph.add_node("later")
    agree("after add_node")


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_and_iteration_agree_on_the_same_row(cls_name):
    """__contains__ and __iter__ now take different routes; keep them honest.

    __iter__ still goes through _keydict(). If the inlined branch ever served a
    different object, these two would drift apart on the same row object.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for u in list(gnx.nodes()):
        row_fx, row_nx = gfx.adj[u], gnx.adj[u]
        assert set(row_fx) == set(row_nx), u
        for v in row_nx:
            assert v in row_fx, (u, v)
        for v in row_fx:
            assert v in row_nx, (u, v)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unhashable_key_still_raises_typeerror(cls_name):
    """br-r37-c1-i9whv / hcn5w: the fast path must not skip the hash contract.

    A dict membership test hashes its argument, so ``node in live`` raises
    TypeError of its own accord — but that is a property of the route, and the
    route changed, so it is asserted rather than assumed.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for graph in (gnx, gfx):
        with pytest.raises(TypeError):
            ["not", "hashable"] in graph.adj["n0"]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_answer_does_not_depend_on_whether_the_row_was_read_first(cls_name):
    """An answer that varies with cache state is the br-r37-c1-alll4 pattern.

    The inlined branch is only taken once the live keydict exists, so a cold row
    and a warm row take DIFFERENT routes to the same question. They must agree.
    """
    for warm in (False, True):
        gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
        row_nx, row_fx = gnx.adj["n0"], gfx.adj["n0"]
        if warm:
            list(row_fx)
            list(row_nx)
        for v in ("n1", "n5", "absent"):
            assert (v in row_fx) == (v in row_nx), (cls_name, warm, v)


class _DiGraphSubclass(fnx.DiGraph):
    pass


def test_no_exact_class_reaches_the_python_row():
    """Pins the scope claim so it cannot rot silently.

    If routing changes and a class lands on the Python AtlasView, this fails
    and whoever changed it learns the fast path now applies more widely —
    which is a fine outcome, but it should be a decision, not a surprise.

    The last exact class on it was DiGraph, whose rows moved to the native
    AtlasView. A SUBCLASS of DiGraph still gets the Python row (the native
    routes are exact-type), which the second half pins.
    """
    on_python_class = []
    for cls_name in CLASSES:
        graph = _build(fnx, cls_name)
        if type(graph.adj["n0"]) is fnx.AtlasView:
            on_python_class.append(cls_name)
    assert on_python_class == [], (
        "the set of classes whose adjacency row is the Python AtlasView "
        f"changed: {on_python_class}"
    )
    subclass_graph = _DiGraphSubclass()
    subclass_graph.add_edge("n0", "n1")
    assert type(subclass_graph.adj["n0"]) is fnx.AtlasView


def test_a_digraph_subclass_row_matches_networkx_and_stays_live():
    """The Python row that subclasses still get, against networkx."""

    class NxSubclass(nx.DiGraph):
        pass

    gnx, gfx = NxSubclass(), _DiGraphSubclass()
    for graph in (gnx, gfx):
        for i in range(12):
            graph.add_edge(f"n{i}", f"n{(i * 5 + 1) % 12}")
    row_nx, row_fx = gnx.adj["n0"], gfx.adj["n0"]
    for step in (lambda g: g.add_edge("n0", "n7"), lambda g: g.remove_edge("n0", "n1")):
        for v in ("n1", "n7", "absent"):
            assert (v in row_fx) == (v in row_nx), v
        step(gnx)
        step(gfx)
    for v in ("n1", "n7", "absent"):
        assert (v in row_fx) == (v in row_nx), v
    assert list(row_fx) == list(row_nx)
