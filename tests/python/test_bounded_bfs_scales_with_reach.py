"""A cutoff-bounded BFS must cost what it REACHES, not what the graph HOLDS.

br-r37-c1-dkwy7. Both single-source BFS-length kernels allocated O(V) before
knowing how far they would walk:

  * ``nodes_ordered()`` built a ``Vec<&str>`` of EVERY node name up front, in
    both the undirected and directed kernels;
  * the directed kernel also filled a ``parent: Vec<u32>`` of length V with
    ``u32::MAX``, then read it only for the nodes actually discovered;
  * both sized the result vector ``with_capacity(node_count)``.

So ``single_source_shortest_path_length(G, s, cutoff=1)`` on a 12800-node graph
paid for 12800 nodes to report 3. Measured, request held FIXED while the parent
grew 64x (200 -> 12800 nodes), fnx vs networkx:

    op                    n=200    n=1600   n=12800   fnx growth   nx growth
    sssp_len(cutoff=1)   1.0453x   1.0548x   0.2457x     4.28x        1.01x
    sssp_len(cutoff=2)   2.0092x   1.2862x   0.2761x     6.99x        0.96x

networkx is flat because its BFS carries a dict that only ever holds what it
reached. The fix walks in index space and resolves names once, at the end, for
the reached nodes only - ``get_node_name`` is an IndexMap ``get_index``, O(1),
and is called strictly fewer times than the discarded vector had entries.

WHAT THIS FILE PROTECTS. The rewrite changed how names and parents are resolved,
which is exactly the machinery behind two documented contracts, so parity is
pinned harder than speed:

  * BFS DISCOVERY ORDER of the returned mapping (br-r37-c1-k3cz4,
    br-r37-c1-bapbi) - the kernel now appends indices and maps to names in a
    second pass, so a reordering there would be invisible to any value-only
    check;
  * the NODE OBJECTS handed back must be the graph's own (br-r37-c1-6hpa9 built
    the parent channel for precisely this), so a wrong index -> name resolution
    would return equal-but-distinct keys and nothing else would notice.
"""

from __future__ import annotations

import time

import networkx as nx
import pytest

import franken_networkx as fnx

CUTOFFS = [None, 0, 1, 2, 3, 99]


def _shapes(lib):
    """Shapes that exercise the reach/hold gap and the index->name mapping."""
    path = lib.Graph()
    path.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(12)])
    path.add_node("island")  # unreachable: must never appear

    star = lib.Graph()
    star.add_edges_from([("hub", f"s{i}") for i in range(8)])

    loopy = lib.Graph()
    loopy.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
    loopy.add_edge("a", "a")  # self-loop

    ints = lib.Graph()
    ints.add_edges_from([(i, i + 1) for i in range(10)])

    tuples = lib.Graph()
    tuples.add_edges_from([((0, 0), (1, 1)), ((1, 1), (2, 2))])

    return {
        "path": (path, "n0"),
        "star": (star, "hub"),
        "loopy": (loopy, "a"),
        "ints": (ints, 0),
        "tuples": (tuples, (0, 0)),
    }


def _directed_shapes(lib):
    chain = lib.DiGraph()
    chain.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(12)])
    chain.add_edge("n5", "n0")  # a back edge, so reachability != insertion order
    chain.add_node("island")

    fan = lib.DiGraph()
    fan.add_edges_from([("root", f"c{i}") for i in range(6)])
    fan.add_edges_from([(f"c{i}", "sink") for i in range(6)])

    ints = lib.DiGraph()
    ints.add_edges_from([(i, i + 1) for i in range(10)])

    return {"chain": (chain, "n0"), "fan": (fan, "root"), "ints": (ints, 0)}


@pytest.mark.parametrize("cutoff", CUTOFFS)
@pytest.mark.parametrize("shape", ["path", "star", "loopy", "ints", "tuples"])
def test_undirected_values_and_order_match_networkx(shape, cutoff):
    got_g, source = _shapes(fnx)[shape]
    want_g, _ = _shapes(nx)[shape]
    got = fnx.single_source_shortest_path_length(got_g, source, cutoff=cutoff)
    want = nx.single_source_shortest_path_length(want_g, source, cutoff=cutoff)
    assert dict(got) == dict(want)
    # ORDER, not just contents: the kernel maps indices to names in a second pass.
    assert [str(k) for k in got] == [str(k) for k in want]


