"""Parity for the BFS-distance fast path in local/global_reaching_centrality (br-r37-c1-lrcdist).

local_reaching_centrality(G, v) with weight=None was up to ~8x SLOWER than networkx
because it (1) called is_negatively_weighted(G, weight=None), which materialized the
whole edges(data=True) view to evaluate the vacuous `any(None in data ...)`, and (2)
built full shortest_path node-lists when only BFS distances are consumed. The
weight=None path now skips the vacuous negative-weight guard and uses
single_source_shortest_path_length (same BFS-discovery order), so the float results
are unchanged while it is now 2.6x-11.7x FASTER. The same guard is applied to
global_reaching_centrality.

These lock value parity (vs networkx) on the unweighted fast path, the weighted
delegated path, and the error contracts.
"""

import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _cp(G, directed=False):
    F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


def _close(a, b, tol=1e-12):
    return abs(a - b) <= tol


def test_local_and_global_match_networkx_unweighted():
    for seed in range(300):
        rnd = random.Random(seed)
        n = rnd.randint(2, 55)
        p = rnd.uniform(0.0, 0.45)
        directed = seed % 2 == 0
        G = nx.gnp_random_graph(n, p, seed=seed, directed=directed)
        F = _cp(G, directed)
        try:
            gx = nx.global_reaching_centrality(G)
        except nx.NetworkXError:
            with pytest.raises(nx.NetworkXError):
                fnx.global_reaching_centrality(F)
            continue
        assert _close(gx, fnx.global_reaching_centrality(F)), seed
        for v in list(G.nodes())[:4]:
            assert _close(
                nx.local_reaching_centrality(G, v),
                fnx.local_reaching_centrality(F, v),
            ), (seed, v)


def test_weighted_path_preserved():
    Gd = nx.gnp_random_graph(35, 0.2, seed=3, directed=True)
    for u, v in Gd.edges():
        Gd[u][v]["weight"] = 1.0 + (u + v) % 4
    Fd = _cp(Gd, directed=True)
    for u, v in Gd.edges():
        Fd[u][v]["weight"] = Gd[u][v]["weight"]
    assert _close(
        nx.global_reaching_centrality(Gd, weight="weight"),
        fnx.global_reaching_centrality(Fd, weight="weight"),
        tol=1e-9,
    )
    for v in [0, 5, 10, 20]:
        assert _close(
            nx.local_reaching_centrality(Gd, v, weight="weight"),
            fnx.local_reaching_centrality(Fd, v, weight="weight"),
            tol=1e-9,
        )


def test_explicit_paths_argument_preserved():
    G = nx.gnp_random_graph(20, 0.25, seed=9)
    F = _cp(G)
    paths = dict(nx.shortest_path(G, source=0))
    fpaths = dict(fnx.shortest_path(F, source=0))
    assert _close(
        nx.local_reaching_centrality(G, 0, paths=paths),
        fnx.local_reaching_centrality(F, 0, paths=fpaths),
    )


def test_edgeless_graph_raises():
    G = nx.empty_graph(5)
    F = _cp(G)
    with pytest.raises(nx.NetworkXError):
        fnx.global_reaching_centrality(F)
    with pytest.raises(nx.NetworkXError):
        fnx.local_reaching_centrality(F, 0)


def test_directed_reachability_fixture():
    # Directed star: center reaches all, leaves reach none.
    G = nx.DiGraph()
    G.add_edges_from([(0, i) for i in range(1, 6)])
    F = _cp(G, directed=True)
    assert _close(nx.local_reaching_centrality(G, 0), fnx.local_reaching_centrality(F, 0))
    assert _close(nx.local_reaching_centrality(G, 1), fnx.local_reaching_centrality(F, 1))
    assert _close(
        nx.global_reaching_centrality(G), fnx.global_reaching_centrality(F)
    )
