"""Parity for the integer-CSR edge_load_centrality.

br-elccsr: edge_load_centrality ran N per-source pure-Python BFS
(_edge_load_from_source_local -> _single_source_shortest_path_basic_local) plus
an O(E) (node, node)-keyed `between` dict rebuilt per source — up to ~10x slower
than networkx (1.25s under load). It now relabels nodes to dense indices once,
snapshots a local integer adjacency list, and runs all N BFS + the edge-load
accumulation on integer-keyed dicts. Neighbor order (G[node]) and edge order
(G.edges()) are preserved, so the float result is bit-identical to the prior
implementation and matches networkx.
"""

import networkx as nx

import franken_networkx as fnx


def _mk(n, seed, *, directed=False):
    if directed:
        base = nx.gnm_random_graph(n, n * 4, seed=seed, directed=True)
    else:
        k = 6 if n > 6 else (n - 1 if (n - 1) % 2 == 0 else n - 2)
        base = nx.connected_watts_strogatz_graph(n, max(2, k), 0.3, seed=seed)
    Gf = (fnx.DiGraph if directed else fnx.Graph)()
    Gf.add_nodes_from(base.nodes())
    Gf.add_edges_from(base.edges())
    return base, Gf


def _close(a, b, tol=1e-9):
    return set(a) == set(b) and all(abs(a[k] - b[k]) <= tol for k in a)


def test_parity_matrix():
    for n, directed in [(60, False), (40, True), (100, False), (8, False)]:
        Gx, Gf = _mk(n, n + int(directed), directed=directed)
        assert _close(
            nx.edge_load_centrality(Gx), fnx.edge_load_centrality(Gf)
        ), (n, directed)


def test_cutoff_parity():
    Gx, Gf = _mk(50, 5)
    for cutoff in (1, 2, 3):
        assert _close(
            nx.edge_load_centrality(Gx, cutoff=cutoff),
            fnx.edge_load_centrality(Gf, cutoff=cutoff),
        ), cutoff


def test_cutoff_false_default():
    Gx, Gf = _mk(40, 7)
    assert _close(
        nx.edge_load_centrality(Gx, cutoff=False),
        fnx.edge_load_centrality(Gf, cutoff=False),
    )


def test_both_edge_directions_present():
    Gx, Gf = _mk(30, 3)
    result = fnx.edge_load_centrality(Gf)
    for u, v in Gf.edges():
        assert (u, v) in result and (v, u) in result


def test_determinism():
    _, Gf = _mk(50, 11)
    assert fnx.edge_load_centrality(Gf) == fnx.edge_load_centrality(Gf)
