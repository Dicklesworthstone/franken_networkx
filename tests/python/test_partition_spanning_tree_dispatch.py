"""br-r37-c1-ity9g: regression tests for partition_spanning_tree on
non-simple-undirected graph classes."""

from __future__ import annotations

import json

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _build(cls, edges):
    g = cls()
    for u, v in edges:
        g.add_edge(u, v, weight=1)
    return g


@needs_nx
@pytest.mark.parametrize(
    "cls_fnx,cls_nx",
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_partition_spanning_tree_accepts_non_simple(cls_fnx, cls_nx):
    edges = [(0, 1), (1, 2)]
    fg = _build(cls_fnx, edges)
    ng = _build(cls_nx, edges)
    fr = fnx.partition_spanning_tree(fg)
    nr = nx.partition_spanning_tree(ng)
    assert sorted((u, v) for u, v in fr.edges()) == sorted((u, v) for u, v in nr.edges())


@needs_nx
def test_partition_spanning_tree_simple_undirected_still_works():
    edges = [(0, 1), (1, 2), (2, 0)]  # triangle
    fg = _build(fnx.Graph, edges)
    ng = _build(nx.Graph, edges)
    fr = fnx.partition_spanning_tree(fg)
    nr = nx.partition_spanning_tree(ng)
    # Compare as edge sets (sort tuples for deterministic compare).
    assert sorted(tuple(sorted(e)) for e in fr.edges()) == sorted(tuple(sorted(e)) for e in nr.edges())


@needs_nx
@pytest.mark.parametrize("minimum", [False, True])
@pytest.mark.parametrize("first_negative", [False, True])
def test_partition_spanning_tree_signed_zero_keeps_live_oracle_order(minimum, first_negative):
    """Python compares signed zeros as equal before the insertion-order tie."""
    graphs = [fnx.Graph(), nx.Graph()]
    for graph in graphs:
        graph.add_nodes_from(range(4))
        graph.add_weighted_edges_from([
            (0, 2, -0.0 if first_negative else 0.0),
            (0, 1, 0.0 if first_negative else -0.0),
            (2, 3, 0.0),
            (1, 3, 0.0),
        ])
    actual = fnx.partition_spanning_tree(graphs[0], minimum=minimum)
    expected = nx.partition_spanning_tree(graphs[1], minimum=minimum)
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    # JSON preserves both edge order and the original signed attributes.
    assert json.dumps(list(actual.edges(data=True))) == json.dumps(list(expected.edges(data=True)))


@needs_nx
@pytest.mark.parametrize("minimum", [False, True])
@pytest.mark.parametrize("infinity", [float("inf"), -float("inf")])
def test_partition_spanning_tree_infinite_weight_keeps_live_oracle_choice(minimum, infinity):
    graphs = [fnx.Graph(), nx.Graph()]
    for graph in graphs:
        graph.add_weighted_edges_from([(0, 1, infinity), (1, 2, 2.0), (0, 2, 3.0)])
    actual = fnx.partition_spanning_tree(graphs[0], minimum=minimum)
    expected = nx.partition_spanning_tree(graphs[1], minimum=minimum)
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    assert json.dumps(list(actual.edges(data=True))) == json.dumps(list(expected.edges(data=True)))
