"""br-r37-c1-lg07d: regression tests for is_semieulerian on directed
graphs.

The wrapper previously imported the Rust kernel directly, which has
require_undirected. nx supports directed input. Wrapped to compose
from has_eulerian_path and is_eulerian (both already directed-aware).
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
def test_one_edge_digraph():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    gx = nx.DiGraph()
    gx.add_edge(0, 1)
    assert fnx.is_semieulerian(g) == nx.is_semieulerian(gx)
    assert fnx.is_semieulerian(g) is True


@needs_nx
def test_directed_eulerian_cycle_is_not_semieulerian():
    # A directed cycle has an Eulerian circuit, so it's NOT semi-Eulerian.
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(0, 1), (1, 2), (2, 0)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.is_semieulerian(g) == nx.is_semieulerian(gx)
    assert fnx.is_semieulerian(g) is False


@needs_nx
def test_directed_path_3_is_semieulerian():
    # 0 -> 1 -> 2: in/out conditions match Eulerian path but not circuit.
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.is_semieulerian(g) == nx.is_semieulerian(gx)
    assert fnx.is_semieulerian(g) is True


@needs_nx
def test_undirected_path_3_is_semieulerian():
    # Both endpoints have odd degree; matches semi-Eulerian.
    g = fnx.path_graph(3)
    gx = nx.path_graph(3)
    assert fnx.is_semieulerian(g) == nx.is_semieulerian(gx)
    assert fnx.is_semieulerian(g) is True


@needs_nx
def test_undirected_cycle_4_is_not_semieulerian():
    # Cycle has Eulerian circuit → not semi-Eulerian.
    g = fnx.cycle_graph(4)
    gx = nx.cycle_graph(4)
    assert fnx.is_semieulerian(g) == nx.is_semieulerian(gx)
    assert fnx.is_semieulerian(g) is False


@needs_nx
def test_directed_disconnected_is_not_semieulerian():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(0, 1), (2, 3)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.is_semieulerian(g) == nx.is_semieulerian(gx)
    assert fnx.is_semieulerian(g) is False
