"""br-r37-c1-2ndmw — what the CHEAPER multigraph cell construction must not break.

`G[u][v]` on a multigraph is `AdjacencyView.__getitem__` on a captured row, and
at 2000-character node keys it was 606.5 ns against networkx's 129.9 ns. The
decomposition said the cost was not the lookup at all:

    hash(v) explicitly                       23.7 ns
    row._atlas()  (frame + constant lambda)  58.1 ns
    v in atlas    (native MultiAtlasView)    58.5 ns
    AtlasView(...) construction             318.1 ns   <- 52 percent

and 132 ns of that constructor was KEYWORD MATCHING alone: the identical body
called positionally is 130.1 ns where four keywords cost 262.3 ns on CPython
3.13.7. So the lever is three mechanical changes, and each one is a way to get
this wrong:

  1. `AtlasView.__init__` loses its `*`, so the five parameters are
     positional-or-keyword, and the hot call site passes positionally.
  2. Three fields whose only constructor value is `None` become CLASS defaults
     — but ONLY on the multigraph-cell shape. Unconditionally they are a net
     loss, because a class default is an instance-dict miss and a `DiGraph` row
     reads all three on every subscript without ever writing them; that cost a
     disjoint 4-5 percent on a row this lever does not touch.
  3. `AdjacencyView.__getitem__` reads `_fnx_captured_row` instead of calling
     `_atlas()`, and skips the explicit `hash(node)` on that path — which also
     required wiring `_fnx_captured_row` on the `G[u]` row builders, where
     br-r37-c1-fr4me had wired it only on `G.adj[u]`.
  4. `AtlasView._atlas` memoises the multigraph CELL's resolved native
     `MultiKeyDictView`. The getter was `lambda: row._atlas()[v]`, so every
     operation on a held cell re-resolved the pair — 423.4 ns of a 769.6 ns
     `cell[k]` at K=3 and 2933.0 ns of 3300.1 ns at K=2000, against networkx's
     71.0 ns and 48.4 ns. That one is also a PARITY FIX; see below.

THE FOUR NEGATIVE CASES, one per change:

  * A class default is SHARED. If a later cache fill ever assigned to the class
    instead of the instance, one row's warm keydict would be served to every
    other row in the process — a silent wrong-answer bug that no timing shows.
    `test_class_default_fields_do_not_leak_between_instances` writes on one
    instance and asserts every other instance still reads `None`.
  * Dropping the explicit `hash(node)` is only sound because the captured row —
    a native `MultiAtlasView`/`MultiDiAtlasView` since br-r37-c1-mh4sg, or the
    plain dict `_detach_row` installs — raises `TypeError` for an unhashable key
    by itself. The comment that this hunk replaced asserted the OPPOSITE (that
    the native view answers `False`), which was true when it was written and is
    false now. `test_unhashable_cell_key_raises_typeerror_on_the_captured_row`
    pins the current behaviour against networkx's own message, so if the native
    view ever reverts to answering `False` this fails instead of silently
    turning networkx's `TypeError` into a `KeyError`.
  * A cheaper wrapper is worthless if it is reached by caching the wrapper.
    networkx returns a FRESH mapping from a multigraph `G[u][v]` on every call,
    so `row[v] is row[v]` is False there; caching would be a parity break that
    looks like a much bigger win.
  * Memoising the cell's atlas is only safe because a `MultiKeyDictView` reads
    THROUGH to the graph — key add/remove and attribute writes are all visible
    through a held one. A memo of a MATERIALISED mapping would pass every
    single-shot test and go stale on the first mutation, so
    `test_memoised_cell_atlas_stays_live` mutates in three ways after the memo
    is filled. And where the memo does change an answer it moves TOWARD
    networkx: after the last parallel edge of a pair is removed, networkx keeps
    serving the (now empty) keydict while fnx used to raise the ROW's KeyError
    from the cell. That is asserted against networkx's own exception args.

These are read-path contracts, not timings — nothing here asserts a duration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))

import franken_networkx as fnx  # noqa: E402

MULTI_CLASSES = ("MultiGraph", "MultiDiGraph")
ALL_CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _pair(cls_name, *, length=3):
    """One graph per library, same edges, plus bulk so the pair is not alone."""
    u, v = "u" * length, "v" * length
    out = []
    for module in (nx, fnx):
        graph = getattr(module, cls_name)()
        graph.add_edge(u, v, weight=1)
        if graph.is_multigraph():
            graph.add_edge(u, v, weight=2)
        for i in range(8):
            graph.add_edge(f"a{i}", f"b{i}")
        out.append(graph)
    return out[0], out[1], u, v


# ---------------------------------------------------------------------------
# 1. class-level defaults
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "field", ["_fnx_live_keydict", "_fnx_kd_cache", "_fnx_edge_fast"]
)
def test_class_default_fields_do_not_leak_between_instances(field):
    """A class default must still be written PER INSTANCE.

    The whole point of hoisting these to the class is that `__init__` no longer
    stores them, so the only thing standing between "cheap constructor" and
    "every row shares one cache" is that the fill sites assign to `self`. A
    naive version that did `AtlasView._fnx_kd_cache = ...` would pass every
    single-graph test and corrupt every multi-graph process.

    The views are built in the MULTIGRAPH CELL shape, because that is the only
    shape that leaves the fields on the class — see
    `test_non_multi_views_keep_instance_storage_for_the_read_path`.
    """
    owner = fnx.MultiGraph()
    view_a = fnx.AtlasView(lambda: {}, None, "a", "adj", owner)
    view_b = fnx.AtlasView(lambda: {}, None, "b", "adj", owner)

    assert getattr(view_a, field) is None
    assert getattr(view_b, field) is None

    sentinel = object()
    setattr(view_a, field, sentinel)

    assert getattr(view_a, field) is sentinel
    assert getattr(view_b, field) is None, (
        f"{field} leaked from one AtlasView to another — it was written on the "
        "class, not the instance"
    )
    assert getattr(fnx.AtlasView, field) is None, (
        f"the class default for {field} was overwritten"
    )
    assert field not in vars(view_b)


@pytest.mark.parametrize(
    "field", ["_fnx_live_keydict", "_fnx_kd_cache", "_fnx_edge_fast"]
)
def test_non_multi_views_keep_instance_storage_for_the_read_path(field):
    """The class default is deliberately NOT applied to non-multigraph views.

    A class default is an instance-dict MISS, so every read of a never-written
    field pays the type-dict fallback afterwards. A `DiGraph` row is built once
    and then reads all three fields on every subscript, and its owner is None so
    they are never written — making them class-level cost that row a disjoint
    4-5 percent (0.4911/0.5185x -> 0.4778/0.4627x vs networkx). This asserts the
    branch that buys the construction saving only where the reads do not pay for
    it; without it, the fields would be absent from `vars()` here too.
    """
    row = fnx.AtlasView(lambda: {"n": {}})
    assert field in vars(row), (
        f"{field} was left on the class for a non-multigraph view — every "
        "subscript on this row now pays a type-dict fallback to read it"
    )
    assert getattr(row, field) is None


def test_class_default_fields_are_readable_before_any_write():
    """Every read site must resolve through the class, not raise."""
    view = fnx.AtlasView(lambda: {"n": {}})
    assert view._fnx_live_keydict is None
    assert view._fnx_kd_cache is None
    assert view._fnx_edge_fast is None
    # And the Mapping surface still works on a never-written instance.
    assert list(view) == ["n"]
    assert len(view) == 1
    assert "n" in view


def test_warming_one_multigraph_row_does_not_warm_another():
    """End-to-end version of the leak test, through the public API."""
    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", weight=1)
    graph.add_edge("c", "d", weight=1)

    warm = graph["a"]["b"]
    list(warm)  # fills _fnx_kd_cache on this cell view only

    cold = graph["c"]["d"]
    assert cold._fnx_kd_cache is None, (
        "a cold cell view served the warm cell's cached keydict"
    )
    assert list(cold) == list(graph.get_edge_data("c", "d"))


# ---------------------------------------------------------------------------
# 2. the dropped hash()
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", ALL_CLASSES)
@pytest.mark.parametrize("bad", [["x"], {1: 2}, {"s"}, bytearray(b"k")])
def test_unhashable_cell_key_raises_typeerror_on_the_captured_row(cls_name, bad):
    """`row[unhashable]` is networkx's TypeError, not a KeyError.

    `AdjacencyView.__getitem__` no longer calls `hash(node)` when it is serving
    a captured row; the probe underneath has to raise on its own. This is the
    exact failure the removed comment warned about, so it is asserted against
    networkx's own exception rather than merely against `TypeError`.
    """
    graph_nx, graph_fnx, u, _v = _pair(cls_name)

    with pytest.raises(TypeError) as nx_exc:
        graph_nx[u][bad]
    with pytest.raises(TypeError) as fnx_exc:
        graph_fnx[u][bad]

    assert str(fnx_exc.value) == str(nx_exc.value)

    # Same through the `G.adj[u]` spelling, which reaches the same row.
    with pytest.raises(TypeError):
        graph_fnx.adj[u][bad]


@pytest.mark.parametrize("cls_name", ALL_CLASSES)
def test_missing_cell_key_keeps_the_original_key_object_in_the_error(cls_name):
    """The ABSENT path is deliberately unchanged — including non-str keys."""
    graph_nx, graph_fnx, u, _v = _pair(cls_name)
    for missing in ("zz", 17, (1, 2), 3.5, frozenset({1})):
        with pytest.raises(KeyError) as nx_exc:
            graph_nx[u][missing]
        with pytest.raises(KeyError) as fnx_exc:
            graph_fnx[u][missing]
        assert fnx_exc.value.args == nx_exc.value.args
        assert type(fnx_exc.value.args[0]) is type(missing)


# ---------------------------------------------------------------------------
# 3. the wrapper is still FRESH, and still LIVE
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_cell_wrapper_identity_matches_networkx(cls_name):
    """networkx hands back a new mapping per subscript; so must fnx.

    Caching the wrapper is the obvious way to make this call cheap and it is
    forbidden — it would make `row[v] is row[v]` True where networkx says False.
    """
    graph_nx, graph_fnx, u, v = _pair(cls_name)
    row_nx, row_fnx = graph_nx[u], graph_fnx[u]

    assert (row_nx[v] is row_nx[v]) is False
    assert (row_fnx[v] is row_fnx[v]) is False
    assert (graph_nx[u][v] is graph_nx[u][v]) is False
    assert (graph_fnx[u][v] is graph_fnx[u][v]) is False


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_captured_row_stays_live_across_edge_mutation(cls_name):
    """`_fnx_captured_row` is now wired on the `G[u]` builder too.

    It holds the native row object rather than a getter, so the thing it must
    keep is liveness: an edge added after the row was captured has to be
    visible through the captured handle.
    """
    graph_nx, graph_fnx, u, v = _pair(cls_name)
    row_nx, row_fnx = graph_nx[u], graph_fnx[u]

    for graph in (graph_nx, graph_fnx):
        graph.add_edge(u, "late", weight=9)

    assert "late" in row_fnx
    assert ("late" in row_fnx) == ("late" in row_nx)
    assert dict(row_fnx["late"]) == dict(row_nx["late"])

    for graph in (graph_nx, graph_fnx):
        graph.remove_edge(u, "late")
    assert ("late" in row_fnx) == ("late" in row_nx)


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_both_row_spellings_agree_now_that_both_capture(cls_name):
    """`G[u]` and `G.adj[u]` had different capture wiring; they must not differ.

    br-r37-c1-fr4me set `_fnx_captured_row` on the `G.adj[u]` builder only, so
    the two spellings of the same row took different paths through
    `__getitem__`. Whatever else changes, they have to answer identically.
    """
    _graph_nx, graph_fnx, u, v = _pair(cls_name)
    direct = graph_fnx[u]
    via_adj = graph_fnx.adj[u]

    assert direct._fnx_captured_row is not None, (
        "G[u] built a row without capturing it — the fast path is dead"
    )
    assert via_adj._fnx_captured_row is not None

    assert dict(direct[v]) == dict(via_adj[v])
    assert (v in direct) == (v in via_adj)
    assert sorted(direct) == sorted(via_adj)
    with pytest.raises(KeyError):
        direct["nope"]
    with pytest.raises(KeyError):
        via_adj["nope"]


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_inner_attr_dict_identity_survives_the_cheaper_wrapper(cls_name):
    """The binding constraint: `G[u][v][key]['w'] = x` must reach the graph."""
    graph_nx, graph_fnx, u, v = _pair(cls_name)
    for graph in (graph_nx, graph_fnx):
        key = next(iter(graph[u][v]))
        graph[u][v][key]["w"] = 99
    assert graph_fnx.get_edge_data(u, v) == graph_nx.get_edge_data(u, v)
    assert graph_fnx[u][v][0] is graph_fnx[u][v][0]


# ---------------------------------------------------------------------------
# 4. the positional signature stays keyword-compatible
# ---------------------------------------------------------------------------
def test_atlasview_positional_and_keyword_construction_agree():
    """Dropping the `*` must not change what any existing call site means."""
    owner = fnx.MultiGraph()
    owner.add_edge("a", "b")
    atlas = {"b": {0: {}}}

    positional = fnx.AtlasView(lambda: atlas, None, "a", "adj", owner)
    keyword = fnx.AtlasView(
        lambda: atlas,
        owner=None,
        row_node="a",
        row_kind="adj",
        multi_edge_owner=owner,
    )

    for view in (positional, keyword):
        assert view._fnx_owner is None
        assert view._fnx_row_node == "a"
        assert view._fnx_row_kind == "adj"
        assert view._fnx_multi_edge_owner is owner
    assert list(positional) == list(keyword)


def test_atlasview_defaults_unchanged_for_a_bare_construction():
    view = fnx.AtlasView(lambda: {"x": {}})
    assert view._fnx_owner is None
    assert view._fnx_row_node is None
    assert view._fnx_row_kind == "adj"
    assert view._fnx_multi_edge_owner is None


# ---------------------------------------------------------------------------
# 5. the detached-row path, which is the other `_fnx_captured_row` shape
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_detached_row_serves_its_snapshot_and_still_raises_typeerror(cls_name):
    """`_detach_row` swaps the captured row for a plain dict snapshot.

    `__getitem__` now reads that attribute directly, so the detached shape has
    to satisfy the same two contracts: serve the frozen contents, and raise
    networkx's TypeError for an unhashable key (a dict `in` hashes, so it does).

    THE SPELLING IS `G.adj[u]`, NOT `G[u]`, and that is not incidental. Only the
    `G.adj[u]` row builder is reached by `_detach_row`; a row held from `G[u]`
    raises `KeyError` after `clear()` where networkx still serves its contents.
    That divergence is PRE-EXISTING — it reproduces identically on the arm
    before this lever — so it is filed separately (br-r37-c1-wdgb8)
    rather than pinned here, and this test uses the spelling whose contract this
    lever actually has to preserve.
    """
    _graph_nx, graph_fnx, u, v = _pair(cls_name)
    row = graph_fnx.adj[u]
    before = dict(row[v])

    graph_fnx.clear()

    assert dict(row[v]) == before, "a detached row lost its snapshot"
    with pytest.raises(TypeError):
        row[["x"]]
    with pytest.raises(KeyError):
        row["never-existed"]


# ---------------------------------------------------------------------------
# 6. the untouched siblings stay untouched
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", ALL_CLASSES)
def test_row_subscript_values_match_networkx(cls_name):
    """The whole read surface of the cell, on every class, against networkx."""
    graph_nx, graph_fnx, u, v = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]

    assert type(cell_fnx).__name__ == type(cell_nx).__name__
    assert list(cell_fnx) == list(cell_nx)
    assert len(cell_fnx) == len(cell_nx)
    assert dict(cell_fnx) == dict(cell_nx)
    for key in cell_nx:
        assert key in cell_fnx
        assert dict(cell_fnx[key]) == dict(cell_nx[key]) if graph_nx.is_multigraph() else True
    assert ("absent" in cell_fnx) == ("absent" in cell_nx)


# ---------------------------------------------------------------------------
# 7. the memoised cell atlas (br-r37-c1-2ndmw, second lever)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_cell_after_all_parallel_edges_removed_matches_networkx(cls_name):
    """A PARITY FIX, and the reason the memo is more than a cost change.

    networkx's `G[u][v]` wraps the keydict OBJECT, so when the last parallel
    edge of the pair goes away the held cell keeps serving that dict — now
    empty — and `cell[0]` raises `KeyError(0)`. fnx used to re-resolve the pair
    through the native row on every operation, find it gone, and raise the ROW's
    `KeyError('vvv')` from an operation on a cell the caller already held:

        nx   sorted(cell) == []          cell[0] -> KeyError(0)
        fnx  sorted(cell) -> KeyError('vvv')

    Memoising the resolved native view reproduces networkx exactly, key included.

    THE FIX IS CONDITIONAL ON THE CELL HAVING BEEN READ, and that is asserted
    deliberately by the `sorted()` below rather than left implicit: the memo
    fills on the FIRST resolution, so a cell that is constructed and never
    touched before the pair vanishes has nothing to serve and still raises the
    row's KeyError. Resolving eagerly at construction would make it
    unconditional and would also put the 700-2900 ns resolution back on every
    `G[u][v]`, which is the cost this bead just removed. The residual is pinned
    by `test_untouched_cell_after_removal_still_diverges_from_networkx`.
    """
    graph_nx, graph_fnx, u, v = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]

    keys = sorted(cell_nx)
    assert sorted(cell_fnx) == keys  # <- the read that fills the memo
    for key in keys:
        graph_nx.remove_edge(u, v, key)
        graph_fnx.remove_edge(u, v, key)

    assert sorted(cell_fnx) == sorted(cell_nx) == []
    assert len(cell_fnx) == len(cell_nx) == 0

    with pytest.raises(KeyError) as nx_exc:
        cell_nx[0]
    with pytest.raises(KeyError) as fnx_exc:
        cell_fnx[0]
    assert fnx_exc.value.args == nx_exc.value.args


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_memoised_cell_atlas_stays_live(cls_name):
    """The memo holds a LIVE native view, not a snapshot.

    `MultiKeyDictView` reads through to the graph on every call, which is the
    whole reason the handle is safe to keep. If a future change ever memoised a
    materialised dict instead, every one of these would go stale.
    """
    graph_nx, graph_fnx, u, v = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]

    for graph in (graph_nx, graph_fnx):
        graph.add_edge(u, v, weight=3)
    assert sorted(cell_fnx) == sorted(cell_nx)

    first = sorted(cell_nx)[0]
    for graph in (graph_nx, graph_fnx):
        graph.remove_edge(u, v, first)
    assert sorted(cell_fnx) == sorted(cell_nx)

    live = sorted(cell_nx)[0]
    cell_nx[live]["weight"] = 41
    cell_fnx[live]["weight"] = 41
    assert dict(cell_fnx[live]) == dict(cell_nx[live])
    assert graph_fnx.get_edge_data(u, v, live)["weight"] == 41


def test_non_cell_views_do_not_memoise_their_atlas():
    """Only a multigraph cell memoises; a genuinely varying getter must not.

    `_atlas()` is shared by every AtlasView in the module, and most of them have
    getters that re-evaluate on purpose. Memoising one of those would freeze a
    view that is supposed to track its source.
    """
    box = [{"a": {}}]
    view = fnx.AtlasView(lambda: box[0])
    assert sorted(view) == ["a"]
    box[0] = {"b": {}}
    assert sorted(view) == ["b"], "a non-cell AtlasView froze its atlas"
    assert view._fnx_captured_atlas is None


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_detach_clears_the_memoised_cell_atlas(cls_name):
    """`_detach_row` rebinds the getter; the memo is consulted BEFORE it.

    A detach that left a stale memo behind would leave the row reading the live
    graph it was explicitly cut loose from, which is the same trap
    br-r37-c1-fr4me hit one level up with `_fnx_captured_row`.
    """
    _graph_nx, graph_fnx, u, v = _pair(cls_name)
    row = graph_fnx.adj[u]
    before = dict(row[v])
    assert before

    graph_fnx.clear()

    assert dict(row[v]) == before
    assert row._fnx_captured_atlas is None


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_untouched_cell_after_removal_still_diverges_from_networkx(cls_name):
    """The RESIDUAL, pinned so it is a known quantity and not a surprise.

    The memo fills on first resolution, so a cell built and never read before
    its pair is removed has no handle to serve and falls back to re-resolving —
    which raises the ROW's KeyError where networkx serves an empty mapping. This
    asserts the divergence rather than hiding it; whoever makes the fix
    unconditional should delete this test, and if they do it by resolving
    eagerly at construction they need a fresh measurement of `G[u][v]` first.
    """
    graph_nx, graph_fnx, u, v = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]  # never read

    for key in sorted(graph_nx.get_edge_data(u, v)):
        graph_nx.remove_edge(u, v, key)
        graph_fnx.remove_edge(u, v, key)

    assert sorted(cell_nx) == []
    with pytest.raises(KeyError) as exc:
        sorted(cell_fnx)
    assert exc.value.args == (v,), (
        "the untouched-cell residual changed shape — if it is now fixed, delete "
        "this test and the caveat it pins in "
        "test_cell_after_all_parallel_edges_removed_matches_networkx"
    )
