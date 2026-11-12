"""``edges(data=<key>)`` must keep its contract when the endpoint walk changes.

br-r37-c1-lecmc. The all-edges EdgeView materialisation splits on the parsed
data mode. ``AllData`` walks by node INDEX - it builds the index -> Python-key
vector once (br-r37-c1-2a00r) - while the data-bearing ``Attr`` /
``AttrWithDefault`` branch called ``py_node_key`` + ``py_adj_key`` per edge,
hashing each endpoint's full canonical name twice per edge. A node of degree d
was hashed about d times across its incident edges.

That is the whole measured asymmetry: on HEAD ``edges(data=True)`` stands at
2.4560x against networkx and ``edges(data=key)`` at 0.9697x, with IDENTICAL
Python-level call counts for the two spellings (20137 either way, one guard
frame per edge) - so the difference cannot be in the shim.

THIS FILE PINS THE CONTRACT, NOT THE SPEED. The change is UNBUILT (the host is
under a no-cargo disk throttle), so these tests run against the OLD path today
and must keep passing after the rebuild. What they protect:

  * VALUES AND ORDER match networkx exactly, for every class, several attribute
    keys, and several defaults - including a key absent from every edge, a key
    present on only some, and ``default`` of a type that is not the values';
  * the ENDPOINT OBJECTS are the graph's own node objects, not copies. The index
    walk hands out ``key_vec[u]`` rather than a per-edge ``py_node_key`` result,
    so identity is exactly what could regress and nothing else would notice;
  * NON-STRING NODE KEYS still round-trip, since the index walk indexes
    ``nodes_ordered()`` and a mismatch there would silently pair the wrong
    endpoints;
  * ``data=False`` and ``data=True`` are unchanged - they take different modes,
    and ``data=True`` must keep handing out the LIVE attr dict while
    ``data=key`` must keep yielding a plain value.

THE LAST ONE IS A SEMANTIC GUARD, not a style point. ``AllData`` marks the store
dirty because it hands out live dicts; the Attr branch yields values and marks
nothing (br-r37-c1-igdzi). The index walk deliberately keeps
``edge_attr_py_value`` for the value, so that difference must survive.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls):
    g = getattr(lib, cls)()
    g.add_edge("a", "b", weight=1.5, color="red")
    g.add_edge("b", "c", weight=2)
    g.add_edge("c", "d")            # no attrs at all
    g.add_edge("d", "a", color="blue")
    g.add_edge("e", "e", weight=7)  # self-loop
    g.add_node("isolated")
    return g


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("key", ["weight", "color", "absent"])
@pytest.mark.parametrize("default", [1, None, "D", 0.0])
def test_values_and_order_match_networkx(cls, key, default):
    got = list(_build(fnx, cls).edges(data=key, default=default))
    want = list(_build(nx, cls).edges(data=key, default=default))
    assert [tuple(map(str, e)) for e in got] == [tuple(map(str, e)) for e in want]


@pytest.mark.parametrize("cls", CLASSES)
def test_endpoints_are_the_graphs_own_node_objects(cls):
    """The index walk hands out key_vec[u]; identity is what could regress."""
    graph = _build(fnx, cls)
    by_value = {str(n): n for n in graph.nodes()}
    for edge in graph.edges(data="weight", default=1):
        u, v = edge[0], edge[1]
        assert u is by_value[str(u)], f"{cls}: endpoint u is a copy, not the node object"
        assert v is by_value[str(v)], f"{cls}: endpoint v is a copy, not the node object"


@pytest.mark.parametrize("cls", CLASSES)
def test_non_string_node_keys_round_trip(cls):
    """A wrong index -> name mapping would silently pair the wrong endpoints."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edge(1, 2, weight=10)
        g.add_edge(2, 3, weight=20)
        g.add_edge((4, 5), 1, weight=30)   # tuple node key
    a = [(str(u), str(v), w) for u, v, w in got.edges(data="weight", default=0)]
    b = [(str(u), str(v), w) for u, v, w in want.edges(data="weight", default=0)]
    assert a == b


@pytest.mark.parametrize("cls", CLASSES)
def test_bool_spellings_are_unchanged(cls):
    got, want = _build(fnx, cls), _build(nx, cls)
    assert [tuple(map(str, e)) for e in got.edges(data=False)] == [
        tuple(map(str, e)) for e in want.edges(data=False)
    ]
    got_data = [(str(u), str(v), dict(d)) for u, v, d in got.edges(data=True)]
    want_data = [(str(u), str(v), dict(d)) for u, v, d in want.edges(data=True)]
    assert got_data == want_data


