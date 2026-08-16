"""The DiGraph edge-attr index lookaside must never serve the wrong edge.

br-r37-c1-0k6zl. ``DiGraph G.adj[u][v]`` measured 0.0804x against networkx at
2000-character node keys — the worst cell this pane measures — because only
simple ``Graph`` reaches the native row view that br-r37-c1-ptiz2 gave a cached
row index. ``DiGraph`` falls through to the PYTHON ``AtlasView``, which calls
``_fnx_edge_attr_dict_fast`` on every subscript and re-canonicalises BOTH
endpoints each time: two heap allocations and O(key length) hashing, three times
over, to fetch a dict it already holds.

The fix keys a lookaside by the endpoint INDEX pair, resolved from CPython's own
cached ``str`` hash.

THREE WAYS THAT CAN BE WRONG, and each has tests below:

1. DIRECTION. The undirected version of this lookaside sorts its endpoint pair,
   because ``u-v`` and ``v-u`` are one edge. Here they are TWO edges with two
   different attribute dicts, so a mirror that copied the sorting would serve
   one direction's attributes for the other. That only shows up when the
   endpoints sort the "wrong" way round, so the tests use reverse-sorted names
   and read both directions.

2. NODE RENUMBERING. Removing a node RENUMBERS indices. An entry that survives a
   removal does not go missing — it names a DIFFERENT edge and returns the wrong
   dict. Every entry carries the ``nodes_seq`` it was recorded under for exactly
   this reason.

3. EDGE IDENTITY. Removing an edge and adding a different one between the same
   indices must not be served from the old entry; ``bump_edges_seq`` clears the
   map.

The other half of the contract is IDENTITY: the lookaside hands out the same live
dict the string-keyed mirror does, so every accessor must return the SAME object
and a write through any one must be visible through the rest. A lookaside that
accidentally produced per-accessor copies would pass every value test and fail
these.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

# Straddle the 128-byte canonical stack buffer, and sort BOTH ways.
KEY_LENGTHS = [3, 130, 400]


def _names(length):
    """Reverse-sorted on purpose: 'z...' > 'a...'."""
    return "z" * length, "a" * length


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_both_directions_keep_their_own_attributes(length):
    """THE direction case: a sorted key would swap these."""
    u, v = _names(length)
    graph = fnx.DiGraph()
    graph.add_edge(u, v, weight="forward")
    graph.add_edge(v, u, weight="backward")

    # Warm both directions through every accessor before re-reading either.
    for _ in range(2):
        assert graph.adj[u][v]["weight"] == "forward"
        assert graph.adj[v][u]["weight"] == "backward"
        assert graph[u][v]["weight"] == "forward"
        assert graph[v][u]["weight"] == "backward"
        assert graph.get_edge_data(u, v)["weight"] == "forward"
        assert graph.get_edge_data(v, u)["weight"] == "backward"
        assert graph.succ[u][v]["weight"] == "forward"
        assert graph.pred[v][u]["weight"] == "forward"


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_one_way_edge_does_not_answer_the_reverse(length):
    """u->v present, v->u absent: the reverse must still raise / return None."""
    u, v = _names(length)
    graph = fnx.DiGraph()
    graph.add_edge(u, v, weight=1)
    reference = nx.DiGraph()
    reference.add_edge(u, v, weight=1)

    assert graph.adj[u][v] == reference.adj[u][v]
    for _ in range(2):  # warmed, then repeated
        with pytest.raises(KeyError):
            graph.adj[v][u]
        with pytest.raises(KeyError):
            graph[v][u]
        assert graph.get_edge_data(v, u) is None
        assert graph.get_edge_data(v, u, default="dflt") == "dflt"


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_node_removal_renumbering_does_not_serve_a_stale_edge(length):
    """THE renumbering case — a stale entry returns the WRONG dict, not a miss."""
    a, b, c, d = (ch * length for ch in "abcd")
    graph = fnx.DiGraph()
    graph.add_edge(a, b, weight=1)
    graph.add_edge(b, c, weight=2)
    graph.add_edge(c, d, weight=3)

    assert graph.adj[c][d]["weight"] == 3  # warm a LATE edge
    graph.remove_node(a)  # renumbers everything after it

    assert graph.adj[c][d]["weight"] == 3, (
        "a surviving edge came back with the WRONG attributes after a node "
        "removal renumbered indices — a stale index-keyed entry"
    )
    assert graph.get_edge_data(c, d)["weight"] == 3
    assert graph.adj[b][c]["weight"] == 2


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_edge_removed_and_replaced_is_not_served_stale(length):
    u, v = _names(length)
    graph = fnx.DiGraph()
    graph.add_edge(u, v, weight="old")
    graph.adj[u][v]  # warm

    graph.remove_edge(u, v)
    with pytest.raises(KeyError):
        graph.adj[u][v]
    assert graph.get_edge_data(u, v) is None

    graph.add_edge(u, v, weight="new")
    assert graph.adj[u][v]["weight"] == "new"
    assert "old" not in graph.adj[u][v].values()


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_every_accessor_returns_the_same_live_dict(length):
    u, v = _names(length)
    graph = fnx.DiGraph()
    graph.add_edge(u, v, weight=1)

    first = graph.adj[u][v]
    assert graph[u][v] is first
    assert graph.get_edge_data(u, v) is first
    assert graph.succ[u][v] is first

    first["written_through"] = 7
    assert graph[u][v]["written_through"] == 7
    assert graph.get_edge_data(u, v)["written_through"] == 7
    assert graph.adj[u][v]["written_through"] == 7


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_matches_networkx_after_a_mutation_sequence(length):
    """Differential: the expectation comes from the incumbent, not from fnx."""
    names = [ch * length for ch in "abcde"]
    graphs = {}
    for name, mod in (("fnx", fnx), ("nx", nx)):
        graph = mod.DiGraph()
        for i in range(4):
            graph.add_edge(names[i], names[i + 1], weight=i)
        graph.add_edge(names[4], names[0], weight=99)
        graphs[name] = graph

    for graph in graphs.values():
        graph.adj[names[3]][names[4]]  # warm the fnx lookaside
        graph.remove_node(names[0])
        graph.remove_edge(names[2], names[3])
        graph.add_edge(names[2], names[3], weight=77)

    assert sorted(map(str, graphs["fnx"].nodes())) == sorted(
        map(str, graphs["nx"].nodes())
    )
    for a, b in sorted(graphs["nx"].edges()):
        assert dict(graphs["fnx"].adj[a][b]) == dict(graphs["nx"].adj[a][b]), (
            f"edge {a!r}->{b!r} diverged after the mutation sequence"
        )


def test_non_string_keys_still_work():
    """The probe is gated on exact `str`; everything else takes the old path."""
    graph = fnx.DiGraph()
    reference = nx.DiGraph()
    for g in (graph, reference):
        g.add_edge(1, 2, weight="int")
        g.add_edge((3, 4), (5, 6), weight="tuple")
        g.add_edge(7.5, 8.5, weight="float")
    for a, b in ((1, 2), ((3, 4), (5, 6)), (7.5, 8.5)):
        for _ in range(2):
            assert dict(graph.adj[a][b]) == dict(reference.adj[a][b])
            assert dict(graph.get_edge_data(a, b)) == dict(reference.get_edge_data(a, b))


def test_many_distinct_long_keys_each_keep_their_own_dict():
    """Volume: the lookaside must stay correct, not merely fast."""
    graph = fnx.DiGraph()
    pairs = [(f"u{i}".ljust(300, "x"), f"v{i}".ljust(300, "y")) for i in range(60)]
    for i, (u, v) in enumerate(pairs):
        graph.add_edge(u, v, weight=i)
    for _ in range(2):
        for i, (u, v) in enumerate(pairs):
            assert graph.adj[u][v]["weight"] == i, f"pair {i} returned the wrong dict"
    graph.remove_node(pairs[0][0])
    for i, (u, v) in enumerate(pairs[1:], start=1):
        assert graph.adj[u][v]["weight"] == i, (
            f"pair {i} returned the wrong dict after a removal renumbered indices"
        )
