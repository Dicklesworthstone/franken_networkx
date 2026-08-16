"""Parity lock for br-r37-c1-aq6jv's three fast paths on ``G.edges(nbunch)``.

The bead is a PERFORMANCE one — small-nbunch ``G.edges(nbunch)`` was 0.356x
against networkx, all of it fixed per-call overhead — but every lever it
introduces is a shortcut around a correctness check, so each needs pinning:

1. A CALL-SHAPE short-circuit in ``EdgeView.__call__`` for the common
   ``G.edges([...])`` / ``G.edges([...], data=...)`` forms. It skips the
   general normalisation that decides between single-node, tuple-key,
   str/bytes and three-positional nbunch spellings. A ``list`` is unhashable
   and so can never be a node, which is what makes those questions answerable
   in advance — every other spelling must still take the long path, and the
   forms below cover them.

2. A pure-Python WALK over the cached adjacency rows for small nbunches,
   replacing the native kernel whose fixed cost dominates at that size. It must
   reproduce networkx's order exactly — nbunch order outer, adjacency order
   inner, second endpoint deduped, and the node added to ``seen`` only AFTER
   its own row so a self-loop still emits (br-r37-c1-6yimw) — and yield the
   LIVE attribute dict for ``data=True``, not a copy.

3. A one-shot handoff of the materialised rows from ``__len__`` to the
   ``__iter__`` that CPython calls immediately after it in ``list(view)``.
   This one is the dangerous shortcut: a caller can legitimately do ``len(v)``,
   mutate, then iterate, and must see the mutation. The handoff is stamped with
   the graph revision for exactly that reason — the unstamped first version
   reintroduced br-r37-c1-af0ig's staleness and is asserted against below.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", w=1)
    graph.add_edge("b", "c", w=2)
    graph.add_edge("c", "d")
    graph.add_edge("d", "d")  # self-loop
    graph.add_node("iso")
    return graph


def _pair(cls_name):
    return _build(nx, cls_name), _build(fnx, cls_name)


def _outcome(fn, graph):
    try:
        return ("ok", fn(graph))
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc))


# Every nbunch spelling networkx accepts. Only the plain-list ones reach the
# call-shape short-circuit; the rest must keep working through the long path.
NBUNCH_FORMS = {
    "list-one": lambda g: g.edges(["a"]),
    "list-many": lambda g: g.edges(["a", "b", "c"]),
    "list-with-absent": lambda g: g.edges(["a", "zz"]),
    "list-empty": lambda g: g.edges([]),
    "list-duplicated": lambda g: g.edges(["a", "a", "b"]),
    "list-selfloop-node": lambda g: g.edges(["d"]),
    "tuple": lambda g: g.edges(("a", "b")),
    "set": lambda g: g.edges({"a", "b"}),
    "generator": lambda g: g.edges(n for n in ["a", "b"]),
    "single-node-str": lambda g: g.edges("a"),
    "range": lambda g: g.edges(range(0)),
    "none": lambda g: g.edges(None),
    "no-arg": lambda g: g.edges(),
}
DATA_FORMS = {
    "data=True": lambda g, nb: g.edges(nb, data=True),
    "data=False": lambda g, nb: g.edges(nb, data=False),
    "data='w'": lambda g, nb: g.edges(nb, data="w"),
    "data='w',default": lambda g, nb: g.edges(nb, data="w", default=-1),
    "positional-data": lambda g, nb: g.edges(nb, True),
    "kw-nbunch": lambda g, nb: g.edges(nbunch=nb, data=True),
}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form_name", list(NBUNCH_FORMS))
def test_every_nbunch_spelling_matches_networkx(cls_name, form_name):
    form = NBUNCH_FORMS[form_name]
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda g: sorted(map(str, form(g))), gfx) == _outcome(
        lambda g: sorted(map(str, form(g))), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form_name", list(DATA_FORMS))
@pytest.mark.parametrize("nbunch", [["a"], ["a", "b", "c"], ["a", "zz"]], ids=["one", "many", "absent"])
def test_data_forms_match_networkx(cls_name, form_name, nbunch):
    form = DATA_FORMS[form_name]
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda g: sorted(map(str, form(g, nbunch))), gfx) == _outcome(
        lambda g: sorted(map(str, form(g, nbunch))), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("size", [1, 2, 8, 9, 16, 40], ids=lambda s: f"nbunch{s}")
def test_walk_and_kernel_agree_across_the_threshold(cls_name, size):
    """The threshold picks a STRATEGY; both must give networkx's answer.

    Sizes straddle _EDGES_NBUNCH_PY_WALK_MAX deliberately, so a mistake in the
    gate shows up as a parity failure rather than only as a slow path.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        for i in range(40):
            graph.add_edge(f"x{i}", f"x{(i + 1) % 40}")
    nbunch = [f"x{i}" for i in range(size)]
    assert list(gfx.edges(nbunch)) == list(gnx.edges(nbunch))
    assert list(gfx.edges(nbunch, data=True)) == list(gnx.edges(nbunch, data=True))
    assert len(gfx.edges(nbunch)) == len(gnx.edges(nbunch))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_iteration_order_is_networkxs_exactly(cls_name):
    """Not sorted: nbunch order outer, adjacency order inner, dedup by second."""
    gnx, gfx = _pair(cls_name)
    for nbunch in (["a", "b"], ["b", "a"], ["c", "a", "b"], ["d"]):
        assert list(gfx.edges(nbunch)) == list(gnx.edges(nbunch)), nbunch
        assert list(gfx.edges(nbunch, data=True)) == list(
            gnx.edges(nbunch, data=True)
        ), nbunch


