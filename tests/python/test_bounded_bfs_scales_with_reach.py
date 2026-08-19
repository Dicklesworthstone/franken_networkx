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


# ---------------------------------------------------------------------------
# single_source_shortest_path: the same defect, one layer up
# ---------------------------------------------------------------------------
# br-r37-c1-dkwy7. The path kernels were ALREADY index-space, yet still sized
# three structures to the whole graph. The dominant term was a
# ``vec![None; n]`` predecessor tree - ``Option<usize>`` is 16 bytes, so a
# cutoff=1 query on 12800 nodes wrote 200KB to report three paths. Measured:
# undirected 12.11x growth vs networkx's 1.00x (1.1706x -> 0.0969x), directed
# 4.88x (0.8180x -> 0.1696x).
#
# The predecessor array was removed outright rather than made sparse: a node's
# parent is always discovered BEFORE it, so its POSITION in the discovery vector
# is known at push time. Reconstruction is then index arithmetic over a vector
# sized to the reach. That rewrote the path-building loop, so these tests pin
# PATH CONTENTS, not just which nodes were reached.


@pytest.mark.parametrize("cutoff", CUTOFFS)
@pytest.mark.parametrize("shape", ["path", "star", "loopy", "ints", "tuples"])
def test_sssp_paths_undirected_match_networkx(shape, cutoff):
    got_g, source = _shapes(fnx)[shape]
    want_g, _ = _shapes(nx)[shape]
    got = fnx.single_source_shortest_path(got_g, source, cutoff=cutoff)
    want = nx.single_source_shortest_path(want_g, source, cutoff=cutoff)
    assert {str(k): [str(n) for n in v] for k, v in got.items()} == {
        str(k): [str(n) for n in v] for k, v in want.items()
    }
    assert [str(k) for k in got] == [str(k) for k in want], "discovery order diverged"


@pytest.mark.parametrize("cutoff", CUTOFFS)
@pytest.mark.parametrize("shape", ["chain", "fan", "ints"])
def test_sssp_paths_directed_match_networkx(shape, cutoff):
    got_g, source = _directed_shapes(fnx)[shape]
    want_g, _ = _directed_shapes(nx)[shape]
    got = fnx.single_source_shortest_path(got_g, source, cutoff=cutoff)
    want = nx.single_source_shortest_path(want_g, source, cutoff=cutoff)
    assert {str(k): [str(n) for n in v] for k, v in got.items()} == {
        str(k): [str(n) for n in v] for k, v in want.items()
    }
    assert [str(k) for k in got] == [str(k) for k in want], "discovery order diverged"


def test_sssp_paths_are_real_walks_of_the_graph():
    """Position-based reconstruction could mis-link a parent and still look sane.

    Every consecutive pair in every returned path must be an actual edge, and
    every path must start at the source and end at its key. A wrong parent
    position yields a well-formed list that is not a path in the graph.
    """
    graph = fnx.Graph()
    graph.add_edges_from(
        [("a", "b"), ("b", "c"), ("c", "d"), ("a", "e"), ("e", "d"), ("d", "f")]
    )
    for cutoff in (None, 1, 2, 3):
        for target, path in fnx.single_source_shortest_path(
            graph, "a", cutoff=cutoff
        ).items():
            assert path[0] == "a", f"path to {target} does not start at the source"
            assert path[-1] == target, f"path to {target} does not end at {target}"
            for left, right in zip(path, path[1:]):
                assert graph.has_edge(left, right), (
                    f"path to {target} traverses {left}->{right}, which is not an edge"
                )


@pytest.mark.parametrize("cutoff", [1, 2])
def test_sssp_path_depth_never_exceeds_the_cutoff(cutoff):
    graph = fnx.Graph()
    graph.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(20)])
    for _target, path in fnx.single_source_shortest_path(
        graph, "n0", cutoff=cutoff
    ).items():
        assert len(path) - 1 <= cutoff, f"path {path} is deeper than cutoff {cutoff}"


