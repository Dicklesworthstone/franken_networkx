"""`has_successor`/`has_predecessor` answer through the native edge path.

br-r37-c1-s8dj1. Both were Python shims that materialised an adjacency ROW to
answer a MEMBERSHIP question -- `succ = self.succ; return u in succ and v in
succ[u]` -- while `has_edge` next to them is the native method and now resolves
through the node-position lookaside. On a MultiDiGraph at E=400 that cost
464.0 ns against `has_edge`'s 123.3 ns for the same answer on the same graph.

networkx defines all three the same way: `has_edge(u, v)` and
`has_successor(u, v)` are both `u in self._succ and v in self._succ[u]`, and
`has_predecessor(u, v)` is the `_pred` twin -- so it is `has_edge(v, u)`, with
the ARGUMENTS REVERSED. That equivalence is the whole fix, so this file asserts
it against networkx itself rather than taking it on faith, including the
reversal, which is the easiest thing to get backwards and would be invisible on
any symmetric fixture.

THE ROW FORM IS STILL THERE AND MUST BE. br-r37-c1-ppiei established that under
assigned private storage the MAPPING decides whether `u` exists, not the node
view: an assigned `_succ` can carry a node the native store does not, and asking
the store returns False where networkx returns True -- a SILENT wrong answer.
So the native path is gated on exact base classes with no assigned storage, and
the tests below drive both sides of that gate.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED = ["DiGraph", "MultiDiGraph"]

# Deliberately asymmetric: a->b exists and b->a exists, but a->lone does not, so
# a reversed-argument bug cannot pass by coincidence.
PROBES = [
    ("a", "b"),
    ("b", "a"),
    ("a", "c"),
    ("c", "a"),
    ("a", "a"),
    ("c", "c"),
    ("lone", "a"),
    ("a", "lone"),
    ("absent", "a"),
    ("a", "absent"),
    ("absent", "alsoabsent"),
]


def _pair(cls_name):
    graphs = []
    for mod in (nx, fnx):
        graph = getattr(mod, cls_name)()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        graph.add_edge("c", "c")
        graph.add_edge("a", "c")
        graph.add_node("lone")
        graphs.append(graph)
    return graphs[0], graphs[1]


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("u,v", PROBES, ids=[f"{u}->{v}" for u, v in PROBES])
def test_matches_networkx(cls_name, u, v):
    ref, fx = _pair(cls_name)

    assert fx.has_successor(u, v) == ref.has_successor(u, v)
    assert fx.has_predecessor(u, v) == ref.has_predecessor(u, v)


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("u,v", PROBES, ids=[f"{u}->{v}" for u, v in PROBES])
def test_the_equivalence_the_fast_path_relies_on(cls_name, u, v):
    """`has_successor(u,v)` is `has_edge(u,v)`; `has_predecessor(u,v)` is
    `has_edge(v,u)` -- asserted on networkx AND on fnx, so the fast path cannot
    be right about fnx while being wrong about the contract it copied."""
    ref, fx = _pair(cls_name)

    for graph in (ref, fx):
        assert graph.has_successor(u, v) == graph.has_edge(u, v), (u, v)
        assert graph.has_predecessor(u, v) == graph.has_edge(v, u), (u, v)


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_a_reversed_argument_would_be_caught(cls_name):
    """The asymmetric pair, stated on its own so the guard is visible."""
    ref, fx = _pair(cls_name)
    for graph in (ref, fx):
        graph.add_edge("only", "forward")

    assert fx.has_successor("only", "forward") is True
    assert fx.has_successor("forward", "only") is False
    assert fx.has_predecessor("forward", "only") is True
    assert fx.has_predecessor("only", "forward") is False
    assert fx.has_successor("only", "forward") == ref.has_successor("only", "forward")
    assert fx.has_predecessor("forward", "only") == ref.has_predecessor("forward", "only")


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_assigned_private_storage_keeps_the_mapping_as_the_authority(cls_name):
    """THE case the row form exists for (br-r37-c1-ppiei).

    The assigned `_succ` carries `q`/`r`, which the native store has never seen.
    Asking the store answers False; networkx answers True. The gate must send
    this graph down the row form.
    """
    ref, fx = _pair(cls_name)
    cell = {0: {}} if "Multi" in cls_name else {}
    for graph in (ref, fx):
        graph._succ = {"q": {"r": cell}, "r": {}}
        graph._pred = {"r": {"q": cell}, "q": {}}
        graph._adj = graph._succ
        graph._node = {"q": {}, "r": {}}

    assert fx.has_successor("q", "r") == ref.has_successor("q", "r") is True
    assert fx.has_predecessor("r", "q") == ref.has_predecessor("r", "q") is True
    # and the edge the NATIVE store still holds is now invisible, as in networkx
    assert fx.has_successor("a", "b") == ref.has_successor("a", "b") is False


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_a_view_is_not_sent_down_the_native_path(cls_name):
    """A view's adjacency is filtered; its `succ` is the authority, not the base."""
    ref, fx = _pair(cls_name)
    sub_ref, sub_fx = ref.subgraph(["a", "b"]), fx.subgraph(["a", "b"])

    for u, v in PROBES:
        assert sub_fx.has_successor(u, v) == sub_ref.has_successor(u, v), (u, v)
        assert sub_fx.has_predecessor(u, v) == sub_ref.has_predecessor(u, v), (u, v)
    assert sub_fx.has_successor("a", "c") == sub_ref.has_successor("a", "c") is False


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_an_unhashable_endpoint_raises_typeerror_like_networkx(cls_name):
    ref, fx = _pair(cls_name)

    with pytest.raises(TypeError):
        fx.has_successor(["unhashable"], "b")
    with pytest.raises(TypeError):
        ref.has_successor(["unhashable"], "b")
    with pytest.raises(TypeError):
        fx.has_predecessor(["unhashable"], "b")
    with pytest.raises(TypeError):
        ref.has_predecessor(["unhashable"], "b")


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_long_and_mixed_type_keys_agree(cls_name):
    """The long-key row is what the lookaside underneath is for."""
    long_u, long_v = "z" * 2000 + "u", "z" * 2000 + "v"
    ref, fx = _pair(cls_name)
    for graph in (ref, fx):
        graph.add_edge(long_u, long_v)
        graph.add_edge(7, 9)
        graph.add_edge((1, 2), 3.5)

    for u, v in ((long_u, long_v), (long_v, long_u), (7, 9), (9, 7), ((1, 2), 3.5), (3.5, (1, 2))):
        assert fx.has_successor(u, v) == ref.has_successor(u, v), (u, v)
        assert fx.has_predecessor(u, v) == ref.has_predecessor(u, v), (u, v)


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_mutations_are_visible_through_the_fast_path(cls_name):
    """The lookaside underneath is maintained incrementally, so a stale hit here
    would report an edge that no longer exists."""
    ref, fx = _pair(cls_name)
    for _ in range(200):  # push past the lookaside warm-up
        fx.has_successor("a", "b")

    for graph in (ref, fx):
        graph.add_edge("new", "edge")
    assert fx.has_successor("new", "edge") == ref.has_successor("new", "edge") is True

    for graph in (ref, fx):
        graph.remove_edge("a", "b")
    assert fx.has_successor("a", "b") == ref.has_successor("a", "b") is False
    assert fx.has_predecessor("b", "a") == ref.has_predecessor("b", "a") is False

    for graph in (ref, fx):
        graph.remove_node("c")
    for u, v in PROBES:
        assert fx.has_successor(u, v) == ref.has_successor(u, v), (u, v)
        assert fx.has_predecessor(u, v) == ref.has_predecessor(u, v), (u, v)


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_parallel_edges_do_not_change_the_answer(cls_name):
    ref, fx = _pair(cls_name)
    for graph in (ref, fx):
        graph.add_edge("p", "q")
        graph.add_edge("p", "q")

    assert fx.has_successor("p", "q") == ref.has_successor("p", "q") is True
    for graph in (ref, fx):
        graph.remove_edge("p", "q")
    assert fx.has_successor("p", "q") == ref.has_successor("p", "q")