@pytest.mark.parametrize("cls", CLASSES)
def test_data_true_hands_out_the_live_dict_and_data_key_does_not(cls):
    """The semantic difference the index walk must preserve.

    ``data=True`` yields the LIVE attr dict - writing through it changes the
    graph. ``data=key`` yields a plain value and must not expose the dict.
    """
    graph = _build(fnx, cls)
    for edge in graph.edges(data=True):
        attrs = edge[-1]
        if "weight" in attrs:
            attrs["weight"] = 999
            break
    assert any(
        w == 999 for *_rest, w in graph.edges(data="weight", default=0)
    ), f"{cls}: data=True did not hand out a live dict"

    for edge in graph.edges(data="weight", default=0):
        assert not isinstance(edge[-1], dict), f"{cls}: data=key yielded a dict"


@pytest.mark.parametrize("cls", CLASSES)
def test_empty_and_single_edge_graphs(cls):
    empty_got, empty_want = getattr(fnx, cls)(), getattr(nx, cls)()
    assert list(empty_got.edges(data="w", default=3)) == list(
        empty_want.edges(data="w", default=3)
    )
    one_got, one_want = getattr(fnx, cls)(), getattr(nx, cls)()
    one_got.add_edge("x", "y", w=5)
    one_want.add_edge("x", "y", w=5)
    assert [tuple(map(str, e)) for e in one_got.edges(data="w", default=3)] == [
        tuple(map(str, e)) for e in one_want.edges(data="w", default=3)
    ]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("key", ["weight", "color", "absent"])
@pytest.mark.parametrize("default", [1, None])
def test_nbunch_values_and_order_match_networkx(cls, key, default):
    """br-r37-c1-lecmc: the NBUNCH branch got the same index walk.

    Its filter moved onto the indexed names, so a wrong index -> name mapping
    would change WHICH edges survive, not just their endpoint objects.
    """
    got, want = _build(fnx, cls), _build(nx, cls)
    for nbunch in (["a"], ["a", "c"], ["e"], ["isolated"], ["a", "absent_node"], []):
        g_rows = [
            tuple(map(str, e)) for e in got.edges(nbunch, data=key, default=default)
        ]
        w_rows = [
            tuple(map(str, e)) for e in want.edges(nbunch, data=key, default=default)
        ]
        assert g_rows == w_rows, f"{cls}: nbunch {nbunch!r} diverged"


@pytest.mark.parametrize("cls", CLASSES)
def test_nbunch_endpoints_are_the_graphs_own_node_objects(cls):
    graph = _build(fnx, cls)
    by_value = {str(n): n for n in graph.nodes()}
    for edge in graph.edges(["a", "c"], data="weight", default=1):
        assert edge[0] is by_value[str(edge[0])]
        assert edge[1] is by_value[str(edge[1])]


@pytest.mark.parametrize("cls", CLASSES)
def test_nbunch_selfloop_and_isolated_are_handled(cls):
    """The filter is `left in set or right in set`; a self-loop hits both."""
    got, want = _build(fnx, cls), _build(nx, cls)
    for nbunch in (["e"], ["isolated"]):
        assert [tuple(map(str, x)) for x in got.edges(nbunch, data="weight", default=0)] == [
            tuple(map(str, x)) for x in want.edges(nbunch, data="weight", default=0)
        ]


@pytest.mark.parametrize("cls", CLASSES)
def test_view_tracks_mutation(cls):
    """The key_vec is built per call, so a stale one would show up here."""
    got, want = _build(fnx, cls), _build(nx, cls)
    first = [tuple(map(str, e)) for e in got.edges(data="weight", default=1)]
    assert first == [tuple(map(str, e)) for e in want.edges(data="weight", default=1)]
    for g in (got, want):
        g.add_edge("fresh", "a", weight=42)
        g.remove_node("c")
    assert [tuple(map(str, e)) for e in got.edges(data="weight", default=1)] == [
        tuple(map(str, e)) for e in want.edges(data="weight", default=1)
    ]


# br-r37-c1-h79gt: a value the attribute store cannot hold lives only in the
# edge's dict - the store keeps '(1, 2)' for a tuple, 'None' for None, a float
# for 2**70 - so a data=<key> read must take the edge's dict first. The nbunch
# DiGraph readers and every MultiDiGraph reader after add_edge read the store.
_UNSTORABLE = [(1, 2), None, [1, 2], 2**70, 10**20, b"b", frozenset({1}), 1.5]

