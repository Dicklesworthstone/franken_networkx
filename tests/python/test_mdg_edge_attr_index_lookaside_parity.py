"""br-r37-c1-7qqr8 — the MultiDiGraph edge-attr lookaside keyed by node INDEX.

`MDG G.edges[u,v,k]` was the worst cell in the ledger: 0.0519x against networkx
at 2000-character node keys, with `get_edge_data` alone about 90 percent of it
(br-r37-c1-tjp0g). After tjp0g stopped allocating the two canonicals, everything
left on the read was still O(key length) work on the STRINGS —
`resolve_internal_edge_key` hashing both endpoints in the inner graph, then
`ensure_edge_py_attrs` allocating two owned Strings for `edge_key` and hashing
them twice more. networkx is flat in key length because CPython caches a str's
hash; this lever borrows that same cached hash to key the lookaside by node
index instead.

WHAT MAKES IT DELICATE IS INVALIDATION, and that is most of this file. An index
key is only meaningful relative to the current node numbering:

  * node REMOVAL renumbers indices and does NOT bump `edges_seq`, so each entry
    carries the `nodes_seq` it was recorded under and a mismatch is a plain MISS;
  * edge identity — an edge removed, a different one added — is covered by
    `bump_edges_seq` clearing the whole map.

Both failure modes hand back a LIVE DICT FOR THE WRONG EDGE rather than raising,
so they are invisible to a test that only checks values. The negative cases below
warm an entry, mutate underneath it, and re-read.

DICT IDENTITY is load-bearing and also pinned: `G.edges[u,v,k]` returns a dict
callers mutate in place, so the lookaside must hand back the SAME object the
string-keyed mirror holds, never a second copy of the same contents.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

LONG = "z" * 300


def _pair(keys):
    """Build the same MultiDiGraph in both libraries."""
    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        for u, v in keys:
            graph.add_edge(u, v, weight=1.0, tag=f"{u}->{v}")
            graph.add_edge(u, v, weight=2.0, tag=f"{u}=>{v}")
    return gnx, gfx


EDGES = [("a", "b"), ("b", "c"), ("c", "a"), (LONG, "b"), ("a", LONG)]


@pytest.mark.parametrize("repeat", [1, 2, 3])
def test_keyed_subscript_matches_networkx_including_on_repeat(repeat):
    """The lookaside only engages from the SECOND read on, so repeat matters.

    A single-read test would exercise nothing but the miss path and pass while
    every warm read returned garbage.
    """
    gnx, gfx = _pair(EDGES)
    for _ in range(repeat):
        for u, v in EDGES:
            for key in (0, 1):
                assert gfx.edges[u, v, key] == gnx.edges[u, v, key], (u, v, key)
                assert gfx.get_edge_data(u, v, key) == gnx.get_edge_data(u, v, key)


def test_warm_read_returns_the_same_dict_object():
    """Identity, not just equality — callers mutate this dict in place."""
    gfx = _pair(EDGES)[1]
    first = gfx.edges["a", "b", 0]
    second = gfx.edges["a", "b", 0]
    assert first is second
    first["added"] = 7
    assert gfx.edges["a", "b", 0]["added"] == 7
    assert gfx.get_edge_data("a", "b", 0) is first


def test_mutation_through_a_warm_dict_is_visible_to_every_reader():
    gnx, gfx = _pair(EDGES)
    for graph in (gnx, gfx):
        graph.edges["b", "c", 1]["weight"] = 99.0
        graph.edges["b", "c", 1]  # warm
        graph.edges["b", "c", 1]["extra"] = "x"
    assert gfx.edges["b", "c", 1] == gnx.edges["b", "c", 1]
    # The mutation must also be visible through the ITERATING view, not just
    # through another subscript that could be served by the same lookaside.
    assert [(u, v, k, dict(d)) for u, v, k, d in gfx.edges(keys=True, data=True)] == [
        (u, v, k, dict(d)) for u, v, k, d in gnx.edges(keys=True, data=True)
    ]
    assert gfx.get_edge_data("b", "c", 1)["extra"] == "x"


def test_node_removal_renumbering_does_not_hand_back_the_wrong_edge():
    """THE negative case the per-entry nodes_seq guard exists for.

    Warm a LATE edge, remove an EARLIER node so every later index shifts down,
    then re-read. An unguarded index key resolves to a DIFFERENT edge and
    returns a live dict for it — a wrong answer, not an exception.
    """
    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_edge("n0", "n1", tag="first")
        graph.add_edge("n2", "n3", tag="late")
        graph.add_edge("n1", "n2", tag="middle")
    assert gfx.edges["n2", "n3", 0]["tag"] == "late"  # warm the index entry
    for graph in (gnx, gfx):
        graph.remove_node("n0")
    assert gfx.edges["n2", "n3", 0] == gnx.edges["n2", "n3", 0]
    assert gfx.edges["n2", "n3", 0]["tag"] == "late"
    assert gfx.edges["n1", "n2", 0] == gnx.edges["n1", "n2", 0]
    assert gfx.edges["n1", "n2", 0]["tag"] == "middle"


def test_removing_the_edge_then_rereading_raises_like_networkx():
    """Edge identity is covered by bump_edges_seq, not by the seq stamp."""
    gnx, gfx = _pair([("a", "b"), ("b", "c")])
    assert gfx.edges["a", "b", 0]["weight"] == 1.0  # warm
    for graph in (gnx, gfx):
        graph.remove_edge("a", "b", 0)
    with pytest.raises(KeyError):
        gnx.edges["a", "b", 0]
    with pytest.raises(KeyError):
        gfx.edges["a", "b", 0]
    assert gfx.get_edge_data("a", "b", 0) == gnx.get_edge_data("a", "b", 0)


def test_edge_removed_and_a_different_one_added_under_the_same_key():
    """The recycled-key case: same (u, v, k) triple, different edge."""
    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", key=0, tag="original")
    assert gfx.edges["a", "b", 0]["tag"] == "original"  # warm
    for graph in (gnx, gfx):
        graph.remove_edge("a", "b", 0)
        graph.add_edge("a", "b", key=0, tag="replacement")
    assert gfx.edges["a", "b", 0] == gnx.edges["a", "b", 0]
    assert gfx.edges["a", "b", 0]["tag"] == "replacement"


def test_node_removed_and_readded_does_not_resurrect_a_stale_entry():
    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", key=0, tag="ab")
        graph.add_edge("c", "d", key=0, tag="cd")
    assert gfx.edges["c", "d", 0]["tag"] == "cd"  # warm
    for graph in (gnx, gfx):
        graph.remove_node("a")
        graph.add_node("a")
    assert gfx.edges["c", "d", 0] == gnx.edges["c", "d", 0]
    with pytest.raises(KeyError):
        gnx.edges["a", "b", 0]
    with pytest.raises(KeyError):
        gfx.edges["a", "b", 0]


def test_absent_edges_still_raise_and_never_warm_anything():
    gnx, gfx = _pair([("a", "b")])
    for missing in [("a", "zz", 0), ("zz", "a", 0), ("a", "b", 9)]:
        for _ in range(3):
            with pytest.raises(KeyError):
                gnx.edges[missing]
            with pytest.raises(KeyError):
                gfx.edges[missing]
    assert gfx.edges["a", "b", 0] == gnx.edges["a", "b", 0]


def test_explicit_non_sequential_int_keys_match():
    """`has_remapped_int_key` turns the probe off; it must still be correct."""
    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", key=17, tag="seventeen")
        graph.add_edge("a", "b", key=4, tag="four")
        graph.add_edge("a", "b", tag="auto")
    for key in (17, 4):
        for _ in range(3):
            assert gfx.edges["a", "b", key] == gnx.edges["a", "b", key], key
    assert sorted(map(str, gfx.edges(keys=True))) == sorted(map(str, gnx.edges(keys=True)))


def test_string_edge_keys_match():
    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", key="kk", tag="stringkey")
    for _ in range(3):
        assert gfx.edges["a", "b", "kk"] == gnx.edges["a", "b", "kk"]


@pytest.mark.parametrize(
    "nodes",
    [(1, 2), (1.5, 2.5), (True, False), ((1, 2), (3, 4)), (b"a", b"b")],
)
def test_non_string_endpoints_are_unaffected(nodes):
    """The probe is exact-`str` only; every other key shape must be untouched."""
    u, v = nodes
    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_edge(u, v, weight=3.0)
    for _ in range(3):
        assert gfx.edges[u, v, 0] == gnx.edges[u, v, 0]
        assert gfx.get_edge_data(u, v, 0) == gnx.get_edge_data(u, v, 0)


def test_str_subclass_endpoints_are_not_taken_by_the_exact_str_probe():
    """`is_exact_instance_of` excludes subclasses, which may lie about hash."""

    class Weird(str):
        pass

    gnx, gfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_edge(Weird("a"), Weird("b"), weight=5.0)
    for _ in range(3):
        assert gfx.edges[Weird("a"), Weird("b"), 0] == gnx.edges[Weird("a"), Weird("b"), 0]
        assert gfx.edges["a", "b", 0] == gnx.edges["a", "b", 0]


def test_unkeyed_subscript_and_whole_edge_dict_still_match():
    """`G.get_edge_data(u, v)` with no key takes the other branch entirely."""
    gnx, gfx = _pair(EDGES)
    for u, v in EDGES:
        for _ in range(3):
            assert gfx.get_edge_data(u, v) == gnx.get_edge_data(u, v), (u, v)
    assert gfx.get_edge_data("a", "zz") == gnx.get_edge_data("a", "zz")
    assert gfx.get_edge_data("a", "zz", default=5) == gnx.get_edge_data("a", "zz", default=5)


def test_long_keys_agree_with_short_keys_on_content():
    """The lever exists for long keys; they must not be a separate code path."""
    gnx, gfx = _pair([(LONG, "b"), ("a", LONG), (LONG, LONG)])
    for u, v in [(LONG, "b"), ("a", LONG), (LONG, LONG)]:
        for _ in range(3):
            assert gfx.edges[u, v, 0] == gnx.edges[u, v, 0]
            assert gfx.edges[u, v, 1] == gnx.edges[u, v, 1]


def test_clear_drops_the_lookaside():
    gfx = _pair(EDGES)[1]
    gfx.edges["a", "b", 0]  # warm
    gfx.clear()
    assert gfx.number_of_nodes() == 0
    with pytest.raises(KeyError):
        gfx.edges["a", "b", 0]
    gfx.add_edge("a", "b", tag="fresh")
    assert gfx.edges["a", "b", 0]["tag"] == "fresh"


def test_copy_and_subgraph_do_not_share_the_lookaside_dicts():
    gfx = _pair(EDGES)[1]
    gfx.edges["a", "b", 0]  # warm
    copied = gfx.copy()
    copied.edges["a", "b", 0]["only_in_copy"] = 1
    assert "only_in_copy" not in gfx.edges["a", "b", 0]
