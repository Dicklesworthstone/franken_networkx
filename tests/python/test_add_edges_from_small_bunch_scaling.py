"""br-r37-c1-6avaj - a small add_edges_from must not cost O(nodes).

Graph.add_edges_from tries a native index batch first, and that batch's guard
walked every node (int_prefix_display_keys_are_plain_ints) BEFORE checking that
the bunch was big enough to batch at all. Every small call on an int-keyed graph
with edges therefore paid O(nodes), and a graph grown by small calls was
quadratic. Measured on the same host, fnx vs networkx live in one process:

    one add_edges_from([(i, i + 1)]) per edge, 8000-node path   0.006x
    make_clique_bipartite(gnm(2000, 6000))                      0.017x
    extended_barabasi_albert_graph(5000, 3, 0, 0)               0.033x

and after the guard learned to decline on length first, 0.36x / 0.61x / 0.65x.

Like test_get_edge_data_parallel_edge_scaling, this measures GROWTH inside one
process, not a ratio: the per-edge cost of the one-edge loop at 8000 nodes over
that at 1000. Before the fix fnx grew ~8x across that span (the scan is linear
in nodes); after, ~1x. networkx's own growth is the control - it should be flat,
and when the host makes it look non-flat the test says so instead of blaming fnx.
"""

from __future__ import annotations

import time

import networkx as nx

import franken_networkx as fnx

SMALL = 1000
LARGE = 8000
# Unfixed fnx grew ~8x across this span, fixed ~1x; the bound sits between.
MAX_RELATIVE_GROWTH = 3.0


def _per_edge_seconds(lib, n, shape):
    best = float("inf")
    for _ in range(3):
        graph = lib.Graph()
        start = time.perf_counter()
        if shape == "pair":
            for i in range(n - 1):
                graph.add_edges_from([(i, i + 1)])
        elif shape == "attr":
            for i in range(n - 1):
                graph.add_edges_from([(i, i + 1, {"w": i})])
        else:
            for i in range(n - 1):
                graph.add_weighted_edges_from([(i, i + 1, 1.5)])
        best = min(best, (time.perf_counter() - start) / (n - 1))
    return best


def _growth(lib, shape):
    return _per_edge_seconds(lib, LARGE, shape) / _per_edge_seconds(lib, SMALL, shape)


def test_one_edge_add_edges_from_loop_stays_linear():
    for shape in ("pair", "attr", "weighted"):
        nx_growth = _growth(nx, shape)
        if nx_growth > MAX_RELATIVE_GROWTH:
            raise AssertionError(
                f"control failed: networkx grew {nx_growth:.1f}x ({shape}); the host is too "
                "noisy to judge fnx's growth"
            )
        fnx_growth = _growth(fnx, shape)
        assert fnx_growth < MAX_RELATIVE_GROWTH, (
            f"{shape}: fnx per-edge cost grew {fnx_growth:.1f}x from {SMALL} to {LARGE} nodes "
            f"(networkx {nx_growth:.1f}x) - a small add_edges_from is paying O(nodes) again"
        )


def test_small_bunch_result_matches_networkx():
    graphs = (fnx.Graph(), nx.Graph())
    for graph in graphs:
        for i in range(300):
            graph.add_edges_from([(i, i + 1), (i, (i * 7) % 301)])
        graph.add_edges_from([(1, 2, {"w": 3})])
    fnx_graph, nx_graph = graphs
    assert list(fnx_graph) == list(nx_graph)
    assert list(fnx_graph.edges(data=True)) == list(nx_graph.edges(data=True))
