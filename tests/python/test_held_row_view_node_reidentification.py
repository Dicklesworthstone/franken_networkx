"""Regression contracts for held rows across removal, re-addition, and collection.

The original divergence below is retained as history, not as a current failure
or an expected xfail. All cases assert the real contract. The later u8rs5 cases
also cover sequential retirement, self-loops, orphaned lookup caches, numeric
aliases, partial errors, collection, and copy isolation.

FOUND BY A SEEDED MUTATION FUZZER, not by reading code, and it is PRE-EXISTING:
the identical divergence reproduces byte-for-byte on builds either side of
br-r37-c1-2ndmw's row-membership index path, so it is not caused by that change.

THE SHAPE. Hold `row = G.adj[u]`, remove `u`, then add `u` back with a different
edge. networkx's `AtlasView` wraps the `_adj[u]` DICT OBJECT, and removing the
node detaches that dict — so the held view keeps reporting the pre-removal
neighbours forever, and never sees the re-added ones. FrankenNetworkX's row view
reads live by node NAME, so once `u` exists again the same held view reports the
NEW neighbours:

    G = MultiGraph(); G.add_edge("u", "a")
    row = G.adj["u"]
    G.remove_node("u")
    G.add_edge("u", "b")

    networkx : "a" in row -> True    "b" in row -> False    len(row) == 1
    fnx before the repair: "a" in row -> False  "b" in row -> True  len(row) == 1

Neither is a counting bug — both report one neighbour. They disagree about WHICH
graph the held view still belongs to. networkx binds the view to an object
identity that a removal destroys; fnx binds it to a name that a re-add revives.

WHY IT IS NARROW, and the reason the passing tests below matter as much as the
original regression: liveness was otherwise IDENTICAL. Holding a row across an edge
addition, an edge removal, an unrelated node addition, or an unrelated node
REMOVAL (which renumbers internal positions) agrees with networkx exactly. Only
re-identification of the row's own node diverges. Any fix must preserve all four
of those, which is why they are pinned here rather than left implicit — the
obvious repair, detaching the row view on node removal, is easy to over-apply.
"""

from __future__ import annotations

import copy
import gc
import weakref

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _probe(mod, cls_name, script):
    g = getattr(mod, cls_name)()
    return script(g)


def _both(cls_name, script):
    return _probe(nx, cls_name, script), _probe(fnx, cls_name, script)


# --------------------------------------------------------------- the divergence


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_after_node_removal_and_readd_matches_networkx(cls_name):
    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"]
        g.remove_node("u")
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("source", ["adj", "getitem"])
def test_held_row_after_batch_removal_and_readd_matches_networkx(cls_name, source):
    """Both public row spellings must detach before ``remove_nodes_from``."""

    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"] if source == "adj" else g["u"]
        g.remove_nodes_from(["missing", "u"])
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}/{source}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("source", ["succ", "pred"])
def test_held_directed_row_after_removal_and_readd_matches_networkx(cls_name, source):
    """The directed aliases carry independent row caches and both detach."""

    def script(g):
        if source == "succ":
            g.add_edge("u", "a")
            row = g.succ["u"]
            g.remove_node("u")
            g.add_edge("u", "b")
            old, new = "a", "b"
        else:
            g.add_edge("a", "u")
            row = g.pred["u"]
            g.remove_node("u")
            g.add_edge("b", "u")
            old, new = "a", "b"
        return {"old": old in row, "new": new in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}/{source}: nx={want} fnx={got}"


# ------------------------------------------------- the liveness that AGREES today
# These pass now and must keep passing: they bound any repair of the case above.


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_tracks_edge_addition(cls_name):
    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"]
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_tracks_edge_removal(cls_name):
    def script(g):
        g.add_edge("u", "a")
        g.add_edge("u", "b")
        row = g.adj["u"]
        g.remove_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_survives_unrelated_node_addition(cls_name):
    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"]
        g.add_node("newnode")
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_survives_unrelated_node_removal(cls_name):
    """The renumbering case. Removing a node reorders internal positions, and the
    row view caches its node's position — so this is the one that would break if
    that cache were not generation-stamped."""

    def script(g):
        g.add_edge("u", "a")
        g.add_node("z")
        row = g.adj["u"]
        g.remove_node("z")
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_of_an_untouched_node_is_unaffected_by_a_neighbours_removal(cls_name):
    """Removing the NEIGHBOUR, not the row's own node, must agree — this is the
    boundary of the divergence and the case a fix is most likely to overreach on."""

    def script(g):
        g.add_edge("u", "a")
        g.add_edge("u", "b")
        row = g.adj["u"]
        g.remove_node("a")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