_BUILDS = {
    "add_edge": lambda g, value: [g.add_edge(i, (i + 1) % 8, w=value) for i in range(8)],
    "dicts_one_key": lambda g, value: g.add_edges_from(
        [(i, (i + 1) % 8, {"w": value}) for i in range(8)]
        + [(i, (i + 3) % 8, {"w": value}) for i in range(8)]
    ),
    "dicts_two_keys": lambda g, value: g.add_edges_from(
        [(i, (i + 1) % 8, {"w": value, "k": i}) for i in range(8)]
        + [(i, (i + 3) % 8, {"k": i, "w": value}) for i in range(8)]
    ),
    "weighted": lambda g, value: g.add_weighted_edges_from(
        [(i, (i + 1) % 8, value) for i in range(16)], weight="w"
    ),
}


def _value_reads(graph):
    reads = {
        "edges": lambda g: list(g.edges(data="w")),
        "edges default": lambda g: list(g.edges(data="w", default=0)),
        "edges nbunch": lambda g: list(g.edges([0, 2, 4, 6], data="w")),
        "edges one node": lambda g: list(g.edges([2], data="w")),
        "for edges nbunch": lambda g: [e for e in g.edges([6, 0, 6], data="w")],
    }
    if graph.is_directed():
        reads["in_edges"] = lambda g: list(g.in_edges(data="w"))
        reads["in_edges nbunch"] = lambda g: list(g.in_edges([1, 3, 5], data="w"))
        reads["out_edges nbunch"] = lambda g: list(g.out_edges([0, 2, 4, 6], data="w"))
    if graph.is_multigraph():
        reads["edges keys nbunch"] = lambda g: list(g.edges([0, 2], keys=True, data="w"))
    return reads


def _typed(rows):
    return [(repr(row), type(row[-1]).__name__) for row in rows]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("build", sorted(_BUILDS))
def test_values_the_store_cannot_hold_come_from_the_edge_dict(cls, build):
    for value in _UNSTORABLE:
        for label, read in _value_reads(getattr(nx, cls)()).items():
            got, want = getattr(fnx, cls)(), getattr(nx, cls)()
            for g in (got, want):
                _BUILDS[build](g, value)
            assert _typed(read(got)) == _typed(read(want)), (cls, build, value, label)


def _write_routes(lib):
    def set_attrs(g, u, v):
        key = (u, v, 0) if g.is_multigraph() else (u, v)
        lib.set_edge_attributes(g, {key: 99.0}, "w")

    def through_data_true(g, u, v):
        for edge in g.edges(data=True):
            if edge[:2] == (u, v):
                edge[-1]["w"] = 99.0

    def item(g, u, v):
        return g[u][v][0] if g.is_multigraph() else g[u][v]

    def synced(g, u, v):
        # Every weighted native algorithm first folds written dicts back into
        # the store, which can leave the graph CLEAN again with the new value.
        item(g, u, v)["w"] = 99.0
        sync = getattr(g, "_fnx_sync_edge_attrs_to_inner", None)
        if sync is not None:
            sync()

    return {
        "add_edge": lambda g, u, v: g.add_edge(u, v, w=99.0),
        "subscript": lambda g, u, v: item(g, u, v).__setitem__("w", 99.0),
        "update": lambda g, u, v: item(g, u, v).update(w=99.0),
        "delete": lambda g, u, v: item(g, u, v).__delitem__("w"),
        "dict.__setitem__": lambda g, u, v: dict.__setitem__(item(g, u, v), "w", 99.0),
        "pred row": lambda g, u, v: (
            g.pred[v][u][0] if g.is_multigraph() else g.pred[v][u]
        ).__setitem__("w", 99.0),
        "set_edge_attributes": set_attrs,
        "weighted_from": lambda g, u, v: g.add_weighted_edges_from([(u, v, 99.0)], weight="w"),
        "through data=True": through_data_true,
        "synced": synced,
    }


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", sorted(_write_routes(nx)))
def test_value_reads_see_an_attribute_written_after_a_warm_read(cls, route):
    """br-r37-c1-7ye53: the value rows a read keeps must not outlive a write."""
    for label, read in _value_reads(getattr(nx, cls)()).items():
        results = []
        for lib in (fnx, nx):
            g = getattr(lib, cls)()
            g.add_weighted_edges_from([(i, (i + 1) % 8, float(i)) for i in range(8)], weight="w")
            g.add_weighted_edges_from([(i, (i + 3) % 8, i + 0.5) for i in range(8)], weight="w")
            read(g)
            read(g)
            _write_routes(lib)[route](g, 2, 3)
            results.append(_typed(read(g)))
        assert results[0] == results[1], (cls, route, label)


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_nbunch_row_is_keyed_by_the_callers_node_object(cls):
    """networkx's row node is the nbunch element itself: 1.0 or True naming
    node 1 comes back as given, whether or not the row was read before."""
    for warm in (False, True):
        results = []
        for lib in (fnx, nx):
            g = getattr(lib, cls)()
            g.add_weighted_edges_from([(1, 2, 0.5), (2, 1, 1.5), (1, 3, 2.5)], weight="w")
            if warm:
                list(g.edges(data="w"))
                list(g.in_edges(data="w"))
            results.append(
                [
                    _typed(g.edges([1.0], data="w")),
                    _typed(g.edges([True, 2], data="w")),
                    _typed(g.in_edges([1.0], data="w")),
                    _typed(g.out_edges([2.0], data="w")),
                ]
            )
        assert results[0] == results[1], (cls, warm)


