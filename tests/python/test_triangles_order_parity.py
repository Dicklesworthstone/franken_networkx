"""Parity for ``triangles`` dict iteration order.

Bead br-r37-c1-k3khk. fnx returned a dict with keys sorted; nx
iterates in node-insertion order. Same iteration-order family fixed
in br-r37-c1-pm78h (communicability_betweenness_centrality),
br-r37-c1-f6epo (second_order_centrality), and br-r37-c1-9fa26
(core_number).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_triangles_iterates_in_insertion_order():
    """When edges are added in non-monotonic order, iteration follows
    node insertion order, not sorted-key order."""
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [(2, 3), (0, 1), (1, 2), (3, 4)]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.triangles(G)
    n = nx.triangles(GX)
    assert list(f.keys()) == list(n.keys()) == [2, 3, 0, 1, 4]


@needs_nx
def test_triangles_string_nodes_iteration_order():
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c")]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.triangles(G)
    n = nx.triangles(GX)
    assert list(f.keys()) == list(n.keys()) == ["c", "d", "a", "b"]


@needs_nx
def test_triangles_k4_values_unchanged():
    """Sanity: values still correct after reorder."""
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    assert dict(fnx.triangles(G)) == dict(nx.triangles(GX))
    assert all(v == 3 for v in fnx.triangles(G).values())


@needs_nx
def test_triangles_empty_graph():
    G = fnx.Graph()
    GX = nx.Graph()
    assert dict(fnx.triangles(G)) == dict(nx.triangles(GX)) == {}


@needs_nx
def test_triangles_isolated_nodes_iteration():
    """Isolated nodes (degree 0) should still appear in iteration."""
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_nodes_from([2, 0, 1])
    GX.add_nodes_from([2, 0, 1])
    G.add_edge(0, 1)
    GX.add_edge(0, 1)
    f = fnx.triangles(G)
    n = nx.triangles(GX)
    assert list(f.keys()) == list(n.keys())
    assert all(v == 0 for v in f.values())


@needs_nx
def test_triangles_with_nodes_kwarg_subset():
    """Subset selection via nodes= kwarg returns dict in iteration
    order of the subset (same on both libs)."""
    G = fnx.cycle_graph(5)
    GX = nx.cycle_graph(5)
    f = fnx.triangles(G, nodes=[2, 0, 4])
    n = nx.triangles(GX, nodes=[2, 0, 4])
    assert dict(f) == dict(n)


# br-r37-c1-mub4s: triangles(nodes=) and clustering(nodes=) count through a
# native per-node kernel. Twins are built from ONE edge stream (rebuilding one
# from the other's edges() reorders rows) and carry self-loops both on queried
# nodes and on their neighbours - a kernel that let a loop into a node's
# neighbour set, or counted w's own loop as a closing edge, shifts both the
# degree and the triangle count.


def _loopy_twins():
    import random

    rng = random.Random(7)
    edges = [(u, v) for u in range(60) for v in range(u + 1, 60) if rng.random() < 0.15]
    edges += [(v, v) for v in range(0, 60, 4)]
    rng.shuffle(edges)
    G, GX = fnx.Graph(), nx.Graph()
    G.add_nodes_from(range(59, -1, -1))
    GX.add_nodes_from(range(59, -1, -1))
    G.add_edges_from(edges)
    GX.add_edges_from(edges)
    return G, GX


def _same_mapping(f, n):
    assert f == n
    assert list(f) == list(n)
    assert [type(value) for value in f.values()] == [type(value) for value in n.values()]


_NBUNCH = [8, 3, 57, 8, 0, 12, 99, 41, 4, "absent", 33]


@needs_nx
def test_triangles_nbunch_equals_networkx_on_self_loop_twins():
    G, GX = _loopy_twins()
    _same_mapping(fnx.triangles(G, nodes=_NBUNCH), nx.triangles(GX, nodes=_NBUNCH))
    _same_mapping(fnx.triangles(G, nodes=list(GX)), nx.triangles(GX, nodes=list(GX)))


@needs_nx
def test_clustering_nbunch_equals_networkx_on_self_loop_twins():
    G, GX = _loopy_twins()
    _same_mapping(fnx.clustering(G, nodes=_NBUNCH), nx.clustering(GX, nodes=_NBUNCH))
    _same_mapping(
        fnx.clustering(G, nodes=iter(range(0, 60, 3))),
        nx.clustering(GX, nodes=iter(range(0, 60, 3))),
    )


@needs_nx
def test_single_node_triangles_and_clustering_equal_networkx():
    G, GX = _loopy_twins()
    for node in GX:
        assert fnx.triangles(G, node) == nx.triangles(GX, node)
        f, n = fnx.clustering(G, node), nx.clustering(GX, node)
        assert f == n and type(f) is type(n)


@needs_nx
def test_nbunch_after_mutation_and_with_string_nodes():
    G, GX = _loopy_twins()
    for graph in (G, GX):
        graph.remove_node(12)
        graph.remove_edges_from([(8, 8), (0, 3)])
        graph.add_edges_from([(8, 3), (8, 57), (3, 57), (41, 41)])
    _same_mapping(fnx.triangles(G, nodes=_NBUNCH), nx.triangles(GX, nodes=_NBUNCH))
    _same_mapping(fnx.clustering(G, nodes=_NBUNCH), nx.clustering(GX, nodes=_NBUNCH))

    stream = [("b", "a"), ("a", "c"), ("c", "b"), ("c", "d"), ("d", "d"), ("d", "b")]
    S, SX = fnx.Graph(stream), nx.Graph(stream)
    _same_mapping(fnx.triangles(S, nodes="dcb"), nx.triangles(SX, nodes="dcb"))
    _same_mapping(fnx.clustering(S, nodes=["d", "a"]), nx.clustering(SX, nodes=["d", "a"]))


@needs_nx
def test_nbunch_keeps_the_callers_equal_key_objects():
    edges = [(1, 2), (2, 3), (3, 1), (3, 4)]
    G, GX = fnx.Graph(edges), nx.Graph(edges)
    f, n = fnx.triangles(G, nodes=[1.0, True, 4]), nx.triangles(GX, nodes=[1.0, True, 4])
    assert f == n
    assert [(key, type(key)) for key in f] == [(key, type(key)) for key in n]


@needs_nx
def test_node_not_in_graph_raises_like_networkx():
    G, GX = _loopy_twins()
    for call in (lambda m, g: m.triangles(g, 99), lambda m, g: m.clustering(g, 99)):
        with pytest.raises(fnx.NetworkXError) as fnx_error:
            call(fnx, G)
        with pytest.raises(nx.NetworkXError) as nx_error:
            call(nx, GX)
        assert fnx_error.value.args == nx_error.value.args


# br-r37-c1-qnj0n: directed clustering(nodes=) reads only the requested nodes'
# rows and their neighbours' rows, as networkx does. It snapshotted pred and
# succ for EVERY node, so clustering(G, node) beside a 32k-node component took
# 56 ms where networkx takes 7 us. Twins carry reciprocal edges (the
# reciprocal-degree term) and self-loops on queried nodes and neighbours.


def _directed_loopy_twins():
    import random

    rng = random.Random(11)
    edges = [(u, v) for u in range(50) for v in range(50) if u != v and rng.random() < 0.08]
    edges += [(v, u) for u, v in edges[::5]] + [(v, v) for v in range(0, 50, 6)]
    rng.shuffle(edges)
    G, GX = fnx.DiGraph(), nx.DiGraph()
    G.add_nodes_from(range(49, -1, -1))
    GX.add_nodes_from(range(49, -1, -1))
    G.add_edges_from(edges)
    GX.add_edges_from(edges)
    return G, GX


@needs_nx
def test_directed_clustering_nbunch_and_single_nodes_equal_networkx():
    G, GX = _directed_loopy_twins()
    _same_mapping(fnx.clustering(G, nodes=_NBUNCH), nx.clustering(GX, nodes=_NBUNCH))
    for node in GX:
        f, n = fnx.clustering(G, node), nx.clustering(GX, node)
        assert f == n and type(f) is type(n)
    G.remove_edges_from([(u, v) for u, v in list(G.edges(0))])
    GX.remove_edges_from([(u, v) for u, v in list(GX.edges(0))])
    G.add_edge(12, 0)
    GX.add_edge(12, 0)
    _same_mapping(fnx.clustering(G, nodes=_NBUNCH), nx.clustering(GX, nodes=_NBUNCH))


def _directed_best_of(fn, reps=30, rounds=7):
    import time

    fn()
    best = None
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            fn()
        elapsed = (time.perf_counter() - start) / reps
        best = elapsed if best is None else min(best, elapsed)
    return best


@needs_nx
def test_directed_single_node_clustering_does_not_grow_with_the_parent():
    """A node of a 10-node component beside a disconnected directed ring of 200
    vs 12800 nodes; fnx's growth judged against networkx's in the same process."""
    growth = {}
    for lib in (fnx, nx):
        times = []
        for ring in (200, 12800):
            g = lib.DiGraph()
            g.add_edges_from([(i, i + 1) for i in range(9)] + [(2, 0), (5, 3)])
            g.add_edges_from((100 + i, 100 + (i + 1) % ring) for i in range(ring))
            times.append(_directed_best_of(lambda: lib.clustering(g, 1)))
        growth[lib.__name__] = times[1] / times[0]
    assert growth["franken_networkx"] < 2.5 * max(growth["networkx"], 1.0), growth


# br-r37-c1-0g2tj follow-up: WEIGHTED clustering(nodes=) snapshotted every
# node's rows and cached every edge weight before looking at the queried nodes
# (0.26-0.37x networkx for one node), where the unweighted path had been
# local since qnj0n. networkx's only whole-graph pass is the max-weight scan.


def _weighted_twins(directed, seed):
    import random

    rng = random.Random(seed)
    edges = [
        (u, v, rng.choice([1, 2, 3, 0.5, 2.5]))
        for u in range(40)
        for v in range(40)
        if u != v and rng.random() < 0.1
    ]
    edges += [(v, v, 2) for v in range(0, 40, 9)]
    graphs = []
    for lib in (fnx, nx):
        graph = lib.DiGraph() if directed else lib.Graph()
        graph.add_nodes_from(range(39, -1, -1))
        graph.add_weighted_edges_from(edges)
        graph.add_edges_from([(3, 17), (17, 3), (8, 30)])  # no weight: 1
        graphs.append(graph)
    return graphs


@needs_nx
@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("directed", [False, True])
def test_weighted_clustering_nbunch_is_the_whole_graph_answer(directed, seed):
    G, GX = _weighted_twins(directed, seed)
    full = fnx.clustering(G, weight="weight")
    subset = [0, 3, 17, 30, 39]
    local = fnx.clustering(G, subset, weight="weight")
    # Bit-identical to the whole-graph pass: same rows, same summation order.
    assert list(local.items()) == [(node, full[node]) for node in subset]
    for node in subset:
        assert fnx.clustering(G, node, weight="weight") == full[node]
    expected = nx.clustering(GX, subset, weight="weight")
    assert list(local) == list(expected)
    for node in subset:
        assert local[node] == pytest.approx(expected[node], rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("directed", [False, True])
def test_weighted_single_node_clustering_costs_one_max_weight_scan(directed):
    """Judged against fnx's own max-weight scan over the same graph, which host
    load moves the same way; the whole-graph snapshot cost ~5x the scan."""
    g = fnx.DiGraph() if directed else fnx.Graph()
    g.add_edges_from([(i, i + 1, {"weight": 1 + i % 3}) for i in range(9)])
    g.add_edges_from([(2, 0, {"weight": 2}), (5, 3, {"weight": 1})])
    g.add_edges_from((100 + i, 100 + (i + 1) % 12800, {"weight": 1}) for i in range(12800))
    scan = _directed_best_of(
        lambda: max(attrs.get("weight", 1) for _, _, attrs in g.edges(data=True)), reps=5
    )
    call = _directed_best_of(lambda: fnx.clustering(g, 1, weight="weight"), reps=5)
    assert call < 2.0 * scan, (call, scan)


# br-r37-c1-0g2tj follow-up: directed clustering counts networkx's integers
# natively (total degree, reciprocal degree, directed triangles - a
# reciprocal neighbour counted twice, self-loops dropped), for every node and
# for nbunch calls alike.


@needs_nx
def test_directed_clustering_all_nodes_equals_networkx_exactly():
    G, GX = _directed_loopy_twins()
    f, n = fnx.clustering(G), nx.clustering(GX)
    assert list(f.items()) == list(n.items())
    assert [type(v) for v in f.values()] == [type(v) for v in n.values()]
    assert fnx.average_clustering(G) == nx.average_clustering(GX)


@needs_nx
def test_directed_clustering_on_views_equals_networkx():
    G, GX = _directed_loopy_twins()
    for view_f, view_n in (
        (G.reverse(copy=False), GX.reverse(copy=False)),
        (G.subgraph(range(0, 50, 2)), GX.subgraph(range(0, 50, 2))),
    ):
        assert list(fnx.clustering(view_f).items()) == list(nx.clustering(view_n).items())
        assert fnx.clustering(view_f, nodes=_NBUNCH) == nx.clustering(view_n, nodes=_NBUNCH)