ROW_SOURCES = [
    (cls_name, source)
    for cls_name in CLASSES
    for source in (
        ("adj", "getitem", "succ", "pred")
        if "DiGraph" in cls_name
        else ("adj", "getitem")
    )
]


@pytest.mark.parametrize("cls_name,source", ROW_SOURCES)
@pytest.mark.parametrize("method", ["remove_node", "remove_nodes_from"])
@pytest.mark.parametrize("order", [(0,), (0, 1), (1, 0), (0, 99, 2), (1, 1, 0), (99, 2, 0)])
@pytest.mark.parametrize("self_loop", [False, True])
@pytest.mark.parametrize("labels", ["int", "str"])
def test_held_removed_row_retains_sequential_removal_contents(
    cls_name, source, method, order, self_loop, labels
):
    """Retiring a row must see earlier removals, not later ones (u8rs5)."""
    def script(g):
        node = (lambda n: n) if labels == "int" else (lambda n: f"node-{n}")
        edges = [(0, 1), (0, 2), (3, 0), (2, 1)]
        if g.is_directed():
            edges.append((1, 0))
        if self_loop:
            edges.append((0, 0))
        for index, (u, v) in enumerate(edges):
            g.add_edge(node(u), node(v), weight=index + 1)
            if g.is_multigraph():
                g.add_edge(node(u), node(v), key="parallel", weight=index + 10)
        rows = {
            n: g[node(n)] if source == "getitem" else getattr(g, source)[node(n)]
            for n in (0, 1, 2, 3)
        }
        # Exercise already-materialized rows, not only lazy lookups after removal.
        for row in rows.values():
            list(row)

        def contents():
            return {
                n: [(neighbor, dict(value)) for neighbor, value in row.items()]
                for n, row in rows.items()
            }

        before = contents()
        if method == "remove_node":
            for n in order:
                if node(n) in g:
                    g.remove_node(node(n))
        else:
            g.remove_nodes_from([node(n) for n in order])
        removed = contents()
        remaining = (list(g), list(g.edges(data=True)))
        # Detached rows must stay detached; surviving rows must stay live.
        g.add_edge(node(0), node(7), weight=77)
        g.add_edge(node(1), node(8), weight=88)
        return before, removed, remaining, contents()

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}/{source}/{method}/{order}/{labels}: nx={want} fnx={got}"


MULTI_ROW_SOURCES = [(cls_name, source) for cls_name, source in ROW_SOURCES if cls_name.startswith("Multi")]


def _held_row(g, node, source):
    return g[node] if source == "getitem" else getattr(g, source)[node]


@pytest.mark.parametrize("cls_name,source", MULTI_ROW_SOURCES)
@pytest.mark.parametrize("operation", ["remove_node", "clear"])
def test_held_row_detaches_after_lookup_cache_replacement(cls_name, source, operation):
    def script(g):
        g.add_edge("u", "a", weight=1)
        g.add_edge("a", "u", weight=2)
        row = _held_row(g, "u", source)
        g.add_node("unrelated")
        _held_row(g, "a", source)  # Replace the cache holding `row`.
        before = [(n, dict(d)) for n, d in row.items()]
        if operation == "remove_node":
            g.remove_node("u")
        else:
            g.clear()
        g.add_edge("u", "new", weight=3)
        g.add_edge("new", "u", weight=4)
        return before, [(n, dict(d)) for n, d in row.items()]

    want, got = _both(cls_name, script)
    assert got == want


