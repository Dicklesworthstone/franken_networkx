"""Native directed A* kernel parity + non-delegation (br-r37-c1-kp1va).

Earlier (br-r37-c1-astdir) directed graphs delegated to networkx because the
Rust ``astar_path`` kernel was undirected-only. The kernel is now generic over
``GraphView`` and the PyO3 binding dispatches DiGraph/MultiDiGraph to their
directed projection (``GraphView::neighbors_iter`` yields successors), so
directed A* runs natively *and* respects edge direction. These tests assert it
matches networkx exactly AND no longer falls back to nx for directed graphs.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _directed(mod, edges):
    g = mod.DiGraph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


_EDGES = [
    (0, 1, 2), (1, 2, 1), (2, 3, 3), (0, 3, 9), (3, 4, 1),
    (4, 0, 1), (1, 4, 5), (2, 4, 2), (0, 2, 4), (4, 2, 1),
]


def test_directed_astar_respects_direction():
    # Only 4->0 exists (not 0->4): 0->4 must take the forward route.
    g = fnx.DiGraph()
    g.add_edge(4, 0, weight=1)
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=1)
    g.add_edge(2, 4, weight=1)
    assert fnx.astar_path(g, 0, 4, weight="weight") == [0, 1, 2, 4]
    assert fnx.astar_path_length(g, 0, 4, weight="weight") == 3


@pytest.mark.parametrize("target", [1, 2, 3, 4])
def test_directed_astar_path_matches_networkx(target):
    gn, gf = _directed(nx, _EDGES), _directed(fnx, _EDGES)
    assert fnx.astar_path(gf, 0, target, weight="weight") == nx.astar_path(gn, 0, target, weight="weight")
    assert fnx.astar_path_length(gf, 0, target, weight="weight") == nx.astar_path_length(gn, 0, target, weight="weight")


def test_directed_astar_with_heuristic_matches_networkx():
    gn, gf = _directed(nx, _EDGES), _directed(fnx, _EDGES)
    h = lambda u, v: 0
    for t in (2, 3, 4):
        assert fnx.astar_path(gf, 0, t, heuristic=h, weight="weight") == nx.astar_path(gn, 0, t, heuristic=h, weight="weight")


def test_multidigraph_astar_matches_networkx():
    def build(mod):
        g = mod.MultiDiGraph()
        g.add_edge(0, 1, weight=2)
        g.add_edge(0, 1, weight=5)
        g.add_edge(1, 2, weight=1)
        g.add_edge(2, 0, weight=1)
        return g
    assert fnx.astar_path(build(fnx), 0, 2, weight="weight") == nx.astar_path(build(nx), 0, 2, weight="weight")


def test_directed_astar_does_not_delegate_to_networkx(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx astar_path fallback was used for a DiGraph")

    monkeypatch.setattr(nx, "astar_path", fail)
    g = _directed(fnx, _EDGES)
    assert fnx.astar_path(g, 0, 4, weight="weight")[0] == 0


def test_directed_astar_length_does_not_delegate_to_networkx(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx astar_path_length fallback was used for a DiGraph")

    monkeypatch.setattr(nx, "astar_path_length", fail)
    g = _directed(fnx, _EDGES)
    assert fnx.astar_path_length(g, 0, 4, weight="weight") >= 0