@pytest.mark.parametrize("cutoff", CUTOFFS)
@pytest.mark.parametrize("shape", ["chain", "fan", "ints"])
def test_directed_values_and_order_match_networkx(shape, cutoff):
    got_g, source = _directed_shapes(fnx)[shape]
    want_g, _ = _directed_shapes(nx)[shape]
    got = fnx.single_source_shortest_path_length(got_g, source, cutoff=cutoff)
    want = nx.single_source_shortest_path_length(want_g, source, cutoff=cutoff)
    assert dict(got) == dict(want)
    assert [str(k) for k in got] == [str(k) for k in want]


@pytest.mark.parametrize("cutoff", [None, 1, 2])
def test_returned_keys_are_the_graphs_own_node_objects(cutoff):
    """A wrong index -> name resolution yields equal-but-distinct keys."""
    graph = fnx.Graph()
    graph.add_edges_from([((0, 0), (1, 1)), ((1, 1), (2, 2))])
    identity = {n: n for n in graph.nodes()}
    for key in fnx.single_source_shortest_path_length(graph, (0, 0), cutoff=cutoff):
        assert key is identity[key], f"{key!r} is a copy, not the graph's node object"


def test_cutoff_zero_returns_only_the_source():
    graph = fnx.Graph()
    graph.add_edges_from([("a", "b"), ("b", "c")])
    assert fnx.single_source_shortest_path_length(graph, "a", cutoff=0) == {"a": 0}


def test_isolated_source_and_unreachable_nodes():
    got, want = fnx.Graph(), nx.Graph()
    for g in (got, want):
        g.add_node("lonely")
        g.add_edge("x", "y")
    for cutoff in (None, 0, 1):
        assert fnx.single_source_shortest_path_length(
            got, "lonely", cutoff=cutoff
        ) == nx.single_source_shortest_path_length(want, "lonely", cutoff=cutoff)


def test_missing_source_still_raises_like_networkx():
    graph = fnx.Graph()
    graph.add_edge("a", "b")
    with pytest.raises(fnx.NodeNotFound):
        fnx.single_source_shortest_path_length(graph, "nope", cutoff=1)


def _best(fn, reps=200, rounds=7):
    fn()
    best = None
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            fn()
        elapsed = (time.perf_counter() - start) / reps
        best = elapsed if best is None else min(best, elapsed)
    return best


def _ring(lib, n):
    graph = lib.Graph()
    graph.add_edges_from([(f"n{i}", f"n{(i + 1) % n}") for i in range(n)])
    return graph


@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); this asserts the fix and must flip to a hard assert once the "
    "extension is rebuilt",
    strict=False,
)
@pytest.mark.parametrize("cutoff", [1, 2])
def test_bounded_bfs_cost_does_not_grow_with_the_parent(cutoff):
    """networkx on the SAME host at the SAME moment is the control.

    Timing is the only instrument that can see this - the whole cost is inside
    the native kernel, so counting Python calls shows nothing. Comparing fnx's
    growth to networkx's growth rather than to an absolute bound makes the
    assertion self-calibrating: load that inflates one arm inflates both.

    THE 2.5x BOUND IS CALIBRATED, not guessed. The defect shows growth of 3.48x
    (bfs_edges), 4.28x (cutoff=1) and 6.99x (cutoff=2) against networkx's ~1.0x,
    and a fixed-cost kernel should show ~1.0x. My first draft used 6x and the
    bfs_edges case XPASSED on the broken kernel - a threshold loose enough to
    accept the bug it exists to catch. Every one of these must fail on today's
    unbuilt tree, which is the only proof they test anything.
    """
    small, large = 200, 12800
    fnx_growth = _best(
        lambda: fnx.single_source_shortest_path_length(
            _ring_cache_fnx[large], "n0", cutoff=cutoff
        )
    ) / _best(
        lambda: fnx.single_source_shortest_path_length(
            _ring_cache_fnx[small], "n0", cutoff=cutoff
        )
    )
    nx_growth = _best(
        lambda: nx.single_source_shortest_path_length(
            _ring_cache_nx[large], "n0", cutoff=cutoff
        )
    ) / _best(
        lambda: nx.single_source_shortest_path_length(
            _ring_cache_nx[small], "n0", cutoff=cutoff
        )
    )
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"cutoff={cutoff}: a {large // small}x bigger parent made fnx "
        f"{fnx_growth:.2f}x slower for the SAME request while networkx moved "
        f"{nx_growth:.2f}x; the O(V) allocation is back"
    )


