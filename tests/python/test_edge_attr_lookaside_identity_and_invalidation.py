"""The edge-attribute lookaside must serve LIVE dicts and never a stale one.

br-r37-c1-ptiz2. The pending lever re-keys `edge_py_attrs_by_endpoint` — today a
`HashMap<String, HashMap<String, Py<PyDict>>>` — by node INDEX instead of by
canonical endpoint string. That removes two full-length string hashes per read
and two `to_owned()` allocations per materialise, which is measured as the
mechanism behind `G.edges[u,v]` growing 7.96x in node-key length while networkx
stays flat.

Re-keying by index is only safe if the cache is invalidated whenever indices can
move. THE NEGATIVE CASE: removing a node RENUMBERS indices. An index-keyed entry
that survives a removal does not merely go missing — it resolves to a DIFFERENT
edge and hands back the wrong attribute dict. That is a silent wrong-answer bug,
and no amount of "the edge is still there" testing finds it. Every removal case
below exists for that reason.

The other half of the contract is IDENTITY. The lookaside hands out live dicts,
so `G.edges[u,v]`, `G[u][v]`, `G.adj[u][v]` and `G.get_edge_data(u,v)` must all
return the SAME object, and a write through any one must be visible through the
rest. A re-keying that accidentally produced per-accessor copies would pass every
value-equality test and fail these.

These assertions hold on HEAD today and are written before the change so it
cannot land unguarded.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph"]
KEY_LENGTHS = [3, 120, 130, 400]


def _graph(class_name, length=3):
    """Node keys straddle the 128-byte canonical buffer on purpose."""
    graph = getattr(fnx, class_name)()
    names = [c * length for c in "abcdef"]
    graph.add_edge(names[0], names[1], weight=1)
    graph.add_edge(names[1], names[2], weight=2)
    graph.add_edge(names[2], names[3], weight=3)
    graph.add_edge(names[3], names[4], weight=4)
    return graph, names


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_all_accessors_return_the_same_live_dict(class_name, length):
    graph, names = _graph(class_name, length)
    u, v = names[0], names[1]

    first = graph.edges[u, v]
    assert graph[u][v] is first, "G[u][v] returned a different object"
    assert graph.adj[u][v] is first, "G.adj[u][v] returned a different object"
    assert graph.get_edge_data(u, v) is first, "get_edge_data returned a copy"

    first["written_through"] = 7
    assert graph.edges[u, v]["written_through"] == 7
    assert graph[u][v]["written_through"] == 7
    assert graph.get_edge_data(u, v)["written_through"] == 7


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_removing_a_node_does_not_leave_a_stale_entry(class_name, length):
    """THE negative case: removal renumbers indices.

    Warm the lookaside for a LATER edge, remove an EARLIER node so the indices
    behind that edge shift, then read it again. An index-keyed cache that is not
    invalidated resolves the old index pair to a different edge and returns the
    wrong attributes — the value here would come back as some other edge's
    weight rather than 4.
    """
    graph, names = _graph(class_name, length)
    late_u, late_v = names[3], names[4]

    warmed = graph.edges[late_u, late_v]
    assert warmed["weight"] == 4

    graph.remove_node(names[0])  # renumbers everything after it

    after = graph.edges[late_u, late_v]
    assert after["weight"] == 4, (
        "the surviving edge came back with the WRONG attributes after a node "
        "removal renumbered indices — a stale index-keyed lookaside entry"
    )
    assert after is warmed or dict(after) == dict(warmed)


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_removed_edge_is_gone_from_every_accessor(class_name, length):
    graph, names = _graph(class_name, length)
    u, v = names[0], names[1]
    graph.edges[u, v]  # warm

    graph.remove_edge(u, v)
    for accessor in (
        lambda: graph.edges[u, v],
        lambda: graph[u][v],
        lambda: graph.adj[u][v],
    ):
        with pytest.raises(KeyError):
            accessor()
    assert graph.get_edge_data(u, v) is None


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_readd_after_remove_is_a_fresh_dict(class_name, length):
    """A re-added edge must NOT resurrect the old attribute dict."""
    graph, names = _graph(class_name, length)
    u, v = names[0], names[1]
    original = graph.edges[u, v]
    original["marker"] = "stale"

    graph.remove_edge(u, v)
    graph.add_edge(u, v, weight=99)

    fresh = graph.edges[u, v]
    assert fresh["weight"] == 99
    assert "marker" not in fresh, (
        "a re-added edge resurrected the previous attribute dict from the "
        "lookaside"
    )


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_clear_invalidates_the_lookaside(class_name, length):
    graph, names = _graph(class_name, length)
    graph.edges[names[0], names[1]]  # warm
    graph.clear()
    graph.add_edge(names[0], names[1], weight=42)
    assert graph.edges[names[0], names[1]]["weight"] == 42


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_matches_networkx_after_the_same_mutation_sequence(class_name, length):
    """Differential: identical operations must produce identical attributes.

    Runs the removal/re-add sequence against live networkx so the expectation
    comes from the incumbent rather than from what fnx happens to do.
    """
    fnx_graph, names = _graph(class_name, length)
    nx_graph = getattr(nx, class_name)()
    for u, v, w in (
        (names[0], names[1], 1),
        (names[1], names[2], 2),
        (names[2], names[3], 3),
        (names[3], names[4], 4),
    ):
        nx_graph.add_edge(u, v, weight=w)

    for graph in (fnx_graph, nx_graph):
        graph.edges[names[3], names[4]]  # warm the fnx lookaside
        graph.remove_node(names[0])
        graph.remove_edge(names[2], names[3])
        graph.add_edge(names[2], names[3], weight=77)

    assert sorted(map(str, fnx_graph.nodes())) == sorted(map(str, nx_graph.nodes()))
    for u, v in sorted(nx_graph.edges()):
        assert dict(fnx_graph.edges[u, v]) == dict(nx_graph.edges[u, v]), (
            f"edge {u!r}-{v!r} attributes diverged after the mutation sequence"
        )


@pytest.mark.parametrize("class_name", CLASSES)
def test_lookaside_survives_many_distinct_long_keys(class_name):
    """Volume case: the lookaside must stay correct, not just fast.

    The lever's whole point is long keys, so this populates many of them past
    the buffer boundary and checks every one still maps to its own attributes.
    """
    graph = getattr(fnx, class_name)()
    pairs = [(f"u{i}".ljust(300, "x"), f"v{i}".ljust(300, "y")) for i in range(60)]
    for i, (u, v) in enumerate(pairs):
        graph.add_edge(u, v, weight=i)
    for i, (u, v) in enumerate(pairs):
        assert graph.edges[u, v]["weight"] == i, f"pair {i} returned the wrong dict"
    # Remove one node, then re-verify every surviving pair.
    graph.remove_node(pairs[0][0])
    for i, (u, v) in enumerate(pairs[1:], start=1):
        assert graph.edges[u, v]["weight"] == i, (
            f"pair {i} returned the wrong dict after a removal renumbered indices"
        )
