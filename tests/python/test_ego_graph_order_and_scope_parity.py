"""br-r37-c1-mqq4m — ego_graph node order and request-scoped reads.

Complements br-r37-c1-fauol's test_ego_graph_node_order_parity.py, which is
differential against networkx on small fixtures and stays valid; this file adds
the LARGE-graph half, where the FilterAtlas rule takes its other branch.

``nx.ego_graph`` is ``G.subgraph(sp).copy()``, so its node order is
``FilterAtlas.__iter__``'s. That rule has TWO branches:

    node_ok_shorter = 2 * len(NODE_OK.nodes) < len(atlas)
    if node_ok_shorter:  (n for n in NODE_OK.nodes if n in atlas)
    else:                (n for n in atlas if NODE_OK(n))

br-r37-c1-fauol implemented only the second, scanning the parent's nodes. For an
ego set small relative to the graph — the overwhelmingly common case, and the
only one anyone calls ego_graph for — networkx takes the FIRST branch, where
``NODE_OK.nodes`` is the SET ``show_nodes`` built. So fnx returned the wrong
ORDER (5 of 6 spot checks: nx ``['n3','n0','n171']`` vs fnx
``['n0','n3','n171']``) and, because scanning the parent is O(parent) while
networkx reads only the ego set, the whole call had the wrong COMPLEXITY too:

    N        nx us    fnx us    t_nx/t_fnx
    2000      34.0      62.5      0.544
    32000     33.6     759.5      0.044

Taking the branch networkx takes fixes both at once — 2.39x-3.36x and flat.

THE ORDER IS SET-ITERATION ORDER, which is hash dependent, so these tests run
under several PYTHONHASHSEED values in a subprocess. A single-seed test would
pass on some seeds and fail on others, which is how br-r37-c1-yioox's ordering
bug survived its first review.
"""

from __future__ import annotations

import random
import subprocess
import sys
import textwrap

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name, order, seed):
    rnd = random.Random(seed)
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for i in range(order):
        j = rnd.randrange(order)
        gnx.add_edge(f"n{i}", f"n{j}", weight=float(i % 5))
        gfx.add_edge(f"n{i}", f"n{j}", weight=float(i % 5))
    return gnx, gfx


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("order", [12, 60, 600])
@pytest.mark.parametrize("radius", [0, 1, 2])
@pytest.mark.parametrize("seed", [0, 3])
def test_ego_graph_node_order_matches_networkx(cls_name, order, radius, seed):
    """Order-SENSITIVE comparison — a set comparison would have passed all along.

    This is the assertion the fix is for, and it holds on ALL FOUR classes.
    """
    gnx, gfx = _pair(cls_name, order, seed)
    for source in ("n0", f"n{order // 2}", f"n{order - 1}"):
        want, got = (
            nx.ego_graph(gnx, source, radius=radius),
            fnx.ego_graph(gfx, source, radius=radius),
        )
        assert list(got.nodes()) == list(want.nodes()), (cls_name, order, radius, source)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("order", [12, 60, 600])
@pytest.mark.parametrize("radius", [0, 1, 2])
@pytest.mark.parametrize("seed", [0, 3])
def test_simple_graph_ego_edge_order_matches_networkx(cls_name, order, radius, seed):
    """Edge order too, on the classes where it holds today.

    Multigraphs are excluded deliberately and pinned separately below — their
    edge emission is a different, pre-existing defect.
    """
    gnx, gfx = _pair(cls_name, order, seed)
    for source in ("n0", f"n{order // 2}", f"n{order - 1}"):
        want, got = (
            nx.ego_graph(gnx, source, radius=radius),
            fnx.ego_graph(gfx, source, radius=radius),
        )
        assert list(got.edges(data=True)) == list(want.edges(data=True))


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_ego_edge_order_matches_networkx_exactly(cls_name):
    """br-r37-c1-9uod6 is FIXED; this is now a plain parity assertion.

    HISTORY, kept because it cost someone else real work. This started as a
    bounded residue pin I wrote: the multigraph branch emitted edges by walking
    every edge in G, so the order diverged, and I recorded the count with
    ``<= 6``. Two things were wrong with that.

    First, the count is PYTHONHASHSEED-dependent, so the bound failed about one
    run in five for reasons unrelated to the code — and it made the author of
    br-r37-c1-vv3sd REVERT a good lever after reading a 8/54 run as a
    regression. They widened the bound to the seed-sweep maximum and left a note.

    Second, a ``<=`` bound cannot notice the bug being FIXED. I documented that
    the pin "will need updating when br-r37-c1-9uod6 lands" but wrote an
    assertion that passes at zero, so it would have sat here indefinitely
    claiming a residue that no longer existed.

    Both problems disappear with the underlying fix: nx's FilterMultiInner takes
    the keep-set-order branch for the inner row, fnx now takes the same branch,
    and the orders agree exactly. Exact equality is both stronger and immune to
    the seed.
    """
    total = 0
    for order in (12, 60, 600):
        for seed in (0, 3):
            gnx, gfx = _pair(cls_name, order, seed)
            for radius in (0, 1, 2):
                for source in ("n0", f"n{order // 2}", f"n{order - 1}"):
                    total += 1
                    want = nx.ego_graph(gnx, source, radius=radius)
                    got = fnx.ego_graph(gfx, source, radius=radius)
                    assert list(got.nodes()) == list(want.nodes())
                    assert list(got.edges(keys=True, data=True)) == list(
                        want.edges(keys=True, data=True)
                    ), (cls_name, order, seed, radius, source)
    assert total >= 50, "this sweep must actually cover something"


