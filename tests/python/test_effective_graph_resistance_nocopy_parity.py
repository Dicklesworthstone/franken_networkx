"""Parity for effective_graph_resistance after dropping the unconditional copy.

br-egrnocopy: effective_graph_resistance always made a shallow copy of G even
when weight=None (the default), where no edge-weight inversion happens -- pure
construction-tax waste (~5x slower than nx on a 300-node graph). It now only
copies when invert_weight is True AND a weight key is given. The result is
bit-identical and G is never mutated.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(Gx):
    Gf = fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def _mk(n, seed, *, weighted=False):
    Gx = nx.connected_watts_strogatz_graph(n, 6, 0.3, seed=seed)
    if weighted:
        rnd = random.Random(seed)
        for u, v in Gx.edges():
            Gx[u][v]["weight"] = rnd.randint(1, 5)
    return Gx, _cp(Gx)


def test_parity_weight_invert_matrix():
    for weight in (None, "weight"):
        for invert in (True, False):
            Gx, Gf = _mk(100, 3, weighted=True)
            a = nx.effective_graph_resistance(Gx, weight=weight, invert_weight=invert)
            b = fnx.effective_graph_resistance(Gf, weight=weight, invert_weight=invert)
            assert abs(a - b) < 1e-6, (weight, invert, a, b)


def test_unweighted_default_does_not_mutate_graph():
    Gf = _cp(nx.connected_watts_strogatz_graph(30, 6, 0.3, seed=1))
    edges_before = sorted(Gf.edges())
    n_before = Gf.number_of_edges()
    fnx.effective_graph_resistance(Gf)
    assert Gf.number_of_edges() == n_before
    assert sorted(Gf.edges()) == edges_before


def test_weighted_invert_does_not_mutate_graph():
    Gx, Gf = _mk(30, 2, weighted=True)
    weights_before = {(u, v): Gf[u][v]["weight"] for u, v in Gf.edges()}
    fnx.effective_graph_resistance(Gf, weight="weight", invert_weight=True)
    weights_after = {(u, v): Gf[u][v]["weight"] for u, v in Gf.edges()}
    assert weights_before == weights_after


def test_disconnected_returns_inf():
    Gf = fnx.Graph([(0, 1), (2, 3)])
    assert fnx.effective_graph_resistance(Gf) == float("inf")


def test_directed_raises():
    Gf = fnx.DiGraph([(0, 1), (1, 0)])
    try:
        fnx.effective_graph_resistance(Gf)
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for directed input")


def test_empty_raises():
    try:
        fnx.effective_graph_resistance(fnx.Graph())
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for empty graph")
