"""br-r37-c1-c99d9 — `G.subgraph([set()])` raises instead of silently dropping it.

networkx resolves a subgraph's nbunch through `nbunch_iter`, which filters with
`n in self._adj` — a DICT — so an unhashable item raises there and the subgraph
is never built. fnx filters against a SET on its large-nbunch branch, and
CPython converts a `set` (and a set SUBCLASS) to a `frozenset` for `x in aset`:

    set() in {frozenset()}   ->  False, NO raise
    set() in {}              ->  TypeError

so the item was silently DROPPED and `G.subgraph([set()])` answered with an
empty subgraph on all four classes. Every other unhashable shape — list, dict,
bytearray — raises out of the same membership test and was already correct,
which is why only a SET exposes this and why the earlier unhashable sweeps
(which used a class with `__hash__ = None`) missed it.

TWO BRANCHES, BOTH COVERED. `_subgraph_filter_from_nbunch` picks between a
whole-graph `set(G)` (when the nbunch is large relative to the graph) and a
per-node walk against the graph itself. Only the first has the defect, and which
one runs depends on `len(nbunch) * 4 >= len(G)` — so every case below runs at
TWO graph sizes chosen to force each branch. A test at one size would have
passed against the unfixed code half the time.

NOT FIXED BY MAKING THE CONTAINER A DICT, which is the obvious move: measured,
`dict.fromkeys(G)` costs 1.72x `set(G)` to build and 1.09x to filter through —
35 percent on a branch that exists precisely because it is the fast one
(br-r37-c1-50w8n). The guard instead runs only when something was dropped, which
a set always is, and each step is a C type check rather than a call.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# `set(G)` is built when len(nbunch) * 4 >= len(G), so a 5-node graph takes the
# set branch for a 2-item nbunch and a 400-node graph takes the per-node walk.
ORDERS = [5, 400]


class _SetSubclass(set):
    """CPython converts a set SUBCLASS to a frozenset for `x in aset` too."""


def _pair(cls_name, order):
    graphs = []
    for lib in (nx, fnx):
        g = getattr(lib, cls_name)()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge((1, 2), "a")
        for i in range(order):
            g.add_node(f"x{i}")
        graphs.append(g)
    return graphs


def _outcome(fn):
    try:
        return ("ok", sorted(fn(), key=repr))
    except Exception as exc:  # noqa: BLE001
        return ("exc", type(exc).__name__, str(exc))


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize(
    "nbunch_of",
    [
        lambda: [set()],
        lambda: [{"x"}],
        lambda: [_SetSubclass()],
        lambda: ["a", set(), "b"],
        lambda: [set(), set()],
        lambda: ["a", "b", set()],
    ],
    ids=["empty-set", "nonempty-set", "set-subclass", "set-in-the-middle",
         "two-sets", "set-last"],
)
def test_a_set_in_the_nbunch_raises_like_networkx(cls_name, order, nbunch_of):
    """THE BUG. Answered `[]` on the unfixed code, on both branches."""
    gnx, gfx = _pair(cls_name, order)
    want = _outcome(lambda: gnx.subgraph(nbunch_of()).nodes())
    got = _outcome(lambda: gfx.subgraph(nbunch_of()).nodes())
    assert want[0] == "exc", "networkx oracle changed"
    assert got == want, (cls_name, order)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("order", ORDERS)
def test_the_other_unhashable_shapes_still_match(cls_name, order):
    """The shapes that were ALREADY right, so the fix cannot have moved them.

    A list, dict or bytearray raises out of the membership test itself, and the
    existing handler turns that into networkx's NetworkXError. Only the set
    slipped through, and only these carry the proof that the rest did not.
    """
    gnx, gfx = _pair(cls_name, order)
    for bad in ([], {}, bytearray()):
        want = _outcome(lambda: gnx.subgraph([bad]).nodes())
        got = _outcome(lambda: gfx.subgraph([bad]).nodes())
        assert want[0] == "exc", (cls_name, type(bad).__name__)
        assert got == want, (cls_name, order, type(bad).__name__)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("order", ORDERS)
def test_a_frozenset_is_a_perfectly_good_node_and_is_not_rejected(cls_name, order):
    """The control that says the guard tests HASHABILITY, not set-ness.

    A frozenset IS hashable and IS a valid networkx node. Rejecting it would be
    the same defect with the sign flipped, and a `isinstance(node, set)` guard
    that also caught frozensets would do exactly that — `frozenset` is not a
    subclass of `set`, which is what makes the spelling safe.
    """
    gnx, gfx = _pair(cls_name, order)
    for lib_graph in (gnx, gfx):
        lib_graph.add_edge(frozenset({7, 8}), "a")
    for nbunch in ([frozenset()], [frozenset({7, 8})], [frozenset({7, 8}), "a"]):
        want = _outcome(lambda: gnx.subgraph(nbunch).nodes())
        got = _outcome(lambda: gfx.subgraph(nbunch).nodes())
        assert want[0] == "ok", (cls_name, nbunch)
        assert got == want, (cls_name, order, nbunch)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("order", ORDERS)
def test_ordinary_nbunches_are_untouched(cls_name, order):
    """The other control: the guard runs only when something was DROPPED.

    Duplicates and absent nodes both shorten the result and therefore reach the
    walk; they must still produce networkx's answer rather than an error.
    """
    gnx, gfx = _pair(cls_name, order)
    for nbunch in (
        ["a", "b"],
        ["a", "a", "b"],
        ["a", "absent"],
        ["absent"],
        [],
        [(1, 2), "a"],
    ):
        want = _outcome(lambda: gnx.subgraph(nbunch).nodes())
        got = _outcome(lambda: gfx.subgraph(nbunch).nodes())
        assert want[0] == "ok", (cls_name, nbunch)
        assert got == want, (cls_name, order, nbunch)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_composed_forms_agree_too(cls_name):
    """`.copy()` and a nested subgraph go through the same resolver."""
    gnx, gfx = _pair(cls_name, 5)
    want = _outcome(lambda: gnx.subgraph(["a", set()]).copy().nodes())
    got = _outcome(lambda: gfx.subgraph(["a", set()]).copy().nodes())
    assert want[0] == "exc"
    assert got == want, cls_name

    want = _outcome(lambda: gnx.subgraph(["a", "b"]).subgraph(["a"]).nodes())
    got = _outcome(lambda: gfx.subgraph(["a", "b"]).subgraph(["a"]).nodes())
    assert got == want, cls_name
