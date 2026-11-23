"""Parity lock for br-r37-c1-hcn5w — membership on an adjacency row.

``AdjacencyView`` defined no ``__contains__``, so ``v in G.adj[u]`` fell through
to the ``Mapping`` ABC, whose implementation is ``try: self[key]``. A membership
test therefore built the whole inner keydict view and discarded it — worse than
the ``len()`` sitting next to it on the same object.

A real ``__contains__`` answers from the row instead. What needs pinning is the
CONTRACT it has to carry, because delegating alone got it wrong:

* an UNHASHABLE key is networkx's TypeError, not False. The native atlas's own
  ``__contains__`` answers False, so ``return node in self._atlas()`` REGRESSED
  the multigraphs — they had been raising only as a side effect of the ABC
  calling ``__getitem__``, which hashed on the way to building the value. An
  explicit ``hash()`` restores br-r37-c1-i9whv's contract;
* present, missing, and exotic-but-hashable keys must answer exactly as
  networkx does, on every class and on both ``G.adj[u]`` and ``G[u]``.

KNOWN RESIDUE, filed as br-r37-c1-espyz and excluded by name below: a simple
Graph's row is a NATIVE AtlasView rather than this Python class, so it never
reaches the guard and still answers False for an unhashable key. That is the
last class diverging on this contract and needs a Rust-side fix.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
# Graph's row is the native AtlasView — see br-r37-c1-espyz.
# br-r37-c1-espyz is FIXED, so simple Graph is folded back in and every class
# holds the same contract. The residue pin that used to sit below — an assertion
# that Graph answered False — did its job: it failed the moment the native
# AtlasView started hashing, which is exactly what it was written to do.
UNHASHABLE_FIXED = CLASSES


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("a", "c")
    graph.add_edge("c", "d")
    graph.add_edge("a", "a")  # self-loop
    graph.add_node("iso")
    return graph


ROWS = {
    "G.adj[u]": lambda g, u: g.adj[u],
    "G[u]": lambda g, u: g[u],
}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("row_name", list(ROWS))
@pytest.mark.parametrize(
    "key", ["b", "c", "a", "zz", 99, (1, 2), frozenset({1})], ids=str
)
def test_membership_matches_networkx(cls_name, row_name, key):
    """Present, missing, self-loop and exotic-but-hashable keys."""
    row = ROWS[row_name]
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    assert (key in row(gfx, "a")) == (key in row(gnx, "a"))


@pytest.mark.parametrize("cls_name", UNHASHABLE_FIXED)
@pytest.mark.parametrize("row_name", list(ROWS))
@pytest.mark.parametrize("bad", [["u"], {"u": 1}, {1, 2}], ids=["list", "dict", "set"])
def test_unhashable_key_raises_typeerror(cls_name, row_name, bad):
    """The guard, on both row spellings, on ALL FOUR classes (br-r37-c1-espyz)."""
    row = ROWS[row_name]
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        with pytest.raises(TypeError):
            bad in row(graph, "a")


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_agrees_with_iteration_and_len(cls_name):
    """`in` must not drift from the row's own contents."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    for row_name, row in ROWS.items():
        rnx, rfx = row(gnx, "a"), row(gfx, "a")
        assert sorted(map(str, rfx)) == sorted(map(str, rnx)), row_name
        assert len(rfx) == len(rnx), row_name
        for nbr in rnx:
            assert nbr in rfx, (row_name, nbr)
        assert ("zz" in rfx) == ("zz" in rnx), row_name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_is_live_across_mutation(cls_name):
    """The row is captured (br-r37-c1-znpkv); membership must still be live."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    for graph in (gnx, gfx):
        graph.add_edge("a", "zz")
        graph.remove_edge("a", "b")
    assert ("zz" in rfx) == ("zz" in rnx) is True
    assert ("b" in rfx) == ("b" in rnx) is False
    assert len(rfx) == len(rnx)


# --- br-r37-c1-9ias7: the key snapshot behind __iter__ ---------------------


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "mutation",
    ["add_edge_new_nbr", "remove_edge", "parallel_edge", "add_node", "remove_other_node"],
)
def test_row_iteration_is_live_across_mutation(cls_name, mutation):
    """__iter__ snapshots dict.fromkeys against (nodes_seq, edges_seq).

    A snapshot is exactly the shape that goes stale, so every structural
    mutation that can change a row's KEY SET is checked against networkx. An
    attribute write deliberately is not: it cannot change the keys, so the
    token correctly does not invalidate on it.

    G.clear() is absent on purpose — a multigraph row held across a clear
    diverges from networkx and did so before the snapshot existed
    (br-r37-c1-s5pxs).
    """
    mutate = {
        "add_edge_new_nbr": lambda g: g.add_edge("a", "c"),
        "remove_edge": lambda g: g.remove_edge("a", "b"),
        "parallel_edge": lambda g: g.add_edge("a", "b"),
        "add_node": lambda g: g.add_node("zz"),
        "remove_other_node": lambda g: g.remove_node("d"),
    }[mutation]
    readings = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        row = graph.adj["a"]
        before = sorted(map(str, row))
        mutate(graph)
        readings.append((before, sorted(map(str, row)), len(row), sorted(map(str, row))))
    assert readings[1] == readings[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_iteration_type_is_dict_keyiterator(cls_name):
    """br-r37-c1-adjitype: the snapshot exists to preserve this type."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    assert type(iter(gfx.adj["a"])).__name__ == type(iter(gnx.adj["a"])).__name__
    assert type(iter(gfx["a"])).__name__ == type(iter(gnx["a"])).__name__


