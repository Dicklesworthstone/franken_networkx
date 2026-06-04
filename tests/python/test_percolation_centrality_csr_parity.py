"""Parity for the integer-CSR fast path of percolation_centrality.

br-perccsr: for the unweighted case, percolation_centrality replaced the
per-source pure-Python Brandes BFS (string-keyed dicts over fnx adjacency) with
an integer-CSR BFS over flat arrays + a local adjacency list. Brandes
accumulation is order-independent and neighbor order is preserved from G[node],
so the result is bit-identical to the previous dict implementation and matches
networkx within float tolerance. 173ms -> 33ms (faster than nx).
"""

import random

import networkx as nx

import franken_networkx as fnx


def _mk(n, seed, *, directed=False, attr=True):
    if directed:
        base = nx.gnm_random_graph(n, min(n * 5, n * (n - 1)), seed=seed, directed=True)
    elif n > 4:
        k = 6 if (n - 1) >= 6 else (n - 1 if (n - 1) % 2 == 0 else n - 2)
        base = nx.connected_watts_strogatz_graph(n, k, 0.3, seed=seed)
    else:
        base = nx.path_graph(n)
    rnd = random.Random(seed)
    if attr:
        for node in base.nodes():
            base.nodes[node]["percolation"] = round(rnd.random(), 3)
    Gf = (fnx.DiGraph if directed else fnx.Graph)()
    Gf.add_nodes_from((node, dict(d)) for node, d in base.nodes(data=True))
    Gf.add_edges_from(base.edges())
    return base, Gf


def _close(a, b, tol=1e-12):
    return set(a) == set(b) and all(abs(a[k] - b[k]) <= tol for k in a)


def test_parity_matrix():
    for n, directed, attr in [
        (80, False, True),
        (60, True, True),
        (100, False, False),
        (50, True, False),
        (3, False, True),
        (5, False, True),
    ]:
        Gx, Gf = _mk(n, n + int(directed), directed=directed, attr=attr)
        assert _close(
            nx.percolation_centrality(Gx), fnx.percolation_centrality(Gf)
        ), (n, directed, attr)


def test_custom_states_dict():
    Gx, Gf = _mk(40, 7, attr=False)
    rnd = random.Random(9)
    states = {i: rnd.random() for i in Gx.nodes()}
    assert _close(
        nx.percolation_centrality(Gx, states=states),
        fnx.percolation_centrality(Gf, states=states),
    )


def test_default_attribute_is_one():
    # No 'percolation' attribute set -> every node defaults to state 1.
    Gx, Gf = _mk(60, 3, attr=False)
    assert _close(
        nx.percolation_centrality(Gx), fnx.percolation_centrality(Gf)
    )


def test_directed_graph_uses_successors():
    Gx, Gf = _mk(70, 11, directed=True)
    assert _close(
        nx.percolation_centrality(Gx), fnx.percolation_centrality(Gf)
    )


def test_weighted_path_still_supported():
    # weight != None falls through to the existing Dijkstra-basic path.
    base = nx.connected_watts_strogatz_graph(40, 6, 0.3, seed=5)
    rnd = random.Random(5)
    for u, v in base.edges():
        base[u][v]["weight"] = rnd.randint(1, 9)
    for node in base.nodes():
        base.nodes[node]["percolation"] = round(rnd.random(), 3)
    Gf = fnx.Graph()
    Gf.add_nodes_from((n, dict(d)) for n, d in base.nodes(data=True))
    Gf.add_edges_from((u, v, dict(d)) for u, v, d in base.edges(data=True))
    assert _close(
        nx.percolation_centrality(base, weight="weight"),
        fnx.percolation_centrality(Gf, weight="weight"),
    )
