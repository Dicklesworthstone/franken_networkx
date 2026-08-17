"""``edges(nbunch, ...)`` resolves nbunch items through the warm index cache.

br-r37-c1-nbidx. This is the THIRD hypothesis about this surface and the first
one that measured anything. The two before it were reasoned out from the shape of
the code and both were wrong; this one came from profiling, which is what the
sibling file's docstring told the next attempt to do.

WHY THE FIRST TWO FAILED, because it is the reusable lesson. Both patched
``views.rs::edge_alldata_items``. A cProfile of ``list(G.edges(nbunch,
data=True))`` shows the call does not go there at all — it enters
``readwrite.rs::edges_nbunch_data``, plus ``edges_nbunch_count`` for the size
hint. Two carefully measured levers landed on code this path never executes,
which is why both read as "no effect": they were correct measurements of nothing.

WHAT THE PROFILE FOUND. Per NBUNCH ITEM the kernel called
``node_key_to_string``, building a ``str:{len}:{s}`` canonical — at 2000
characters an allocation and a 2000-byte copy each — and then hashed those bytes
to get the node index. ``cached_exact_string_node_index`` answers the same
question from CPython's own cached ``str`` hash, and already backed ``has_edge``.
Both kernels now use it. The count kernel matters twice over: ``list(view)``
calls ``__len__`` for the size hint BEFORE ``__iter__``, so the per-item cost was
being paid on every materialization.

MEASURED, 300 edges, nbunch=200, min of 7 rounds of 30:

    K=2000    0.2971x -> 0.4589x        K=3    1.2425x -> 1.6829x
    nbunch=600 at K=2000: 965.4us -> 532.8us   (1.6us -> 0.89us per item)

STILL NOT FIXED, and the sibling xfail stays strict because of it. The remaining
O(key length) work is PER EDGE: ``PyGraph::edge_key(u_name, v_name)`` builds an
owned key from BOTH 2000-character names to look up ``edge_py_attrs``. The
lookaside that would answer it from two ``usize``s already exists
(``cached_edge_py_attrs_by_index``), but populating it needs ``&mut self`` and
this kernel reaches the graph through ``extract_graph``, which yields a
``PyRef``. That is a different and larger change, not a line edit, so it is not
being smuggled in here.

WHAT THIS FILE PINS. The speedup is a CACHE, so the tests that matter are the
ones about it being wrong rather than the one about it being fast:

1. Odd nbunch items must behave exactly as before. The old code raised out of
   ``node_key_to_string``; the new code performs a hash-cache lookup first, so an
   unhashable item now meets a different piece of machinery first. Compared
   against networkx by EXCEPTION ARGS, not just type — a type-only comparison
   reports false green.
2. Node removal RENUMBERS node indices, so a stale cached index would silently
   name a DIFFERENT node. The cache is stamped with ``nodes_seq``; these tests
   fail if that stamp is ever dropped.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(lib, key_len: int = 1, edges: int = 6):
    graph = lib.Graph()
    for i in range(edges):
        graph.add_edge(f"a{i}".ljust(key_len, "x"), f"b{i}".ljust(key_len, "y"), weight=i)
    graph.add_edge(1, 2)
    graph.add_edge((3, 4), (5, 6))
    return graph


def _edges(graph, nbunch, **kw):
    """Normalized result, or the exception identity, so the two are comparable."""
    try:
        return (
            "ok",
            sorted(
                (repr(u), repr(v), tuple(sorted(d.items())))
                for u, v, d in graph.edges(nbunch, data=True, **kw)
            ),
        )
    except Exception as exc:  # noqa: BLE001 - comparing the raise itself
        return (type(exc).__name__, exc.args)


ODD_NBUNCHES = [
    ["a0"],
    [1],
    [(3, 4)],
    [["unhashable"]],
    [None],
    ["absent"],
    [1, "a0", (3, 4)],
    [b"bytes"],
    [1.5],
    [True],
    [],
    ["a0", "a0", "a0"],
]


@pytest.mark.parametrize("nbunch", ODD_NBUNCHES, ids=repr)
def test_odd_nbunch_items_match_networkx_including_the_raise(nbunch):
    """Requirement 1 — compared by exception ARGS, not merely by type."""
    assert _edges(_build(fnx), nbunch) == _edges(_build(nx), nbunch)


def test_warm_cache_survives_node_removal_renumbering():
    """Requirement 2 — the case a missing ``nodes_seq`` stamp would break.

    The first call warms an index for every nbunch item. Removing a node
    renumbers the remaining indices, so a cached index that outlived the removal
    would resolve to the WRONG node and quietly emit another node's edges.
    """
    got, want = _build(fnx), _build(nx)
    nbunch = [f"a{i}" for i in range(6)]

    assert _edges(got, nbunch) == _edges(want, nbunch)  # warm

    for victim in ("a0", "b3", 1):
        got.remove_node(victim)
        want.remove_node(victim)
        assert _edges(got, nbunch) == _edges(want, nbunch), (
            f"diverged after removing {victim!r} — a cached node index outlived "
            "the renumbering that removal performs"
        )


def test_warm_cache_survives_node_addition():
    """Additions also move ``nodes_seq``; a re-add must not resurrect an index."""
    got, want = _build(fnx), _build(nx)
    nbunch = ["a1", "b1", "a2"]
    assert _edges(got, nbunch) == _edges(want, nbunch)

    for graph in (got, want):
        graph.remove_node("a1")
        graph.add_edge("zzz", "b1", weight=99)
        graph.add_edge("a1", "b5", weight=7)

    assert _edges(got, nbunch) == _edges(want, nbunch)


def test_len_and_iteration_agree_after_the_shared_lever():
    """``__len__`` and ``__iter__`` use SEPARATE kernels; both were changed.

    ``list(view)`` calls ``__len__`` first for a size hint, so a divergence
    between the two would either truncate or over-allocate the result.
    """
    got, want = _build(fnx, key_len=64), _build(nx, key_len=64)
    for nbunch in ([], ["a0"], ["a0", "b0"], [f"a{i}" for i in range(6)], ["absent"]):
        view = got.edges(nbunch)
        assert len(view) == len(list(view))
        assert len(view) == len(want.edges(nbunch))