@pytest.mark.parametrize("cls_name", CLASSES)
def test_repeated_iteration_is_stable_and_matches_networkx(cls_name):
    """The snapshot is reused; it must not drift or accumulate."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    for _ in range(3):
        assert list(rfx) == list(rnx)
    gnx.add_edge("a", "zz")
    gfx.add_edge("a", "zz")
    for _ in range(3):
        assert list(rfx) == list(rnx)


NATIVE_MULTI_ROWS = [
    ("MultiGraph", "adj", "_native_adjacency_row"),
    ("MultiDiGraph", "succ", "_native_successor_row"),
    ("MultiDiGraph", "pred", "_native_predecessor_row"),
]


def _native_multi_row(lib, graph, direction, native_method, node):
    if lib is fnx:
        return getattr(graph, native_method)(node)
    return getattr(graph, direction)[node]


@pytest.mark.parametrize("cls_name,direction,native_method", NATIVE_MULTI_ROWS)
@pytest.mark.parametrize("nested", [False, True], ids=["scalar", "tuple"])
@pytest.mark.parametrize("mutation", ["add", "remove", "error"])
def test_native_multi_row_membership_allows_hash_reentry(
    cls_name, direction, native_method, nested, mutation
):
    """Hash once, outside the graph borrow, then observe the updated row.

    These deliberately call the native row rather than its Python wrapper:
    the wrapper's own guard otherwise masks a second, borrowed hash. A hash
    that raises after mutation must preserve both its first exception and
    exactly the side effects of NetworkX's single dict lookup.
    """
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        other = (1,) if nested else 1
        graph.add_nodes_from([0, other])
        edge = (other, 0) if direction == "pred" else (0, other)
        if mutation == "remove":
            graph.add_edge(*edge)
        row = _native_multi_row(lib, graph, direction, native_method, 0)
        events = []

        class Probe(int):
            def __hash__(self):
                events.append("hash")
                if mutation == "error":
                    graph.add_node(100 + len(events))
                    raise LookupError("row hash failed", len(events))
                if len(events) == 1:
                    if mutation == "add":
                        graph.add_edge(*edge)
                    else:
                        graph.remove_edge(*edge)
                return int.__hash__(self)

        probe = (Probe(1),) if nested else Probe(1)
        try:
            outcome = ("ok", probe in row)
        except Exception as exc:  # noqa: BLE001
            outcome = ("error", type(exc).__name__, exc.args)
        results.append((outcome, events, list(graph), list(graph.edges(keys=True))))
    assert results[1] == results[0]
    assert results[0][1] == ["hash"]


UNHASHED_ROW_DIRECTIONS = [
    ("Graph", False),
    ("MultiGraph", False),
    ("DiGraph", False),
    ("DiGraph", True),
    ("MultiDiGraph", False),
    ("MultiDiGraph", True),
]


def _unhashed_row_cursor(lib, graph, node, reverse):
    if lib is fnx:
        return graph._fnx_unhashed_neighbors_iter(node, reverse=reverse)
    rows = graph._pred if reverse else graph._adj
    return iter(rows[node])


def _row_edge(reverse, neighbor):
    return (neighbor, 0) if reverse else (0, neighbor)


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
@pytest.mark.parametrize("nested", [False, True], ids=["scalar", "tuple"])
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_unhashed_neighbor_cursor_does_not_hash_existing_labels(
    cls_name, reverse, nested, warm
):
    """Native algorithm row iteration must not insert original label keys."""
    for lib in (nx, fnx):
        armed = False
        events = []

        class Label(int):
            def __hash__(self):
                if armed:
                    events.append("hash")
                    raise RuntimeError("existing neighbor was hashed")
                return int.__hash__(self)

            def __eq__(self, other):
                if armed:
                    events.append("eq")
                    raise RuntimeError("existing neighbor was compared")
                return int.__eq__(self, other)

        labels = [Label(1), Label(2), Label(3)]
        if nested:
            labels = [(label,) for label in labels]
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from([0, *labels])
        graph.add_edges_from(_row_edge(reverse, label) for label in labels)
        if warm:
            assert [id(value) for value in _unhashed_row_cursor(lib, graph, 0, reverse)] == [
                id(value) for value in labels
            ]
        armed = True
        actual = list(_unhashed_row_cursor(lib, graph, 0, reverse))
        armed = False
        assert events == []
        assert [id(value) for value in actual] == [id(value) for value in labels]


def _drain_row_cursor(iterator):
    output = []
    while True:
        try:
            output.append(next(iterator))
        except StopIteration:
            return (output, "stop")
        except RuntimeError as exc:
            return (output, type(exc).__name__, exc.args)


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_unhashed_neighbor_cursor_does_not_hash_ordinary_object_labels(cls_name, reverse, warm):
    for lib in (nx, fnx):
        armed = False

        class Label:
            def __init__(self, value):
                self.value = value

            def __hash__(self):
                if armed:
                    raise RuntimeError("ordinary neighbor was hashed")
                return self.value

            def __eq__(self, other):
                if armed:
                    raise RuntimeError("ordinary neighbor was compared")
                return isinstance(other, Label) and self.value == other.value

        labels = [Label(197), Label(199)]
        graph = getattr(lib, cls_name)()
        graph.add_edges_from(_row_edge(reverse, label) for label in labels)
        if warm:
            list(_unhashed_row_cursor(lib, graph, 0, reverse))
        armed = True
        actual = list(_unhashed_row_cursor(lib, graph, 0, reverse))
        armed = False
        assert [id(value) for value in actual] == [id(value) for value in labels]


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
@pytest.mark.parametrize("label_kind", ["int_subclass", "numeric_alias"])
def test_unhashed_neighbor_cursor_retains_first_equal_display_label(cls_name, reverse, label_kind):
    """Existing dict keys retain identity; deletion permits a new first key."""
    for lib in (nx, fnx):
        class Label(int):
            pass

        first, second = (Label(1), Label(1)) if label_kind == "int_subclass" else (1.0, 1)
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from([0, 1])
        graph.add_edge(*_row_edge(reverse, first))
        iterator = _unhashed_row_cursor(lib, graph, 0, reverse)
        graph.add_edge(*_row_edge(reverse, second))
        assert next(iterator) is first
        assert next(_unhashed_row_cursor(lib, graph, 0, reverse)) is first
        if graph.is_multigraph():
            graph.remove_edge(*_row_edge(reverse, second))
            assert next(_unhashed_row_cursor(lib, graph, 0, reverse)) is first
        graph.remove_edge(*_row_edge(reverse, first))
        graph.add_edge(*_row_edge(reverse, second))
        assert next(_unhashed_row_cursor(lib, graph, 0, reverse)) is second


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
@pytest.mark.parametrize("consumed", [0, 1, 3])
@pytest.mark.parametrize(
    "mutation",
    [
        "add",
        "remove",
        "replace_unseen",
        "replace_seen",
        "remove_readd_unseen",
        "remove_readd_seen",
        "parallel",
        "unrelated",
        "remove_neighbor_node",
        "remove_edges_batch",
        "remove_owner",
        "remove_owner_readd",
        "remove_nodes_owner_first",
        "remove_nodes_owner_last",
        "clear_edges",
        "clear_edges_readd",
        "clear",
        "clear_readd",
        "bulk_plain",
        "bulk_attr",
        "bulk_weighted",
    ],
)
def test_unhashed_neighbor_cursor_preserves_live_row_mutations(
    cls_name, reverse, consumed, mutation
):
    """Compare the actual cursor, including size and same-size edits.

    Owner removal and graph clear detach rows, while clear_edges edits them
    in place. Directed predecessor and successor self-loop handling differs.
    Bulk inputs exceed the native batch threshold with only this private row
    active, so a batch cannot silently bypass its mutation hooks.
    """
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from(range(20))
        graph.add_edges_from(_row_edge(reverse, neighbor) for neighbor in (1, 2, 3, 0))
        iterator = _unhashed_row_cursor(lib, graph, 0, reverse)
        prefix = [next(iterator) for _ in range(consumed)]
        if mutation == "add":
            graph.add_edge(*_row_edge(reverse, 4))
        elif mutation == "remove":
            graph.remove_edge(*_row_edge(reverse, 2))
        elif mutation in ("replace_unseen", "replace_seen"):
            graph.remove_edge(*_row_edge(reverse, 2 if mutation.endswith("unseen") else 1))
            graph.add_edge(*_row_edge(reverse, 4))
        elif mutation in ("remove_readd_unseen", "remove_readd_seen"):
            neighbor = 2 if mutation.endswith("unseen") else 1
            graph.remove_edge(*_row_edge(reverse, neighbor))
            graph.add_edge(*_row_edge(reverse, neighbor))
        elif mutation == "parallel":
            graph.add_edge(*_row_edge(reverse, 2))
        elif mutation == "unrelated":
            graph.add_edge(7, 8)
        elif mutation == "remove_neighbor_node":
            graph.remove_node(2)
        elif mutation == "remove_edges_batch":
            graph.remove_edges_from([_row_edge(reverse, neighbor) for neighbor in (2, 3, 9)])
        elif mutation in ("remove_owner", "remove_owner_readd"):
            graph.remove_node(0)
            if mutation == "remove_owner_readd":
                graph.add_edge(*_row_edge(reverse, 9))
        elif mutation == "remove_nodes_owner_first":
            graph.remove_nodes_from([0, 2])
        elif mutation == "remove_nodes_owner_last":
            graph.remove_nodes_from([2, 0])
        elif mutation in ("clear_edges", "clear_edges_readd"):
            graph.clear_edges()
            if mutation == "clear_edges_readd":
                graph.add_edges_from(_row_edge(reverse, neighbor) for neighbor in (4, 5, 6, 0))
        elif mutation in ("clear", "clear_readd"):
            graph.clear()
            if mutation == "clear_readd":
                graph.add_edge(*_row_edge(reverse, 9))
        elif mutation == "bulk_plain":
            graph.add_edges_from([_row_edge(reverse, neighbor) for neighbor in range(4, 16)])
        elif mutation == "bulk_attr":
            graph.add_edges_from(
                [(*_row_edge(reverse, neighbor), {"weight": neighbor}) for neighbor in range(4, 16)]
            )
        elif mutation == "bulk_weighted":
            graph.add_weighted_edges_from(
                [(*_row_edge(reverse, neighbor), neighbor) for neighbor in range(4, 16)]
            )
        else:
            raise AssertionError(mutation)
        outcome = _drain_row_cursor(iterator)
        current = list(_unhashed_row_cursor(lib, graph, 0, reverse)) if 0 in graph else None
        results.append((prefix, outcome, current))
    assert results[1] == results[0]


@pytest.mark.parametrize(
    "cls_name,reverse",
    [("MultiGraph", False), ("MultiDiGraph", False), ("MultiDiGraph", True)],
)
@pytest.mark.parametrize("last_edge", [False, True])
def test_unhashed_neighbor_cursor_removes_only_last_parallel_edge(cls_name, reverse, last_edge):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        for neighbor in (1, 2, 3):
            graph.add_edge(*_row_edge(reverse, neighbor), key="first")
            graph.add_edge(*_row_edge(reverse, neighbor), key="second")
        iterator = _unhashed_row_cursor(lib, graph, 0, reverse)
        prefix = next(iterator)
        graph.remove_edge(*_row_edge(reverse, 2), key="first")
        if last_edge:
            graph.remove_edge(*_row_edge(reverse, 2), key="second")
        results.append((prefix, _drain_row_cursor(iterator)))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
def test_unhashed_neighbor_cursor_visits_label_cycles(cls_name, reverse):
    import gc
    import weakref

    class Label:
        pass

    graph = getattr(fnx, cls_name)()
    label = Label()
    label.graph = graph
    graph.add_edge(*_row_edge(reverse, label))
    iterator = _unhashed_row_cursor(fnx, graph, 0, reverse)
    assert next(iterator) is label
    reference = weakref.ref(label)
    del iterator, label, graph
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
@pytest.mark.parametrize("nested", [False, True], ids=["scalar", "tuple"])
@pytest.mark.parametrize("mutation", ["add", "remove_owner", "error"])
def test_unhashed_neighbor_cursor_binds_after_source_hash(cls_name, reverse, nested, mutation):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        owner = (0,) if nested else 0
        graph.add_nodes_from([owner, 1])
        events = []

        class Source(int):
            def __hash__(self):
                events.append("hash")
                if mutation == "error":
                    graph.add_node(100 + len(events))
                    raise LookupError("source hash failed", len(events))
                if len(events) == 1:
                    if mutation == "add":
                        graph.add_edge(*((1, owner) if reverse else (owner, 1)))
                    else:
                        graph.remove_node(owner)
                return int.__hash__(self)

        source = (Source(0),) if nested else Source(0)
        try:
            outcome = ("ok", list(_unhashed_row_cursor(lib, graph, source, reverse)))
        except Exception as exc:  # noqa: BLE001
            outcome = ("error", type(exc).__name__, exc.args)
        results.append((outcome, events, list(graph)))
    assert results[1] == results[0]
    assert results[0][1] == ["hash"]


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
def test_unhashed_neighbor_cursor_detaches_when_native_state_is_replaced(cls_name, reverse):
    """Native pickle restoration replaces outer storage, like graph clear."""
    graph = getattr(fnx, cls_name)()
    graph.add_edges_from(_row_edge(reverse, neighbor) for neighbor in (1, 2, 3))
    iterator = _unhashed_row_cursor(fnx, graph, 0, reverse)
    assert next(iterator) == 1
    replacement = getattr(fnx, cls_name)()
    replacement.add_edges_from(_row_edge(reverse, neighbor) for neighbor in (5, 4))
    graph.__setstate__(replacement.__getstate__())
    assert list(iterator) == [2, 3]
    assert list(_unhashed_row_cursor(fnx, graph, 0, reverse)) == [5, 4]
    graph.add_edge(*_row_edge(reverse, 6))
    assert list(_unhashed_row_cursor(fnx, graph, 0, reverse)) == [5, 4, 6]


@pytest.mark.parametrize("cls_name,reverse", UNHASHED_ROW_DIRECTIONS)
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_unhashed_neighbor_cursor_hashes_ordinary_owner_once(cls_name, reverse, warm):
    """Reuse the lookup hash when resolving an ordinary object owner."""
    results = []
    for lib in (nx, fnx):
        events = []

        class Owner:
            def __hash__(self):
                events.append("hash")
                return 197

        owner = Owner()
        graph = getattr(lib, cls_name)()
        graph.add_edge(*((1, owner) if reverse else (owner, 1)))
        if warm:
            list(_unhashed_row_cursor(lib, graph, owner, reverse))
        events.clear()
        values = list(_unhashed_row_cursor(lib, graph, owner, reverse))
        results.append((values, events.copy()))
    assert results[1] == results[0] == ([1], ["hash"])


@pytest.mark.parametrize("cls_name,direction,native_method", NATIVE_MULTI_ROWS)
def test_native_multi_row_binding_allows_custom_key_hash_reentry(
    cls_name, direction, native_method
):
    """Resolving an existing custom node can safely mutate graph topology.

    Generic custom-key canonicalization has separate hash-count semantics;
    this regression fixes the graph-borrow boundary and resulting row only.
    """
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        armed = False
        mutated = False

        class Node:
            def __hash__(self):
                nonlocal mutated
                if armed and not mutated:
                    mutated = True
                    graph.add_edge("during-hash", "new-neighbor")
                return 197

        node = Node()
        edge = ("neighbor", node) if direction == "pred" else (node, "neighbor")
        graph.add_edge(*edge)
        armed = True
        row = _native_multi_row(lib, graph, direction, native_method, node)
        armed = False
        results.append(
            (
                list(row),
                len(row),
                mutated,
                graph.has_edge("during-hash", "new-neighbor"),
                graph.number_of_nodes(),
            )
        )
    assert results[1] == results[0]