@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); flip to a hard assert once the extension is rebuilt",
    strict=False,
)
def test_sssp_path_cost_does_not_grow_with_the_parent():
    small, large = 200, 12800
    fnx_growth = _best(
        lambda: fnx.single_source_shortest_path(_ring_cache_fnx[large], "n0", cutoff=1)
    ) / _best(
        lambda: fnx.single_source_shortest_path(_ring_cache_fnx[small], "n0", cutoff=1)
    )
    nx_growth = _best(
        lambda: nx.single_source_shortest_path(_ring_cache_nx[large], "n0", cutoff=1)
    ) / _best(
        lambda: nx.single_source_shortest_path(_ring_cache_nx[small], "n0", cutoff=1)
    )
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"a {large // small}x bigger parent made fnx single_source_shortest_path "
        f"{fnx_growth:.2f}x slower for the SAME request while networkx moved "
        f"{nx_growth:.2f}x"
    )


# ---------------------------------------------------------------------------
# dfs_edges: the bfs_edges defect, in the depth-first pair
# ---------------------------------------------------------------------------
# br-r37-c1-dkwy7. Measured 5.17x growth undirected and 5.28x directed against
# networkx's 1.00x - 1.1058x of nx at n=200 down to 0.2130x at n=12800. Same
# whole-graph name vector, plus stack and result vectors reserved for the whole
# graph on a bounded walk.
#
# DFS is order-sensitive in a way BFS is not: nx pushes neighbours in REVERSE so
# they pop in insertion order, and it always visits immediate neighbours at
# depth 1 regardless of depth_limit. These tests pin the emitted sequence, which
# is where a mis-resolved parent or a reordered push would show.


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("shape", ["path", "star", "loopy", "ints", "tuples"])
def test_dfs_edges_undirected_sequence_matches_networkx(shape, depth):
    got_g, source = _shapes(fnx)[shape]
    want_g, _ = _shapes(nx)[shape]
    got = [(str(u), str(v)) for u, v in fnx.dfs_edges(got_g, source, depth_limit=depth)]
    want = [(str(u), str(v)) for u, v in nx.dfs_edges(want_g, source, depth_limit=depth)]
    assert got == want, f"{shape}/depth={depth}: DFS edge SEQUENCE diverged"


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("shape", ["chain", "fan", "ints"])
def test_dfs_edges_directed_sequence_matches_networkx(shape, depth):
    got_g, source = _directed_shapes(fnx)[shape]
    want_g, _ = _directed_shapes(nx)[shape]
    got = [(str(u), str(v)) for u, v in fnx.dfs_edges(got_g, source, depth_limit=depth)]
    want = [(str(u), str(v)) for u, v in nx.dfs_edges(want_g, source, depth_limit=depth)]
    assert got == want, f"{shape}/depth={depth}: directed DFS sequence diverged"


def test_dfs_edges_branching_order_is_networkxs():
    """A wide branching node is where a reordered push would surface."""
    got, want = fnx.Graph(), nx.Graph()
    for g in (got, want):
        g.add_edges_from([("r", "a"), ("r", "b"), ("r", "c")])
        g.add_edges_from([("a", "a1"), ("a", "a2"), ("b", "b1"), ("c", "c1")])
    for depth in (None, 1, 2, 3):
        assert [
            (str(u), str(v)) for u, v in fnx.dfs_edges(got, "r", depth_limit=depth)
        ] == [(str(u), str(v)) for u, v in nx.dfs_edges(want, "r", depth_limit=depth)]


def test_dfs_edges_endpoints_are_the_graphs_own_node_objects():
    graph = fnx.Graph()
    graph.add_edges_from([((0, 0), (1, 1)), ((1, 1), (2, 2))])
    identity = {n: n for n in graph.nodes()}
    for u, v in fnx.dfs_edges(graph, (0, 0)):
        assert u is identity[u] and v is identity[v]


@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); flip to a hard assert once the extension is rebuilt",
    strict=False,
)
def test_dfs_edges_cost_does_not_grow_with_the_parent():
    small, large = 200, 12800
    fnx_growth = _best(
        lambda: list(fnx.dfs_edges(_ring_cache_fnx[large], "n0", depth_limit=1))
    ) / _best(lambda: list(fnx.dfs_edges(_ring_cache_fnx[small], "n0", depth_limit=1)))
    nx_growth = _best(
        lambda: list(nx.dfs_edges(_ring_cache_nx[large], "n0", depth_limit=1))
    ) / _best(lambda: list(nx.dfs_edges(_ring_cache_nx[small], "n0", depth_limit=1)))
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"a {large // small}x bigger parent made fnx dfs_edges {fnx_growth:.2f}x "
        f"slower for the SAME request while networkx moved {nx_growth:.2f}x"
    )


