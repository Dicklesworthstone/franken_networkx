"""A read that escapes ONE edge's dict must not cost the whole weighted store.

br-r37-c1-igdzi. ``edges_dirty`` is a single bit for the whole graph and it never
lifts, so ``G[u][v]`` — one edge, read, not written — permanently disabled every
store-backed weighted read: ``size(weight)`` measured 6.12x against networkx on a
clean graph and 0.73x after that one subscript, on a graph nobody mutated.

The fix records WHICH edges escaped instead of only THAT something did, so the
kernels answer every other edge from the store and read only the escaped ones
back out of their live dicts.

WHAT THIS FILE IS FOR, and it is not the speed. The narrow scope is a
correctness hazard before it is a win: the store may now be trusted for edges it
was previously not trusted for, and every way that trust can be misplaced ends in
a silently STALE weight rather than a crash. So the assertions below are about
answers, not gates — each one writes through an escaped dict, or renumbers the
positions the scope is keyed by, and demands the weighted read still agree with
networkx computing the same thing.

The gate probe appears exactly once, in the last test, and only to pin the
behaviour change itself.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

N = 30


def _pair(weight_of=lambda i: i + 1, weight_key="w"):
    """One fnx graph and one networkx graph with identical contents."""
    graphs = []
    for mod in (fnx, nx):
        g = mod.Graph()
        for i in range(N):
            g.add_edge("n%d" % i, "n%d" % ((i + 1) % N), **{weight_key: weight_of(i)})
        graphs.append(g)
    return graphs[0], graphs[1]


def _weighted(g, weight="w"):
    """Both weighted readers, as a comparable pair."""
    return (
        g.size(weight=weight),
        sorted((str(k), v) for k, v in g.degree(weight=weight)),
    )


# The reads that escape exactly ONE edge's live dict. Each returns that dict, so
# the caller can write through it — which is the whole reason the store cannot
# simply be trusted for that edge afterwards.
SINGLE_EDGE_ESCAPES = {
    "getitem_edge": lambda g, u, v: g[u][v],
    "adj_edge": lambda g, u, v: g.adj[u][v],
    "get_edge_data": lambda g, u, v: g.get_edge_data(u, v),
    "edges_subscript": lambda g, u, v: g.edges[(u, v)],
}


@pytest.mark.parametrize("label", sorted(SINGLE_EDGE_ESCAPES))
def test_a_write_through_an_escaped_dict_is_visible_to_both_readers(label):
    """THE soundness case: the escaped edge must be read from its live dict.

    If the narrowed scope forgot this edge, the store's stale weight would be
    summed instead and the answer would be quietly wrong — the failure mode that
    makes this change dangerous rather than merely fast.
    """
    fx, ref = _pair()
    SINGLE_EDGE_ESCAPES[label](fx, "n0", "n1")["w"] = 5000
    ref["n0"]["n1"]["w"] = 5000

    assert _weighted(fx) == _weighted(ref)


@pytest.mark.parametrize("label", sorted(SINGLE_EDGE_ESCAPES))
def test_a_float_write_through_an_escaped_dict_is_visible(label):
    """The float kernel is a separate accumulator with its own refusal rules."""
    fx, ref = _pair(weight_of=lambda i: float(i) + 0.5)
    SINGLE_EDGE_ESCAPES[label](fx, "n0", "n1")["w"] = 1234.75
    ref["n0"]["n1"]["w"] = 1234.75

    assert _weighted(fx) == _weighted(ref)


def test_deleting_the_weight_key_through_an_escaped_dict_takes_nxs_default():
    """An absent key is not an error: networkx defaults it to 1."""
    fx, ref = _pair()
    del fx["n0"]["n1"]["w"]
    del ref["n0"]["n1"]["w"]

    assert _weighted(fx) == _weighted(ref)


def test_a_non_numeric_write_through_an_escaped_dict_still_matches_networkx():
    """The kernel must refuse, not guess — networkx raises here, so must fnx."""
    fx, ref = _pair()
    fx["n0"]["n1"]["w"] = "heavy"
    ref["n0"]["n1"]["w"] = "heavy"

    for graph in (fx, ref):
        with pytest.raises(TypeError):
            graph.size(weight="w")


def test_a_self_loop_written_through_an_escaped_dict_still_counts_twice():
    """Self-loops are the one asymmetric case in the degree accumulation."""
    fx, ref = _pair()
    for g in (fx, ref):
        g.add_edge("n0", "n0", w=7)
    fx["n0"]["n0"]["w"] = 900
    ref["n0"]["n0"]["w"] = 900

    assert _weighted(fx) == _weighted(ref)


def test_a_write_after_node_removal_renumbers_and_is_still_correct():
    """The scope is keyed by POSITION, and node removal renumbers positions.

    Warm the escape on an edge, then remove an EARLIER node so every later index
    shifts down. An entry kept across that renumbering would name a different
    edge: the write below would be attributed to the wrong pair, the mutated edge
    would be summed from the store, and the total would be stale but plausible.
    The scope has to widen instead.
    """
    fx, ref = _pair()
    fx["n5"]["n6"]  # escape, recorded at the CURRENT positions
    for g in (fx, ref):
        g.remove_node("n0")  # every index above 0 shifts down by one

    fx["n5"]["n6"]["w"] = 4242
    ref["n5"]["n6"]["w"] = 4242

    assert _weighted(fx) == _weighted(ref)


def test_a_write_through_a_dict_escaped_before_a_node_was_added_is_visible():
    """Adding a node renumbers nothing today, but it does bump the stamp.

    Kept separate from removal because the two are one `bump_nodes_seq` apart and
    a future change could make either one the renumbering case.
    """
    fx, ref = _pair()
    escaped = fx["n5"]["n6"]
    for g in (fx, ref):
        g.add_node("later")

    escaped["w"] = 31337
    ref["n5"]["n6"]["w"] = 31337

    assert _weighted(fx) == _weighted(ref)


def test_two_escaped_edges_are_both_read_live():
    """One entry in the scope is the easy case; the set has to hold up too."""
    fx, ref = _pair()
    fx["n1"]["n2"]["w"] = 111
    fx["n7"]["n8"]["w"] = 222
    ref["n1"]["n2"]["w"] = 111
    ref["n7"]["n8"]["w"] = 222

    assert _weighted(fx) == _weighted(ref)


def test_a_bulk_handout_stays_conservative_and_correct():
    """`edges(data=True)` escapes every dict at once and keeps the wide scope.

    It is the case this change deliberately does NOT narrow, so it is also the
    control: the answer must still be right, by the whole-graph fallback.
    """
    fx, ref = _pair()
    for _, _, attrs in fx.edges(data=True):
        attrs["w"] = 3
    for _, _, attrs in ref.edges(data=True):
        attrs["w"] = 3

    assert _weighted(fx) == _weighted(ref)


def test_a_write_through_a_row_escaped_dict_is_visible():
    """`list(G[u].items())` escapes a whole row and is likewise not narrowed."""
    fx, ref = _pair()
    dict(fx["n3"].items())["n4"]["w"] = 808
    ref["n3"]["n4"]["w"] = 808

    assert _weighted(fx) == _weighted(ref)


def test_the_single_edge_read_no_longer_disables_the_size_scalar():
    """The behaviour change itself, stated once, on the kernel that carries it.

    `_weighted_size_fast` is the store scalar behind `size(weight)`. Before this
    change one edge subscript returned it to None for the life of the graph and
    `size(weight)` fell to the exact Python formula; now it corrects that one
    edge and keeps the scalar.

    THE DEGREE KERNEL IS DELIBERATELY NOT INCLUDED. A scope-aware version of
    `_native_weighted_degree_int_values` was built and measured SLOWER than the
    fallback it replaced (2468us clean -> 3058us with the per-edge probe, against
    a 2189us fallback), so it kept its plain gate — which is why the assertion
    below is that it still refuses. That is a real limit of this fix, not an
    oversight, and a later change that makes it pay should flip this line
    deliberately.
    """
    narrow, bulk = _pair()[0], _pair()[0]

    narrow["n0"]["n1"]
    assert narrow._weighted_size_fast("w") is not None, (
        "a single-edge escape must leave the size scalar answering"
    )
    assert narrow._native_weighted_degree_int_values("w") is None, (
        "the degree kernel is measured-slower with the scope probe and keeps "
        "its plain gate"
    )

    bulk_items = list(bulk.edges(data=True))
    assert bulk._weighted_size_fast("w") is not None, (
        "a bulk edge-data read must retain the exact live-dict weighted scalar"
    )

    # Planted negative: this is the state change the old global dirty bit could
    # not safely recover from. The fast scalar must remain enabled *and* read
    # the dict returned by the bulk view after its weight changes.
    bulk_items[0][2]["w"] = 4_321
    assert bulk._weighted_size_fast("w") == bulk.size(weight="w")