@pytest.mark.parametrize("order", [40, 400])
def test_both_filteratlas_branches_are_exercised(order):
    """The rule switches at half the parent; cover BOTH sides deliberately.

    A big radius pulls in more than half the graph and flips networkx to the
    parent-order branch. If only the small-ego branch were tested, a regression
    that dropped the parent-order path entirely would go unnoticed.
    """
    gnx, gfx = _pair("Graph", order, seed=1)
    small = nx.ego_graph(gnx, "n0", radius=1)
    large = nx.ego_graph(gnx, "n0", radius=order)
    assert 2 * len(small) < len(gnx), "radius=1 should be the small-ego branch"
    assert 2 * len(large) >= len(gnx), "radius=order should be the parent branch"
    for radius in (1, order):
        assert list(fnx.ego_graph(gfx, "n0", radius=radius).nodes()) == list(
            nx.ego_graph(gnx, "n0", radius=radius).nodes()
        ), radius


@pytest.mark.parametrize("center", [True, False])
@pytest.mark.parametrize("undirected", [True, False])
def test_center_and_undirected_variants_keep_order_parity(center, undirected):
    gnx, gfx = _pair("DiGraph", 200, seed=5)
    kwargs = {"radius": 2, "center": center, "undirected": undirected}
    assert list(fnx.ego_graph(gfx, "n7", **kwargs).nodes()) == list(
        nx.ego_graph(gnx, "n7", **kwargs).nodes()
    )


def test_weighted_ego_keeps_order_parity():
    """distance= routes through Dijkstra, a different branch entirely."""
    gnx, gfx = _pair("Graph", 300, seed=2)
    assert list(fnx.ego_graph(gfx, "n3", radius=2.5, distance="weight").nodes()) == list(
        nx.ego_graph(gnx, "n3", radius=2.5, distance="weight").nodes()
    )


def test_missing_source_still_raises_node_not_found():
    """br-r37-c1-egonotfound's contract sits above the changed line."""
    gnx, gfx = _pair("Graph", 30, seed=0)
    with pytest.raises(nx.NodeNotFound):
        nx.ego_graph(gnx, "nope", radius=1)
    with pytest.raises(nx.NodeNotFound):
        fnx.ego_graph(gfx, "nope", radius=1)


_SEED_CHILD = textwrap.dedent(
    """
    import random, sys
    import networkx as nx
    import franken_networkx as fnx
    bad = 0
    total = 0
    for order in (60, 600):
        rnd = random.Random(3)
        gnx, gfx = nx.Graph(), fnx.Graph()
        for i in range(order):
            j = rnd.randrange(order)
            gnx.add_edge("n%d" % i, "n%d" % j)
            gfx.add_edge("n%d" % i, "n%d" % j)
        for _ in range(6):
            src = "n%d" % rnd.randrange(order)
            for radius in (1, 2):
                total += 1
                if list(nx.ego_graph(gnx, src, radius=radius).nodes()) != list(
                    fnx.ego_graph(gfx, src, radius=radius).nodes()
                ):
                    bad += 1
    print("%d/%d" % (bad, total))
    """
)


@pytest.mark.parametrize("hashseed", ["0", "1", "7", "42"])
def test_order_parity_holds_under_several_hash_seeds(hashseed):
    """Set-iteration order is hash dependent; one seed is not evidence.

    br-r37-c1-yioox: an ordering bug of exactly this shape passed on 2 of 5
    seeds and failed on 3. Running in a subprocess is the only way to vary
    PYTHONHASHSEED, since it is fixed at interpreter start.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _SEED_CHILD],
        capture_output=True,
        text=True,
        timeout=600,
        env={"PYTHONHASHSEED": hashseed, "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    bad, total = proc.stdout.strip().split("/")
    assert int(total) > 0, "child asserted nothing"
    assert int(bad) == 0, f"{bad}/{total} order divergences at PYTHONHASHSEED={hashseed}"