# ---------------------------------------------------------------------------
# dfs_postorder_nodes: the last O(V) term is the name vector alone
# ---------------------------------------------------------------------------
# br-r37-c1-dkwy7. Here `visited` is one calloc and both output vectors already
# started empty, so the whole-graph name vector was the entire defect: 8.39x
# growth against networkx's 0.99x, 1.9093x of nx down to 0.2244x.
#
# The postorder contract is subtle and worth pinning precisely: networkx emits a
# reverse-depth_limit event for cutoff nodes, so a node at exactly the depth
# limit appears in PREORDER but NOT in postorder - except the root, which still
# closes normally. That asymmetry lives in the loop whose emit site just moved.


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("shape", ["path", "star", "loopy", "ints", "tuples"])
def test_dfs_postorder_undirected_matches_networkx(shape, depth):
    got_g, source = _shapes(fnx)[shape]
    want_g, _ = _shapes(nx)[shape]
    got = [str(n) for n in fnx.dfs_postorder_nodes(got_g, source, depth_limit=depth)]
    want = [str(n) for n in nx.dfs_postorder_nodes(want_g, source, depth_limit=depth)]
    assert got == want, f"{shape}/depth={depth}: postorder sequence diverged"


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("shape", ["chain", "fan", "ints"])
def test_dfs_postorder_directed_matches_networkx(shape, depth):
    got_g, source = _directed_shapes(fnx)[shape]
    want_g, _ = _directed_shapes(nx)[shape]
    got = [str(n) for n in fnx.dfs_postorder_nodes(got_g, source, depth_limit=depth)]
    want = [str(n) for n in nx.dfs_postorder_nodes(want_g, source, depth_limit=depth)]
    assert got == want, f"{shape}/depth={depth}: directed postorder diverged"


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_dfs_postorder_cutoff_node_omission_matches_networkx(depth):
    """The reverse-depth_limit asymmetry: cutoff nodes are omitted, the root is not."""
    got, want = fnx.Graph(), nx.Graph()
    for g in (got, want):
        g.add_edges_from([("r", "a"), ("a", "b"), ("b", "c"), ("r", "d"), ("d", "e")])
    got_seq = [str(n) for n in fnx.dfs_postorder_nodes(got, "r", depth_limit=depth)]
    want_seq = [str(n) for n in nx.dfs_postorder_nodes(want, "r", depth_limit=depth)]
    assert got_seq == want_seq
    assert "r" in got_seq, "the root must still close with a normal reverse event"


@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); flip to a hard assert once the extension is rebuilt",
    strict=False,
)
def test_dfs_postorder_cost_does_not_grow_with_the_parent():
    small, large = 200, 12800
    fnx_growth = _best(
        lambda: list(
            fnx.dfs_postorder_nodes(_ring_cache_fnx[large], "n0", depth_limit=1)
        )
    ) / _best(
        lambda: list(
            fnx.dfs_postorder_nodes(_ring_cache_fnx[small], "n0", depth_limit=1)
        )
    )
    nx_growth = _best(
        lambda: list(nx.dfs_postorder_nodes(_ring_cache_nx[large], "n0", depth_limit=1))
    ) / _best(
        lambda: list(nx.dfs_postorder_nodes(_ring_cache_nx[small], "n0", depth_limit=1))
    )
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"a {large // small}x bigger parent made fnx dfs_postorder_nodes "
        f"{fnx_growth:.2f}x slower for the SAME request while networkx moved "
        f"{nx_growth:.2f}x"
    )


# ---------------------------------------------------------------------------
# bidirectional_shortest_path: the algorithm whose whole point is stopping early
# ---------------------------------------------------------------------------
# br-r37-c1-dkwy7. Two-way BFS meets in the middle and touches a neighbourhood,
# not a graph - yet it allocated two whole-graph parent arrays before the first
# expansion (Option<usize> is 16 bytes, so 32 bytes per node in the graph to
# answer a query that meets in two hops). Measured 9.41x growth against
# networkx's 0.99x: 2.0786x of nx at n=200 down to 0.2185x at n=12800.
#
# The parent maps are sparse now; the two `seen` marks stay dense because they
# are probed on every neighbour of every expansion. Reconstruction reads the
# parent maps by node index, and a missing key means exactly what None meant, so
# these tests pin the RECONSTRUCTED PATH rather than merely its endpoints.
#
# NOTE: the live binding is bidirectional_shortest_path_index_meta, NOT the
# `pub fn bidirectional_shortest_path` in the same crate - that one still builds
# nodes_ordered() and is off the Python path entirely.


