"""A* parity with networkx under admissible-but-INCONSISTENT heuristics.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.1: the native A* kernel closed a
node on its first pop, which is only optimal for consistent heuristics. With an
admissible but inconsistent heuristic it returned a longer path than networkx
(networkx GH #3464 / test_astar_directed3: cost 43 instead of 42). networkx
re-expands nodes and calls the heuristic once per node on first enqueue; these
tests pin the path, the length, and the heuristic call sequence to networkx.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED3_EDGES = [("n5", "n1", 11), ("n5", "n2", 9), ("n2", "n1", 1), ("n1", "n0", 32)]
DIRECTED3_H = {"n5": 36, "n2": 4, "n1": 0, "n0": 0}


def _build(module, cls_name, edges, nodes=()):
    graph = getattr(module, cls_name)()
    graph.add_nodes_from(nodes)
    graph.add_weighted_edges_from(edges)
    return graph


@pytest.mark.parametrize("cls_name", ["DiGraph", "Graph"])
def test_networkx_gh3464_directed3_case(cls_name):
    def heuristic(u, v):
        return DIRECTED3_H[u]

    for module in (nx, fnx):
        graph = _build(module, cls_name, DIRECTED3_EDGES)
        assert module.astar_path(graph, "n5", "n0", heuristic) == ["n5", "n2", "n1", "n0"]
        assert module.astar_path_length(graph, "n5", "n0", heuristic) == 42


def test_heuristic_call_sequence_matches_networkx():
    edges = [("s", "a", 1), ("s", "b", 1), ("a", "t", 1), ("b", "t", 1), ("t", "s", 1)]
    sequences = {}
    for module in (nx, fnx):
        calls = []

        def heuristic(u, v, calls=calls):
            calls.append((u, v))
            return 0

        graph = _build(module, "DiGraph", edges)
        assert module.astar_path(graph, "s", "t", heuristic) == ["s", "a", "t"]
        sequences[module.__name__] = calls
    assert sequences["franken_networkx"] == sequences["networkx"] == [
        ("a", "t"),
        ("b", "t"),
        ("t", "t"),
    ]


def _random_case(rng, directed):
    n = rng.randint(4, 18)
    nodes = list(range(n))
    edges = set()
    for _ in range(rng.randint(n, 4 * n)):
        u, v = rng.sample(nodes, 2)
        if not directed and (v, u) in edges:
            continue
        edges.add((u, v))
    weighted = [(u, v, rng.randint(1, 20)) for u, v in sorted(edges)]
    return nodes, weighted


@pytest.mark.parametrize("directed", [True, False])
def test_random_inconsistent_heuristics_match_networkx_and_dijkstra(directed):
    rng = random.Random(20260923 + directed)
    cls_name = "DiGraph" if directed else "Graph"
    checked = 0
    for _ in range(300):
        nodes, edges = _random_case(rng, directed)
        source, target = rng.sample(nodes, 2)
        gnx = _build(nx, cls_name, edges, nodes)
        gfx = _build(fnx, cls_name, edges, nodes)
        if not nx.has_path(gnx, source, target):
            continue
        # Admissible (never exceeds the true distance) but deliberately
        # inconsistent: every node gets its own random fraction of the truth.
        rev = gnx.reverse(copy=True) if directed else gnx
        true_dist = nx.single_source_dijkstra_path_length(rev, target)
        frac = {u: rng.random() for u in nodes}
        h_table = {u: int(frac[u] * true_dist.get(u, 0)) for u in nodes}

        def heuristic(u, v, h_table=h_table):
            return h_table[u]

        optimum = nx.dijkstra_path_length(gnx, source, target)
        nx_path = nx.astar_path(gnx, source, target, heuristic)
        fx_path = fnx.astar_path(gfx, source, target, heuristic)
        assert fx_path == nx_path, (edges, source, target, h_table)
        assert nx.path_weight(gnx, fx_path, "weight") == optimum
        assert fnx.astar_path_length(gfx, source, target, heuristic) == optimum
        checked += 1
    assert checked > 100