_ring_cache_fnx = {n: _ring(fnx, n) for n in (200, 12800)}
_ring_cache_nx = {n: _ring(nx, n) for n in (200, 12800)}


# ---------------------------------------------------------------------------
# bfs_edges: the same defect, in three more kernels
# ---------------------------------------------------------------------------
# br-r37-c1-dkwy7. ``bfs_edges``, ``bfs_edges_directed`` and
# ``bfs_edges_directed_reverse`` each built the same whole-graph name vector.
# Measured, request fixed, parent grown 64x: fnx 3.48x growth against networkx's
# 1.02x, i.e. 1.309x of nx at n=200 falling to 0.3839x at n=12800.
#
# These kernels differ from the length kernels in one way that matters here:
# they resolve names INSIDE the walk (each emitted edge needs both endpoints,
# and the CGSE decision sink is fed the same pair), so the lookup order had to
# change too. A name is now resolved BEFORE its node is marked visited, so the
# unreachable None case cannot mark a node seen and then fail to emit it.

DEPTHS = [None, 0, 1, 2, 99]


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("shape", ["path", "star", "loopy", "ints", "tuples"])
def test_bfs_edges_undirected_sequence_matches_networkx(shape, depth):
    got_g, source = _shapes(fnx)[shape]
    want_g, _ = _shapes(nx)[shape]
    got = [(str(u), str(v)) for u, v in fnx.bfs_edges(got_g, source, depth_limit=depth)]
    want = [(str(u), str(v)) for u, v in nx.bfs_edges(want_g, source, depth_limit=depth)]
    assert got == want, f"{shape}/depth={depth}: BFS edge SEQUENCE diverged"


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("shape", ["chain", "fan", "ints"])
@pytest.mark.parametrize("reverse", [False, True])
def test_bfs_edges_directed_sequence_matches_networkx(shape, depth, reverse):
    """``reverse=True`` is a third kernel walking predecessors."""
    got_g, source = _directed_shapes(fnx)[shape]
    want_g, _ = _directed_shapes(nx)[shape]
    got = [
        (str(u), str(v))
        for u, v in fnx.bfs_edges(got_g, source, reverse=reverse, depth_limit=depth)
    ]
    want = [
        (str(u), str(v))
        for u, v in nx.bfs_edges(want_g, source, reverse=reverse, depth_limit=depth)
    ]
    assert got == want, f"{shape}/reverse={reverse}/depth={depth}: sequence diverged"


@pytest.mark.parametrize("reverse", [False, True])
def test_bfs_edges_endpoints_are_the_graphs_own_node_objects(reverse):
    """Name resolution moved; equal-but-distinct endpoints would pass a str check."""
    graph = fnx.DiGraph()
    graph.add_edges_from([((0, 0), (1, 1)), ((1, 1), (2, 2))])
    identity = {n: n for n in graph.nodes()}
    source = (0, 0) if not reverse else (2, 2)
    for u, v in fnx.bfs_edges(graph, source, reverse=reverse):
        assert u is identity[u], f"{u!r} is a copy, not the graph's node object"
        assert v is identity[v], f"{v!r} is a copy, not the graph's node object"


def test_bfs_edges_depth_zero_emits_nothing():
    graph = fnx.Graph()
    graph.add_edges_from([("a", "b"), ("b", "c")])
    assert list(fnx.bfs_edges(graph, "a", depth_limit=0)) == []


@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); flip to a hard assert once the extension is rebuilt",
    strict=False,
)
def test_bfs_edges_cost_does_not_grow_with_the_parent():
    """networkx on the same host at the same moment is the control."""
    small, large = 200, 12800
    fnx_growth = _best(
        lambda: list(fnx.bfs_edges(_ring_cache_fnx[large], "n0", depth_limit=1))
    ) / _best(lambda: list(fnx.bfs_edges(_ring_cache_fnx[small], "n0", depth_limit=1)))
    nx_growth = _best(
        lambda: list(nx.bfs_edges(_ring_cache_nx[large], "n0", depth_limit=1))
    ) / _best(lambda: list(nx.bfs_edges(_ring_cache_nx[small], "n0", depth_limit=1)))
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"a {large // small}x bigger parent made fnx bfs_edges {fnx_growth:.2f}x "
        f"slower for the SAME request while networkx moved {nx_growth:.2f}x"
    )