def _bidir_shapes(lib):
    grid = lib.Graph()
    for i in range(5):
        for j in range(5):
            if i < 4:
                grid.add_edge((i, j), (i + 1, j))
            if j < 4:
                grid.add_edge((i, j), (i, j + 1))
    two_routes = lib.Graph()
    two_routes.add_edges_from(
        [("s", "a"), ("a", "t"), ("s", "b"), ("b", "c"), ("c", "t")]
    )
    disconnected = lib.Graph()
    disconnected.add_edges_from([("x", "y"), ("p", "q")])
    return {"grid": grid, "two_routes": two_routes, "disconnected": disconnected}


@pytest.mark.parametrize(
    "shape,src,dst",
    [
        ("grid", (0, 0), (4, 4)),
        ("grid", (0, 0), (0, 0)),
        ("grid", (2, 2), (2, 3)),
        ("two_routes", "s", "t"),
        ("two_routes", "s", "s"),
    ],
)
def test_bidirectional_path_matches_networkx(shape, src, dst):
    got = fnx.bidirectional_shortest_path(_bidir_shapes(fnx)[shape], src, dst)
    want = nx.bidirectional_shortest_path(_bidir_shapes(nx)[shape], src, dst)
    assert [str(n) for n in got] == [str(n) for n in want]


def test_bidirectional_path_is_a_real_walk_of_the_graph():
    """Sparse parents are read by index; a wrong lookup yields a plausible list.

    Deliberately NOT an object-identity test. The other kernels here do assert
    identity, but bidirectional_shortest_path cannot: measured on a tuple-keyed
    grid, NETWORKX ITSELF returns a mix of the graph's own node objects and
    equal-but-distinct ones ([False, True, False, False, False] over a 5-node
    path), so identity is not a contract either library offers on this call and
    asserting it would pin an accident. What IS checkable is that the path is a
    genuine walk - a mis-read parent map produces a well-formed list of real
    nodes that is not connected end to end.
    """
    graph = _bidir_shapes(fnx)["grid"]
    path = fnx.bidirectional_shortest_path(graph, (0, 0), (4, 4))
    assert path[0] == (0, 0) and path[-1] == (4, 4)
    assert len(path) == len(set(path)), "the path revisits a node"
    for left, right in zip(path, path[1:]):
        assert graph.has_edge(left, right), f"{left}->{right} is not an edge"
    want = nx.bidirectional_shortest_path(_bidir_shapes(nx)["grid"], (0, 0), (4, 4))
    assert len(path) == len(want), "path length differs from networkx's"


def test_bidirectional_no_path_still_raises_like_networkx():
    got, want = _bidir_shapes(fnx)["disconnected"], _bidir_shapes(nx)["disconnected"]
    with pytest.raises(Exception) as got_exc:
        fnx.bidirectional_shortest_path(got, "x", "q")
    with pytest.raises(Exception) as want_exc:
        nx.bidirectional_shortest_path(want, "x", "q")
    assert type(got_exc.value).__name__ == type(want_exc.value).__name__


def test_bidirectional_directed_respects_orientation():
    got, want = fnx.DiGraph(), nx.DiGraph()
    for g in (got, want):
        g.add_edges_from([("a", "b"), ("b", "c"), ("c", "d")])
    assert [str(n) for n in fnx.bidirectional_shortest_path(got, "a", "d")] == [
        str(n) for n in nx.bidirectional_shortest_path(want, "a", "d")
    ]
    with pytest.raises(Exception):
        fnx.bidirectional_shortest_path(got, "d", "a")


@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); flip to a hard assert once the extension is rebuilt",
    strict=False,
)
def test_bidirectional_cost_does_not_grow_with_the_parent():
    small, large = 200, 12800
    fnx_growth = _best(
        lambda: fnx.bidirectional_shortest_path(_ring_cache_fnx[large], "n0", "n2")
    ) / _best(
        lambda: fnx.bidirectional_shortest_path(_ring_cache_fnx[small], "n0", "n2")
    )
    nx_growth = _best(
        lambda: nx.bidirectional_shortest_path(_ring_cache_nx[large], "n0", "n2")
    ) / _best(lambda: nx.bidirectional_shortest_path(_ring_cache_nx[small], "n0", "n2"))
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"a {large // small}x bigger parent made fnx bidirectional_shortest_path "
        f"{fnx_growth:.2f}x slower for a two-hop query while networkx moved "
        f"{nx_growth:.2f}x"
    )


