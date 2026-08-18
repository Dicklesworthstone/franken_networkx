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
