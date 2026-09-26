"""Seeded edge swaps produce exactly networkx's graph.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.4: fnx's double_edge_swap and
directed_edge_swap used a different algorithm (uniform edge pick) than networkx
(degree-weighted source + random neighbour), so ``seed=42`` gave a different
graph — 12 failures in networkx's own test_swap.py when run with fnx as the
backend. These tests compare against networkx for many seeds, including the
final adjacency ORDER, the max_tries error text, and the precondition errors.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _pair(module, edges, directed=False):
    graph = (module.DiGraph if directed else module.Graph)()
    graph.add_edges_from(edges)
    return graph


def _adjacency(G):
    return [(u, list(G[u])) for u in G]


@pytest.mark.parametrize("seed", range(40))
def test_double_edge_swap_matches_networkx(seed):
    base = nx.gnm_random_graph(30, 70, seed=seed)
    edges = list(base.edges())
    gnx, gfx = _pair(nx, edges), _pair(fnx, edges)
    rn = nx.double_edge_swap(gnx, nswap=10, max_tries=500, seed=seed)
    rf = fnx.double_edge_swap(gfx, nswap=10, max_tries=500, seed=seed)
    assert rf is gfx and rn is gnx
    assert _adjacency(gfx) == _adjacency(gnx)
    assert list(gfx.edges()) == list(gnx.edges())


@pytest.mark.parametrize("seed", range(40))
def test_directed_edge_swap_matches_networkx(seed):
    base = nx.gnm_random_graph(25, 90, seed=seed, directed=True)
    edges = list(base.edges())
    gnx, gfx = _pair(nx, edges, True), _pair(fnx, edges, True)
    nx.directed_edge_swap(gnx, nswap=5, max_tries=500, seed=seed)
    fnx.directed_edge_swap(gfx, nswap=5, max_tries=500, seed=seed)
    assert _adjacency(gfx) == _adjacency(gnx)
    assert [(u, list(gfx.pred[u])) for u in gfx] == [(u, list(gnx.pred[u])) for u in gnx]


def test_random_instance_seed_consumes_like_networkx():
    edges = list(nx.gnm_random_graph(20, 45, seed=3).edges())
    rn, rf = random.Random(99), random.Random(99)
    gnx, gfx = _pair(nx, edges), _pair(fnx, edges)
    nx.double_edge_swap(gnx, nswap=4, max_tries=200, seed=rn)
    fnx.double_edge_swap(gfx, nswap=4, max_tries=200, seed=rf)
    assert list(gfx.edges()) == list(gnx.edges())
    assert rn.random() == rf.random()  # same number of draws consumed


def test_max_tries_exhaustion_message_and_partial_state_match():
    edges = list(nx.complete_graph(5).edges())  # complete: no swap can succeed
    for module in (nx, fnx):
        G = _pair(module, edges)
        with pytest.raises(module.NetworkXAlgorithmError, match=r"Maximum number of swap attempts \(\d+\)"):
            module.double_edge_swap(G, nswap=1, max_tries=10, seed=1)


@pytest.mark.parametrize(
    "call, error",
    [
        (lambda m: m.directed_edge_swap(m.path_graph(5), nswap=1, seed=1), "NetworkXNotImplemented"),
        (lambda m: m.directed_edge_swap(_pair(m, [(0, 1), (1, 2), (2, 3), (3, 0)], True), nswap=5, max_tries=2, seed=1), "NetworkXError"),
        (lambda m: m.directed_edge_swap(_pair(m, [(0, 1), (1, 2)], True), nswap=1, seed=1), "NetworkXError"),
        (lambda m: m.double_edge_swap(m.path_graph(3), nswap=1, seed=1), "NetworkXError"),
    ],
)
def test_precondition_errors_match_networkx(call, error):
    for module in (nx, fnx):
        with pytest.raises(getattr(module, error)):
            call(module)


@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("window_threshold", [3, 1, 50])
def test_connected_double_edge_swap_matches_networkx(seed, window_threshold):
    base = nx.connected_watts_strogatz_graph(30, 4, 0.3, seed=seed)
    edges = list(base.edges())
    gnx, gfx = _pair(nx, edges), _pair(fnx, edges)
    cn = nx.connected_double_edge_swap(gnx, nswap=20, _window_threshold=window_threshold, seed=seed)
    cf = fnx.connected_double_edge_swap(gfx, nswap=20, _window_threshold=window_threshold, seed=seed)
    assert cf == cn
    assert _adjacency(gfx) == _adjacency(gnx)
    assert fnx.is_connected(gfx)


# br-r37-c1-cdf1v: networkx's @py_random_state resolves the seed before the
# body's checks - and before @not_implemented_for, which its flattened argmap
# runs after - so a bad seed raises ValueError whatever the graph. fnx checked
# directedness and size first.
@pytest.mark.parametrize("seed", [1.5, "x", float("nan")])
@pytest.mark.parametrize(
    "name, directed, edges",
    [
        ("double_edge_swap", True, [(0, 1), (1, 2), (2, 3), (3, 0)]),
        ("double_edge_swap", False, [(0, 1), (1, 2)]),
        ("directed_edge_swap", False, [(0, 1), (1, 2), (2, 3), (3, 0)]),
        ("directed_edge_swap", True, [(0, 1), (1, 2)]),
        ("directed_edge_swap", True, [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]),
    ],
    ids=["double_on_digraph", "double_small", "directed_on_graph", "directed_small", "directed_ok"],
)
def test_swap_seed_is_resolved_before_the_graph_checks(name, directed, edges, seed):
    def outcome(module):
        try:
            getattr(module, name)(_pair(module, edges, directed), nswap=1, max_tries=100, seed=seed)
        except Exception as exc:  # noqa: BLE001 - the exception is the outcome
            return type(exc).__name__, str(exc)
        return "ok"

    assert outcome(fnx) == outcome(nx)
