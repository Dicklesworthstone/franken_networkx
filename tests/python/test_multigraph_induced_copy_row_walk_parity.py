"""br-r37-c1-pzw49 — the multigraph half of the induced-copy fast path.

`MultiGraph.subgraph(keep).copy()` fell through to the generic filtered view,
which re-tests node visibility per endpoint and adds nodes and edges one call at
a time (cProfile: `_node_visible` at 10000 calls per copy of a 2000-node keep
set). Walking only the kept rows is the same work the simple-graph builder
already does.

    new/old wall clock, lower is better, N=4000, two independent runs:
      frac 0.1   0.590 / 0.623
      frac 0.5   0.652 / 0.574
      frac 0.9   0.772 / 0.817
    against networkx: 0.465 -> 1.149, 0.900 -> 1.644, 0.941 -> 1.022

WHAT MAKES THIS DELICATE is ORDER, and it is why an earlier attempt of mine was
wrongly refuted and a later draft was wrong in a different way. networkx's order
comes from two applications of the FilterAtlas rule over DIFFERENT atlases:

  * NODE order: keep-set order when ``2 * len(keep) < len(G)``, else parent
    order.
  * INNER ROW order: keep-set order when ``2 * len(keep) < len(row)``, else
    parent row order — and that branch exists for multigraphs at all only
    because ``FilterMultiInner`` carries ``NODE_OK.nodes`` where a simple
    graph's ``FilterAtlas`` does not (br-r37-c1-9uod6).

With a keep set of half the graph the row test is FALSE while with a small keep
set it is TRUE, so both branches are live in ordinary use and both are covered
below.

AND THE KEEP SET MUST BE THE FILTER'S OWN SET, never a rebuilt one: set
ITERATION order depends on insertion history, so ``{n for n in keep}`` has the
same members in a different order. A draft that rebuilt it diverged on 12 of 144
cases at two of three hash seeds and passed at the third — which is why every
order assertion here is swept across seeds in the differential test below.

MultiDiGraph is deliberately NOT on this path; see the code comment for the
measurements. Its runs disagreed in sign and it regressed at a large keep set.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
FRACTIONS = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]


def _pair(cls_name, order, seed):
    rnd = random.Random(seed)
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for _ in range(order * 4):
        u, v = f"n{rnd.randrange(order)}", f"n{rnd.randrange(order)}"
        weight = float(rnd.randrange(5))
        gnx.add_edge(u, v, weight=weight)
        gfx.add_edge(u, v, weight=weight)
    for i in range(order):
        node = f"n{i}"
        if node in gnx:
            gnx.nodes[node]["tag"] = i % 3
            gfx.nodes[node]["tag"] = i % 3
    gnx.graph["name"] = gfx.graph["name"] = "fixture"
    return gnx, gfx


def _edges(graph):
    if graph.is_multigraph():
        return list(graph.edges(keys=True, data=True))
    return list(graph.edges(data=True))


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("frac", FRACTIONS)
@pytest.mark.parametrize("seed", [0, 3, 7])
def test_induced_copy_matches_networkx_in_order(cls_name, frac, seed):
    """Node AND edge order, across keep fractions that straddle both branches.

    frac spans both sides of the node rule (2*keep < len(G)) and, because rows
    are short, keeps the row rule on its parent-order branch for large keep sets
    and its keep-set branch for small ones.
    """
    order = 30
    gnx, gfx = _pair(cls_name, order, seed)
    keep = [f"n{i}" for i in range(int(order * frac))]
    want, got = gnx.subgraph(keep).copy(), gfx.subgraph(keep).copy()
    assert list(got.nodes()) == list(want.nodes()), (cls_name, frac, seed)
    assert _edges(got) == _edges(want), (cls_name, frac, seed)
    assert dict(got.nodes(data=True)) == dict(want.nodes(data=True))
    assert dict(got.graph) == dict(want.graph)
    assert type(got).__name__ == type(want).__name__


@pytest.mark.parametrize("frac", [0.1, 0.5, 0.9])
def test_the_two_builders_agree_with_each_other(frac):
    """Force the generic path and the row walk on the SAME call.

    Comparing each to networkx separately would miss a case where both drifted
    together, and the gate's premise is that they are interchangeable.
    """
    order = 40
    graph = _pair("MultiGraph", order, seed=1)[1]
    keep = [f"n{i}" for i in range(int(order * frac))]
    view = graph.subgraph(keep)
    fast = view.copy()
    original = type(view)._copy_induced_multi_fast
    try:
        type(view)._copy_induced_multi_fast = lambda self: None
        generic = graph.subgraph(keep).copy()
    finally:
        type(view)._copy_induced_multi_fast = original
    assert list(fast.nodes()) == list(generic.nodes()), frac
    assert _edges(fast) == _edges(generic), frac


def test_multidigraph_is_deliberately_not_on_the_fast_path():
    """Pins the scope decision so it reads as measured, not forgotten.

    MultiDiGraph's before/after runs disagreed in SIGN and it regressed at a
    large keep set, so it stays on the generic builder. If someone later adopts
    it there, this failing is the prompt to bring a replicated measurement.
    """
    graph = _pair("MultiDiGraph", 20, seed=0)[1]
    view = graph.subgraph([f"n{i}" for i in range(10)])
    assert view._copy_induced_multi_fast() is None
    multi = _pair("MultiGraph", 20, seed=0)[1]
    multi_view = multi.subgraph([f"n{i}" for i in range(10)])
    assert multi_view._copy_induced_multi_fast() is not None, (
        "the fast path must actually engage for MultiGraph, or every test above "
        "is exercising the generic builder"
    )


def test_self_loops_and_parallel_edges_survive_the_row_walk():
    """The two multigraph shapes the dedup has to get right.

    A self-loop only emits because the node joins the dedup set AFTER its own
    row (br-r37-c1-6yimw); parallel edges must all emit, in key order.
    """
    gnx, gfx = nx.MultiGraph(), fnx.MultiGraph()
    for graph in (gnx, gfx):
        graph.add_edge("a", "a", weight=1.0)
        graph.add_edge("a", "b", weight=2.0)
        graph.add_edge("a", "b", weight=3.0)
        graph.add_edge("b", "c", weight=4.0)
        graph.add_edge("a", "a", weight=5.0)
        graph.add_node("iso")
    for keep in (["a"], ["a", "b"], ["a", "b", "c", "iso"], ["b", "c"]):
        want, got = gnx.subgraph(keep).copy(), gfx.subgraph(keep).copy()
        assert list(got.nodes()) == list(want.nodes()), keep
        assert _edges(got) == _edges(want), keep


def test_copy_is_a_real_copy_not_a_view():
    graph = _pair("MultiGraph", 40, seed=2)[1]
    copied = graph.subgraph([f"n{i}" for i in range(10)]).copy()
    before = sorted(map(str, copied.edges(keys=True)))
    graph.add_edge("n0", "n1", weight=99.0)
    graph.remove_node("n2")
    assert sorted(map(str, copied.edges(keys=True))) == before


def test_keep_set_containing_absent_nodes_matches_networkx():
    """nx filters the keep set against the graph; so must the row walk."""
    gnx, gfx = _pair("MultiGraph", 20, seed=5)
    keep = ["n0", "n1", "absent-1", "absent-2", "n5"]
    want, got = gnx.subgraph(keep).copy(), gfx.subgraph(keep).copy()
    assert list(got.nodes()) == list(want.nodes())
    assert _edges(got) == _edges(want)