# ---------------------------------------------------------------------------
# The MULTIGRAPH mirrors, which were far worse than the simple-graph originals
# ---------------------------------------------------------------------------
# br-r37-c1-dkwy7. The multigraph bidirectional helpers built a HashMap of EVERY
# node name -> index on every call - hashing the whole node set before a two-hop
# query could start - on top of the same dense parent arrays. Measured growth
# 200 -> 12800 nodes, against networkx's 0.98x:
#
#     MultiGraph    bidirectional_shortest_path   67.39x   0.6388x -> 0.0093x
#     MultiDiGraph  bidirectional_shortest_path   68.01x   0.5988x -> 0.0088x
#     MultiGraph    single_source_shortest_path   44.22x   0.7135x -> 0.0158x
#     MultiDiGraph  single_source_shortest_path   81.30x   0.3236x -> 0.0040x
#
# The graph classes already carry the map the helpers rebuilt: get_node_index is
# an IndexMap lookup, so a neighbour costs the same single hash it cost through
# the temporary, without the O(V) build in front of it. Parallel edges are the
# thing to pin here - a multigraph neighbour row repeats a node once per parallel
# edge, so a per-neighbour index lookup runs more often than the old map build
# did, and any divergence would show up as a duplicated or reordered path node.

MULTI = ["MultiGraph", "MultiDiGraph"]


def _multi_with_parallel_edges(lib, cls):
    graph = getattr(lib, cls)()
    graph.add_edge("s", "a")
    graph.add_edge("s", "a")          # parallel
    graph.add_edge("a", "t")
    graph.add_edge("s", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", "t")
    graph.add_edge("t", "t")          # self-loop
    return graph


@pytest.mark.parametrize("cls", MULTI)
def test_multigraph_bidirectional_path_matches_networkx(cls):
    got = _multi_with_parallel_edges(fnx, cls)
    want = _multi_with_parallel_edges(nx, cls)
    for src, dst in (("s", "t"), ("s", "s"), ("s", "a"), ("a", "t")):
        assert [str(n) for n in fnx.bidirectional_shortest_path(got, src, dst)] == [
            str(n) for n in nx.bidirectional_shortest_path(want, src, dst)
        ], f"{cls}: {src}->{dst} diverged"


@pytest.mark.parametrize("cls", MULTI)
def test_multigraph_bidirectional_path_is_a_real_walk(cls):
    graph = _multi_with_parallel_edges(fnx, cls)
    path = fnx.bidirectional_shortest_path(graph, "s", "t")
    assert len(path) == len(set(path)), f"{cls}: parallel edges duplicated a node"
    for left, right in zip(path, path[1:]):
        assert graph.has_edge(left, right), f"{cls}: {left}->{right} is not an edge"


@pytest.mark.parametrize("cls", MULTI)
def test_multigraph_bounded_traversals_match_networkx(cls):
    """The other multigraph mirrors on this bead, pinned at the public API."""
    got = _multi_with_parallel_edges(fnx, cls)
    want = _multi_with_parallel_edges(nx, cls)
    for cutoff in (None, 0, 1, 2):
        assert dict(
            fnx.single_source_shortest_path_length(got, "s", cutoff=cutoff)
        ) == dict(nx.single_source_shortest_path_length(want, "s", cutoff=cutoff))
        assert {
            str(k): [str(x) for x in v]
            for k, v in fnx.single_source_shortest_path(got, "s", cutoff=cutoff).items()
        } == {
            str(k): [str(x) for x in v]
            for k, v in nx.single_source_shortest_path(want, "s", cutoff=cutoff).items()
        }
        assert [
            (str(u), str(v))
            for u, v in fnx.bfs_edges(got, "s", depth_limit=cutoff)
        ] == [
            (str(u), str(v)) for u, v in nx.bfs_edges(want, "s", depth_limit=cutoff)
        ]


@pytest.mark.parametrize("cls", MULTI)
@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); flip to a hard assert once the extension is rebuilt",
    strict=False,
)
def test_multigraph_bidirectional_cost_does_not_grow_with_the_parent(cls):
    small, large = 200, 12800
    rings = {
        n: (_multi_ring(fnx, cls, n), _multi_ring(nx, cls, n)) for n in (small, large)
    }
    fnx_growth = _best(
        lambda: fnx.bidirectional_shortest_path(rings[large][0], "n0", "n2")
    ) / _best(lambda: fnx.bidirectional_shortest_path(rings[small][0], "n0", "n2"))
    nx_growth = _best(
        lambda: nx.bidirectional_shortest_path(rings[large][1], "n0", "n2")
    ) / _best(lambda: nx.bidirectional_shortest_path(rings[small][1], "n0", "n2"))
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"{cls}: a {large // small}x bigger parent made fnx {fnx_growth:.2f}x "
        f"slower for a two-hop query while networkx moved {nx_growth:.2f}x"
    )


