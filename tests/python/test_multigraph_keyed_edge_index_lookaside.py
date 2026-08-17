"""The KEYED multigraph edge lookaside must never serve the wrong edge.

br-r37-c1-f3i50. ``G.edges[u, v, k]`` on a MultiGraph resolved both endpoints as
canonical strings on every call — O(node key length) — and measured 0.0754x
against networkx at 2000-character keys, the worst cell on this surface. The
index-keyed caches on the class all served the UNKEYED branch; MultiDiGraph has
had the keyed one since br-r37-c1-7qqr8 and the undirected class never got it.

The fix keys a lookaside by endpoint POSITIONS plus the internal key. Three ways
that can be wrong, one test each:

1. ORIENTATION. This graph is undirected, so ``u-v`` and ``v-u`` are ONE edge and
   must share an entry — the opposite of the directed twin, which must not sort.
   A mirror that copied the directed version's unsorted key would miss on the
   reversed read and silently fall back, or worse, collide.

2. NODE RENUMBERING. Removing a node compacts POSITIONS. An entry that survives
   does not go missing — it names a DIFFERENT edge. Every entry carries the
   ``nodes_seq`` it was recorded under for exactly this reason.

3. EDGE IDENTITY. Removing an edge and adding a different one that REUSES the
   same internal key must not be served from the old entry. The entry stores only
   ``nodes_seq``, so ``bump_edges_seq`` clears the map — unlike the sibling
   ``edge_keydict_by_index``, which carries both sequence numbers in its value
   and needs no clear. Getting that asymmetry wrong is a stale-read bug.

Key lengths straddle the 128-byte canonical stack buffer so the borrowed and
heap-spilled paths are both exercised.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

KEY_LENGTHS = [3, 130, 400]


def _graph(mod, length):
    u, v, w = ("u" * length, "v" * length, "w" * length)
    g = mod.MultiGraph()
    g.add_edge(u, v, weight="uv0")
    g.add_edge(u, v, weight="uv1")
    g.add_edge(v, w, weight="vw0")
    return g, u, v, w


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_keyed_subscript_matches_networkx(length):
    g, u, v, _w = _graph(fnx, length)
    r, ru, rv, _rw = _graph(nx, length)
    for key in (0, 1):
        assert dict(g.edges[u, v, key]) == dict(r.edges[ru, rv, key])


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_reversed_orientation_hits_the_same_edge(length):
    """THE orientation case: undirected, so the pair must be sorted."""
    g, u, v, _w = _graph(fnx, length)
    r, ru, rv, _rw = _graph(nx, length)
    for key in (0, 1):
        assert dict(g.edges[v, u, key]) == dict(r.edges[rv, ru, key])
        # warm forward, then read reversed — a per-orientation entry shows here
        g.edges[u, v, key]
        assert dict(g.edges[v, u, key]) == dict(r.edges[rv, ru, key])


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_edge_removed_and_readded_under_the_same_key(length):
    """THE edge-identity case: same internal key, different edge."""
    g, u, v, _w = _graph(fnx, length)
    assert g.edges[u, v, 0]["weight"] == "uv0"  # warm the entry

    g.remove_edge(u, v, 0)
    g.add_edge(u, v, key=0, weight="fresh")

    assert g.edges[u, v, 0]["weight"] == "fresh", (
        "a re-added edge reusing internal key 0 was served from the stale entry"
    )


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_node_removal_renumbering_does_not_serve_a_stale_edge(length):
    """THE renumbering case — a stale entry returns the WRONG edge, not a miss."""
    g, u, v, w = _graph(fnx, length)
    r, ru, rv, rw = _graph(nx, length)
    assert g.edges[u, v, 1]["weight"] == "uv1"  # warm before the shift

    g.remove_node(w)
    r.remove_node(rw)

    assert g.edges[u, v, 1]["weight"] == "uv1", (
        "the surviving edge came back wrong after a node removal renumbered "
        "positions — a stale index-keyed entry"
    )
    assert dict(g.edges[u, v, 0]) == dict(r.edges[ru, rv, 0])
    assert g.number_of_edges() == r.number_of_edges()


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_missing_key_still_raises_networkx_keyerror(length):
    g, u, v, _w = _graph(fnx, length)
    r, ru, rv, _rw = _graph(nx, length)
    g.edges[u, v, 0]  # warm, so the miss goes through the populated map
    with pytest.raises(KeyError) as got:
        g.edges[u, v, 99]
    with pytest.raises(KeyError) as want:
        r.edges[ru, rv, 99]
    assert got.value.args == want.value.args


@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_keyed_read_is_the_same_live_dict_as_get_edge_data(length):
    g, u, v, _w = _graph(fnx, length)
    assert g.edges[u, v, 0] is g.get_edge_data(u, v, 0)
    g.edges[u, v, 0]["written"] = 5
    assert g.get_edge_data(u, v, 0)["written"] == 5
    assert g[u][v][0]["written"] == 5


def test_custom_public_keys_bypass_the_int_gate():
    """The probe is gated on an exact int public key equal to the internal one.

    A graph with explicit non-int keys sets `has_remapped_int_key`, which must
    disable the fast path entirely rather than mis-resolve.
    """
    g, r = fnx.MultiGraph(), nx.MultiGraph()
    for graph in (g, r):
        graph.add_edge("a", "b", key="alpha", weight=1)
        graph.add_edge("a", "b", key=7, weight=2)
    assert dict(g.edges["a", "b", "alpha"]) == dict(r.edges["a", "b", "alpha"])
    assert dict(g.edges["a", "b", 7]) == dict(r.edges["a", "b", 7])
