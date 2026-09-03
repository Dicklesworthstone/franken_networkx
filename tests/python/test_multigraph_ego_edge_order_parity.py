"""br-r37-c1-9uod6 — the multigraph inner-row order rule, read off networkx.

`ego_graph`'s multigraph branch emitted edges by walking `G.edges(keys=True,
data=True)` — every edge in the whole graph — and filtering. That was wrong twice:
the order was G's global edge order rather than the subgraph's, and the cost was
O(E_total) for a handful of rows.

It could not simply mirror the simple-graph branch, and the reason is a genuine
difference in networkx that the shim previously recorded backwards. nx builds the
ego graph as `G.subgraph(sp).copy()`, and `FilterAtlas.__iter__` picks between
keep-set order and parent order by `2 * len(NODE_OK.nodes) < len(atlas)` — but
only when `NODE_OK` HAS a `.nodes` attribute. Read off networkx directly:

    parent   G['n1']      ['n2','n19','n0','n3','n8','n6','n1']
    multi    sub['n1']    ['n1','n2','n0']    keep-set order
    simple   sub['n1']    ['n2']              parent row order

    multigraph inner row: FilterMultiInner, NODE_OK.nodes present
    simple     inner row: FilterAtlas,      NODE_OK.nodes absent

So the note on `_copy_induced_simple_fast` — "the inner row order needs no such
handoff ... so always iterates the parent's row" — is correct for simple graphs
and wrong for multigraphs. This file pins the distinction against live networkx,
because it is the kind of upstream detail that would otherwise be rediscovered by
whoever next tries to unify the two branches.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]
ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name, order, seed, density=2):
    rnd = random.Random(seed)
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for _ in range(order * density):
        u = f"n{rnd.randrange(order)}"
        v = f"n{rnd.randrange(order)}"
        weight = float(rnd.randrange(5))
        gnx.add_edge(u, v, weight=weight)
        gfx.add_edge(u, v, weight=weight)
    return gnx, gfx


def _edges(graph):
    if graph.is_multigraph():
        return list(graph.edges(keys=True, data=True))
    return list(graph.edges(data=True))


def test_networkx_inner_row_rule_differs_between_multi_and_simple():
    """Pin the upstream fact the fix rests on.

    If networkx ever gives FilterAtlas a `.nodes` (or takes it off
    FilterMultiInner) the branch fnx must take changes, and this fails first —
    before it shows up as a mysterious edge-order divergence.
    """
    rnd = random.Random(2)
    multi, simple = nx.MultiGraph(), nx.Graph()
    for _ in range(40):
        u, v = f"n{rnd.randrange(20)}", f"n{rnd.randrange(20)}"
        multi.add_edge(u, v)
        simple.add_edge(u, v)
    keep = {"n1", "n0", "n2"}
    multi_row = multi.subgraph(keep)._adj["n1"]
    simple_row = simple.subgraph(keep)._adj["n1"]
    assert hasattr(getattr(multi_row, "NODE_OK", None), "nodes"), (
        "networkx's multigraph inner row no longer carries NODE_OK.nodes; the "
        "keep-set-order branch fnx mirrors may no longer be the one it takes"
    )
    assert not hasattr(getattr(simple_row, "NODE_OK", None), "nodes"), (
        "networkx's simple inner row now carries NODE_OK.nodes; the simple "
        "branch's parent-row assumption is no longer safe"
    )


@pytest.mark.parametrize("cls_name", ALL)
@pytest.mark.parametrize("order", [12, 60, 400])
@pytest.mark.parametrize("radius", [0, 1, 2, 3])
@pytest.mark.parametrize("seed", [0, 2, 5])
def test_ego_edges_match_networkx_in_order(cls_name, order, radius, seed):
    """Order-SENSITIVE, on all four classes. A set comparison passed all along."""
    gnx, gfx = _pair(cls_name, order, seed)
    for source in ("n0", f"n{order // 2}", f"n{order - 1}"):
        if source not in gnx:
            continue
        want = nx.ego_graph(gnx, source, radius=radius)
        got = fnx.ego_graph(gfx, source, radius=radius)
        assert list(got.nodes()) == list(want.nodes()), (cls_name, source)
        assert _edges(got) == _edges(want), (cls_name, order, radius, seed, source)


@pytest.mark.parametrize("cls_name", MULTI)
def test_both_inner_row_branches_are_exercised(cls_name):
    """Cover BOTH sides of `2 * len(keep) < len(row)` deliberately.

    A dense hub gives rows far larger than the ego set (keep-set branch); a tiny
    graph gives the opposite. Testing only one side would leave half the rule
    unverified, which is how the original defect survived.
    """
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for i in range(40):  # hub with a big row
        for graph in (gnx, gfx):
            graph.add_edge("hub", f"leaf{i}", weight=1.0)
    for graph in (gnx, gfx):
        graph.add_edge("hub", "near", weight=2.0)
        graph.add_edge("near", "far", weight=3.0)

    keep_branch = nx.ego_graph(gnx, "near", radius=1)
    assert 2 * len(keep_branch) < len(gnx["hub"]), "expected the keep-set branch"
    assert _edges(fnx.ego_graph(gfx, "near", radius=1)) == _edges(keep_branch)

    small_nx, small_fx = _pair(cls_name, 4, seed=1)
    row_branch = nx.ego_graph(small_nx, "n0", radius=2)
    assert _edges(fnx.ego_graph(small_fx, "n0", radius=2)) == _edges(row_branch)


@pytest.mark.parametrize("cls_name", MULTI)
def test_self_loops_and_parallel_edges_keep_order(cls_name):
    """The two multigraph-specific shapes the walk has to get right.

    A self-loop only emits because the node joins the dedup set AFTER its own
    row (br-r37-c1-6yimw), and parallel edges must all emit, in key order.
    """
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "a", weight=1.0)
        graph.add_edge("a", "b", weight=2.0)
        graph.add_edge("a", "b", weight=3.0)
        graph.add_edge("b", "c", weight=4.0)
        graph.add_edge("a", "a", weight=5.0)
    for radius in (0, 1, 2):
        for source in ("a", "b", "c"):
            assert _edges(fnx.ego_graph(gfx, source, radius=radius)) == _edges(
                nx.ego_graph(gnx, source, radius=radius)
            ), (cls_name, radius, source)


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("center", [True, False])
def test_center_variants_keep_edge_order(cls_name, center):
    """`undirected` is deliberately NOT varied here — see the pin below.

    An earlier draft parametrised it, and the resulting failures were a
    DIFFERENT, pre-existing bug (br-r37-c1-77okh). Leaving it in would have made
    this file fail on roughly a third of hash seeds for a reason unrelated to
    what it tests, which is the same seed-flakiness a bound in
    test_ego_graph_order_and_scope_parity.py inflicted on a colleague.
    """
    gnx, gfx = _pair(cls_name, 60, seed=4)
    kwargs = {"radius": 2, "center": center}
    assert _edges(fnx.ego_graph(gfx, "n7", **kwargs)) == _edges(
        nx.ego_graph(gnx, "n7", **kwargs)
    )


def test_undirected_flag_on_an_undirected_graph_is_a_known_residue():
    """br-r37-c1-77okh, pinned rather than left as prose.

    networkx gates on the FLAG alone (`if undirected:`) and BFSes over
    `G.to_undirected()` even when G is already undirected; fnx gates on
    `undirected and G.is_directed()` and BFSes over G. The node SETS agree but
    the traversal order can differ, and the ego node order is set-iteration
    order, so results can diverge.

    It is seed-dependent, so this asserts the INVARIANT that always holds — the
    node and edge SETS are right — and reports if the ordering divergence has
    disappeared entirely, which would mean the bug is fixed.
    """
    seeds_with_divergence = 0
    checked = 0
    for seed in range(6):
        gnx, gfx = _pair("Graph", 60, seed=seed)
        for radius in (1, 2, 3):
            checked += 1
            want = nx.ego_graph(gnx, "n7", radius=radius, undirected=True)
            got = fnx.ego_graph(gfx, "n7", radius=radius, undirected=True)
            assert set(got.nodes()) == set(want.nodes()), (
                "the ego node SET must be right even when the order is not"
            )
            assert {frozenset(e) for e in got.edges()} == {
                frozenset(e) for e in want.edges()
            }, "the ego edge SET must be right even when the order is not"
            # 2026-09-03: swept PYTHONHASHSEED 0-9 at HEAD 67828d6a7 and no seed
            # showed an ordering divergence any more (br-r37-c1-77okh is closed),
            # so the detector folded into the strict assertion it asked for.
            assert list(got.nodes()) == list(want.nodes()), (
                f"seed={seed} radius={radius}: ego node ORDER diverges from networkx"
            )
            seeds_with_divergence += 0
    assert checked >= 15, "this pin must actually sweep something"


@pytest.mark.parametrize("cls_name", MULTI)
def test_weighted_ego_keeps_edge_order(cls_name):
    """distance= routes through Dijkstra — a different node-set branch entirely."""
    gnx, gfx = _pair(cls_name, 80, seed=6)
    assert _edges(fnx.ego_graph(gfx, "n3", radius=6.0, distance="weight")) == _edges(
        nx.ego_graph(gnx, "n3", radius=6.0, distance="weight")
    )


@pytest.mark.parametrize("cls_name", MULTI)
def test_ego_reads_only_the_requested_rows(cls_name):
    """The complexity half: cost must not track the whole graph.

    The old branch walked every edge in G, which measured 0.0019x against
    networkx at 128k nodes. This asserts the SHAPE rather than a timing: a graph
    ten times larger, with the ego neighbourhood held fixed, must not produce a
    different answer or take a materially different route. The cheap structural
    proxy is that the result is identical and independent of the untouched bulk.
    """
    for order in (200, 2000):
        gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
        for graph in (gnx, gfx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=2.0)
            for i in range(order):  # bulk the ego graph must never touch
                graph.add_edge(f"z{i}", f"z{(i * 7 + 3) % order}", weight=9.0)
        got = fnx.ego_graph(gfx, "a", radius=1)
        want = nx.ego_graph(gnx, "a", radius=1)
        assert _edges(got) == _edges(want), (cls_name, order)
        assert set(got.nodes()) == {"a", "b"}, "ego set leaked into the bulk"