_DEFAULT_STATES = {
    "batch": lambda g: g.add_edges_from([(0, 1, {"w": 1.0}), (1, 2, {}), (2, 0, {})]),
    # A tuple value keeps the edge's dict beside the store and leaves the graph
    # clean - the state in which the multigraph snapshots answer.
    "kept dict": lambda g: [g.add_edge(0, 1, w=(1, 2)), g.add_edge(1, 2), g.add_edge(2, 0, w=5)],
}


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("state", sorted(_DEFAULT_STATES))
def test_default_is_the_object_given(cls, state):
    """A remembered row must not answer for an equal default of another type
    or another object: networkx yields the default it was handed."""
    forms = [lambda g, **kw: g.edges(data="w", **kw)]
    if cls.startswith("Multi"):
        forms.append(lambda g, **kw: g.edges(keys=True, data="w", **kw))
    if cls in ("DiGraph", "MultiDiGraph"):
        forms.append(lambda g, **kw: g.in_edges(data="w", **kw))
    for index, form in enumerate(forms):
        got, want = getattr(fnx, cls)(), getattr(nx, cls)()
        for g in (got, want):
            _DEFAULT_STATES[state](g)
            list(form(g, default=0))
            list(form(g, default=0))
        assert _typed(form(got, default=0.0)) == _typed(form(want, default=0.0)), index
        marker = []
        assert [row[-1] is marker for row in form(got, default=marker)] == [
            row[-1] is marker for row in form(want, default=marker)
        ], index


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_rows_read_by_nbunch_then_whole_graph_then_after_mutation(cls):
    reads = [
        lambda g: list(g.edges([5, 1, 5], data="w")),
        lambda g: list(g.in_edges([2, 0], data="w", default=-1)),
        lambda g: list(g.edges(data="w")),
        lambda g: list(g.in_edges(data="w")),
        lambda g: list(g.out_edges([3, 8, 0], data="w")),
        lambda g: list(g.in_edges([8, 2], data="w")),
        lambda g: list(g.edges(data="w")),
        lambda g: list(g.in_edges(data="w")),
    ]
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_weighted_edges_from([(i, (i * 5 + 1) % 9, i / 2) for i in range(18)], weight="w")
    for step in range(3):
        for index, read in enumerate(reads):
            assert _typed(read(got)) == _typed(read(want)), (cls, step, index)
        for g in (got, want):
            if step == 0:
                g.add_edge(5, 7, w=70.0)
                g.add_edge(1, 5)
            elif step == 1:
                g.remove_node(2)


@pytest.mark.parametrize("cls", CLASSES)
def test_a_dict_value_is_the_edge_dicts_own(cls):
    """A nested dict is live: every value view must hand out the object the
    edge's dict holds, as networkx's `dd[key]` does."""
    graph = getattr(fnx, cls)()
    graph.add_edges_from([(0, 1, {"d": {"x": 1}}), (1, 2, {"d": {"x": 2}})])
    forms = [lambda g: g.edges(data="d"), lambda g: g.edges([0, 1], data="d")]
    if graph.is_directed():
        forms += [lambda g: g.in_edges(data="d"), lambda g: g.in_edges([1, 2], data="d")]
    for form in forms:
        for row in form(graph):
            u, v = row[0], row[1]
            held = graph[u][v][0]["d"] if graph.is_multigraph() else graph[u][v]["d"]
            assert row[-1] is held, (cls, row)