@pytest.mark.parametrize("cls_name,source", MULTI_ROW_SOURCES)
def test_held_row_registry_does_not_retain_dead_rows_or_buckets(cls_name, source):
    g = getattr(fnx, cls_name)()
    g.add_edge("u", "a")
    row = _held_row(g, "u", source)
    reference = weakref.ref(row)
    g.add_node("unrelated")
    _held_row(g, "a", source)
    del row
    gc.collect()
    assert reference() is None
    assert "u" not in vars(g)["_fnx_held_multigraph_rows"]


@pytest.mark.parametrize("cls_name,source", MULTI_ROW_SOURCES)
def test_old_row_expiry_does_not_remove_readded_nodes_registry(cls_name, source):
    g = getattr(fnx, cls_name)()
    g.add_edge("u", "a")
    old_row = _held_row(g, "u", source)
    # Retain the old weakref so its callback can execute after the bucket is
    # replaced. It must not retire a different row of the re-added node.
    old_reference = next(iter(vars(g)["_fnx_held_multigraph_rows"]["u"].values()))
    g.remove_node("u")
    g.add_edge("u", "new")
    new_row = _held_row(g, "u", source)
    new_bucket = vars(g)["_fnx_held_multigraph_rows"]["u"]
    del old_row
    gc.collect()
    assert old_reference() is None
    assert vars(g)["_fnx_held_multigraph_rows"]["u"] is new_bucket
    assert any(reference() is new_row for reference in new_bucket.values())


@pytest.mark.parametrize("cls_name,source", ROW_SOURCES)
@pytest.mark.parametrize("failure", ["unhashable", "iterator"])
@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_held_rows_match_after_partial_removal_error(cls_name, source, failure, order):
    def script(g):
        g.add_edges_from([(0, 1), (1, 2), (0, 0), (2, 0)])
        rows = {n: _held_row(g, n, source) for n in (0, 1, 2)}
        for row in rows.values():
            list(row)
        if failure == "unhashable":
            nodes = [*order, [], 2]
        else:
            def broken_iterator():
                yield from order
                raise ValueError("iterator stopped")
            nodes = broken_iterator()
        try:
            g.remove_nodes_from(nodes)
        except (TypeError, ValueError) as exc:
            error = (type(exc).__name__, exc.args)
        else:
            raise AssertionError("the populated error probe did not raise")
        return error, list(g), {n: list(row) for n, row in rows.items()}

    want, got = _both(cls_name, script)
    assert got == want


@pytest.mark.parametrize("cls_name,source", ROW_SOURCES)
def test_held_rows_retire_once_for_equal_numeric_removal_labels(cls_name, source):
    def script(g):
        g.add_edges_from([(0, 1), (1, 2), (0, 0), (1, 1), (2, 0)])
        rows = {n: _held_row(g, n, source) for n in (0, 1, 2)}
        for row in rows.values():
            list(row)
        g.remove_nodes_from([1.0, True, 0.0])
        return list(g), {n: [(type(v).__name__, repr(v)) for v in row] for n, row in rows.items()}

    want, got = _both(cls_name, script)
    assert got == want


@pytest.mark.parametrize("cls_name,source", MULTI_ROW_SOURCES)
def test_held_row_registry_does_not_keep_graph_cycles_alive(cls_name, source):
    references = []
    for _ in range(50):
        g = getattr(fnx, cls_name)()
        g.add_edge("u", "a")
        _held_row(g, "u", source)
        assert "u" in vars(g)["_fnx_held_multigraph_rows"]
        references.append(weakref.ref(g))
    del g
    gc.collect()
    gc.collect()
    assert all(reference() is None for reference in references)


@pytest.mark.parametrize("cls_name,source", MULTI_ROW_SOURCES)
@pytest.mark.parametrize("clone", ["copy", "deepcopy"])
def test_cloned_graph_removal_cannot_retire_original_held_rows(cls_name, source, clone):
    def script(g):
        g.add_edge("u", "a")
        g.add_edge("a", "u")
        row = _held_row(g, "u", source)
        other = g.copy() if clone == "copy" else copy.deepcopy(g)
        other.remove_node("u")
        # The original row must still be live after removal from the copy.
        g.add_edge("u", "new")
        g.add_edge("new", "u")
        return list(row), list(g), list(other)

    want, got = _both(cls_name, script)
    assert got == want
