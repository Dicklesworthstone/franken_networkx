"""br-r37-c1-2fsuy: regression tests for native has_cycle.

The wrapper previously delegated to nx.algorithms.dag.has_cycle.
Replaced with `not is_directed_acyclic_graph(G)` which uses the
existing native Rust DAG check.
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


def test_has_cycle_detects_simple_cycle():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 0)
    assert fnx.algorithms.dag.has_cycle(g) is True


def test_has_cycle_dag_returns_false():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(0, 2)
    assert fnx.algorithms.dag.has_cycle(g) is False


def test_has_cycle_empty_dag_returns_false():
    g = fnx.DiGraph()
    assert fnx.algorithms.dag.has_cycle(g) is False


def test_has_cycle_self_loop_is_cycle():
    g = fnx.DiGraph()
    g.add_edge(0, 0)
    assert fnx.algorithms.dag.has_cycle(g) is True


def test_has_cycle_rejects_undirected():
    g = fnx.Graph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.algorithms.dag.has_cycle(g)


@needs_nx
def test_has_cycle_matches_nx_on_cycle_fixtures():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 1)]:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    assert fnx.algorithms.dag.has_cycle(fg) == nx.algorithms.dag.has_cycle(ng)


@needs_nx
def test_has_cycle_matches_nx_on_dag_fixtures():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v in [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    assert fnx.algorithms.dag.has_cycle(fg) == nx.algorithms.dag.has_cycle(ng)