def _multi_ring(lib, cls, n):
    graph = getattr(lib, cls)()
    graph.add_edges_from([(f"n{i}", f"n{(i + 1) % n}") for i in range(n)])
    return graph


# br-r37-c1-dkwy7. The multigraph sssp helpers: MultiGraph hashed every node name
# into a temporary index map per call (44.22x growth, 0.7135x -> 0.0158x), and
# MultiDiGraph found its source by LINEAR SCAN over every node name with string
# comparison (81.30x growth, 0.3236x -> 0.0040x - 250x slower than networkx at
# 12800 nodes). Both now use get_node_index.
#
# THAT SUBSTITUTION HAS A PRECONDITION worth testing rather than trusting:
# get_node_index must index the SAME order nodes_ordered() yields, because the
# returned source_idx is used against a `nodes` vector built from the latter. If
# the two ever disagreed - most plausibly after node removals renumber storage -
# the BFS would start from the WRONG NODE and return a confident, wrong answer.


@pytest.mark.parametrize("cls", MULTI + ["Graph", "DiGraph"])
def test_source_index_survives_node_removal_renumbering(cls):
    """Removals are where an index/order disagreement would surface."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(12)])
        g.add_edge("last", "n0")
        g.remove_node("n3")
        g.remove_node("n7")
        g.add_edge("fresh", "n11")

    for source in ("n0", "last", "fresh", "n11"):
        assert dict(fnx.single_source_shortest_path_length(got, source)) == dict(
            nx.single_source_shortest_path_length(want, source)
        ), f"{cls}: length from {source} diverged after removals"
        assert {
            str(k): [str(x) for x in v]
            for k, v in fnx.single_source_shortest_path(got, source).items()
        } == {
            str(k): [str(x) for x in v]
            for k, v in nx.single_source_shortest_path(want, source).items()
        }, f"{cls}: paths from {source} diverged after removals"


@pytest.mark.parametrize("cls", MULTI)
def test_last_inserted_node_as_source(cls):
    """A linear scan and an index map differ most obviously at the far end."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(30)])
        g.add_edge("omega", "n30")
    for cutoff in (None, 1, 2):
        assert dict(
            fnx.single_source_shortest_path_length(got, "omega", cutoff=cutoff)
        ) == dict(nx.single_source_shortest_path_length(want, "omega", cutoff=cutoff))


@pytest.mark.parametrize("cls", MULTI)
@pytest.mark.xfail(
    reason="br-r37-c1-dkwy7 kernel is written but UNBUILT (host disk throttle, "
    "no cargo); flip to a hard assert once the extension is rebuilt",
    strict=False,
)
def test_multigraph_sssp_path_cost_does_not_grow_with_the_parent(cls):
    small, large = 200, 12800
    rings = {
        n: (_multi_ring(fnx, cls, n), _multi_ring(nx, cls, n)) for n in (small, large)
    }
    fnx_growth = _best(
        lambda: fnx.single_source_shortest_path(rings[large][0], "n0", cutoff=1)
    ) / _best(lambda: fnx.single_source_shortest_path(rings[small][0], "n0", cutoff=1))
    nx_growth = _best(
        lambda: nx.single_source_shortest_path(rings[large][1], "n0", cutoff=1)
    ) / _best(lambda: nx.single_source_shortest_path(rings[small][1], "n0", cutoff=1))
    assert fnx_growth < 2.5 * max(nx_growth, 1.0), (
        f"{cls}: a {large // small}x bigger parent made fnx "
        f"single_source_shortest_path {fnx_growth:.2f}x slower for a one-hop "
        f"request while networkx moved {nx_growth:.2f}x"
    )