@pytest.mark.parametrize("cls_name", CLASSES)
def test_data_true_yields_the_live_attribute_dict(cls_name):
    """The walk must hand back the graph's dict, not a copy.

    networkx yields the live attr dict, so a write through the yielded dict is
    visible on the graph. A walk that copied would silently break that.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        for u, v, data in graph.edges(["a"], data=True):
            data["marked"] = True
    assert gfx["a"]["b"] == gnx["a"]["b"]
    assert "marked" in (gfx["a"]["b"][0] if gfx.is_multigraph() else gfx["a"]["b"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_len_then_mutate_then_iterate_sees_the_mutation(cls_name):
    """The handoff hazard, asserted directly.

    ``len(v)`` materialises and hands the rows to the next ``__iter__``. A
    caller who mutates in between must NOT get the pre-mutation rows.
    """
    outcomes = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        view = graph.edges(["a"])
        before = len(view)
        graph.add_edge("a", "zz")
        outcomes.append((before, sorted(map(str, view)), len(view)))
    assert outcomes[1] == outcomes[0]
    assert any("zz" in entry for entry in outcomes[1][1])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_repeated_len_and_iteration_are_stable(cls_name):
    """The handoff is consumed once; it must not leak into later reads."""
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = gnx.edges(["a", "b"]), gfx.edges(["a", "b"])
    for _ in range(3):
        assert len(view_fx) == len(view_nx)
        assert list(view_fx) == list(view_nx)
        assert list(view_fx) == list(view_nx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_mutating_during_iteration_still_fails_fast(cls_name):
    """The walk must stay behind the fail-fast guard.

    Asserted on the UNRESTRICTED form, where both libraries raise. The nbunch
    form is deliberately not asserted here: fnx raises there and networkx does
    NOT, because nx pre-builds the (node, row) pair list so growing the graph
    resizes no dict it is walking. That is fnx being STRICTER than networkx —
    pre-existing, verified against a tree without this bead's changes, and
    filed as br-r37-c1-u5tyh.
    """
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        with pytest.raises(RuntimeError):
            for _edge in graph.edges(data=True):
                graph.add_edge("brand", "new")


# The mutations networkx tolerates mid-iteration, and the ones it does not.
# networkx has no policy here: its nbunch view walks the LIVE row dicts, so the
# answer is whatever CPython says when the dict under iteration is resized.
MUTATIONS_DURING_ITERATION = {
    "add_edge_new_nodes": lambda g: g.add_edge("brand", "new"),
    "add_edge_onto_iterated_row": lambda g: g.add_edge("a", "c"),
    "add_node": lambda g: g.add_node("solo"),
    "remove_edge_elsewhere": lambda g: g.remove_edge("c", "d"),
    "remove_node_elsewhere": lambda g: g.remove_node("iso"),
    "remove_frozen_node": lambda g: g.remove_node("a"),
    "clear": lambda g: g.clear(),
}


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("mutation", list(MUTATIONS_DURING_ITERATION), ids=list(MUTATIONS_DURING_ITERATION))
def test_simple_class_nbunch_iteration_matches_networkx_mutation_for_mutation(cls_name, mutation):
    """br-r37-c1-u5tyh on Graph: both directions, one mutation at a time.

    fnx used to be wrong BOTH ways at once here — it raised where networkx
    completes (adding a node, removing an unrelated node, clear) and completed
    where networkx raises (adding an edge onto the row being iterated). Walking
    the live rows gets every case right, so this asserts each one rather than
    just "does not over-raise".
    """
    mutate = MUTATIONS_DURING_ITERATION[mutation]
    outcomes = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        iterator = iter(graph.edges(["a", "b"]))
        next(iterator)
        try:
            mutate(graph)
            outcomes.append(("completed", len(list(iterator))))
        except Exception as exc:  # noqa: BLE001
            outcomes.append((type(exc).__name__, exc.args))
    assert outcomes[1] == outcomes[0], mutation


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraphs_still_over_raise_on_nbunch_iteration(cls_name):
    """Pins the REMAINING divergence so the gap cannot go quiet.

    br-r37-c1-u5tyh is fixed for Graph and DiGraph: the multigraphs reach
    edges(nbunch) through view classes whose rows are nested key/attr mappings
    with no live keys-row to walk — the same wall br-r37-c1-dwy1n hit.
    Deliberately an assertion about a bug: when they are fixed this fails and
    says so.
    """
    graph = _build(fnx, cls_name)
    with pytest.raises(RuntimeError):
        for _edge in graph.edges(["a", "b", "c"]):
            graph.add_edge("brand", "new")
    reference = _build(nx, cls_name)
    for _edge in reference.edges(["a", "b", "c"]):
        reference.add_edge("brand", "new")


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unhashable_nbunch_element_raises_networkxs_error(cls_name):
    """br-r37-c1-w5sa7: the short-circuit must not bypass this translation."""
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda g: list(g.edges([["un", "hashable"]])), gfx) == _outcome(
        lambda g: list(g.edges([["un", "hashable"]])), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_one_shot_nbunch_survives_a_later_rebuild(cls_name):
    """A generator nbunch is consumed by the call; the view must still know it.

    br-r37-c1-u5tyh: the freeze ran AFTER the call had drained the generator, so
    it recorded an empty nbunch and every rebuild after a mutation
    (br-r37-c1-af0ig) answered with nothing. Latent while only the first read
    mattered.
    """
    outcomes = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        view = graph.edges(n for n in ["a", "b"])
        outcomes.append(sorted(map(str, view)))
        graph.add_edge("b", "zz")
        outcomes.append(sorted(map(str, view)))
    assert outcomes[2:] == outcomes[:2]
    assert outcomes[0]
