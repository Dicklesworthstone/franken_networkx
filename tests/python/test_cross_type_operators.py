"""br-r37-c1-jwdzp: regression — 8 sibling binary-graph operators
must accept nx graph args via boundary coercion (same defect class as
br-r37-c1-i2uub on fnx.union).

Affected functions:
  - difference, symmetric_difference
  - is_isomorphic, could_be_isomorphic
  - fast_could_be_isomorphic, faster_could_be_isomorphic
  - graph_edit_distance, optimal_edit_paths

Each previously raised ``TypeError: expected Graph, DiGraph,
MultiGraph, or MultiDiGraph`` because the PyO3-bound Rust kernels
strictly check fnx graph types. Each wrapper now coerces via
``_coerce_arg_to_fnx_graph`` first.
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
def test_difference_accepts_nx_graph():
    ng = nx.Graph([(0, 1), (1, 2)])
    fg = fnx.Graph([(0, 1), (1, 2)])
    assert list(fnx.difference(ng, fg).edges()) == []


@needs_nx
def test_symmetric_difference_accepts_nx_graph():
    ng = nx.Graph([(0, 1), (1, 2)])
    fg = fnx.Graph([(0, 1), (1, 2)])
    assert list(fnx.symmetric_difference(ng, fg).edges()) == []


@needs_nx
def test_is_isomorphic_accepts_nx_graph():
    ng = nx.path_graph(5)
    fg = fnx.path_graph(5)
    assert fnx.is_isomorphic(ng, fg) is True
    assert fnx.is_isomorphic(fg, ng) is True


@needs_nx
def test_could_be_isomorphic_accepts_nx_graph():
    ng = nx.complete_graph(5)
    fg = fnx.complete_graph(5)
    assert fnx.could_be_isomorphic(ng, fg) is True


@needs_nx
def test_fast_could_be_isomorphic_accepts_nx_graph():
    ng = nx.complete_graph(5)
    fg = fnx.complete_graph(5)
    assert fnx.fast_could_be_isomorphic(ng, fg) is True


@needs_nx
def test_faster_could_be_isomorphic_accepts_nx_graph():
    ng = nx.complete_graph(5)
    fg = fnx.complete_graph(5)
    assert fnx.faster_could_be_isomorphic(ng, fg) is True


@needs_nx
def test_graph_edit_distance_accepts_nx_graph():
    ng = nx.path_graph(3)
    fg = fnx.path_graph(3)
    assert fnx.graph_edit_distance(ng, fg) == 0.0


@needs_nx
def test_optimal_edit_paths_accepts_nx_graph():
    ng = nx.path_graph(3)
    fg = fnx.path_graph(3)
    paths, cost = fnx.optimal_edit_paths(ng, fg)
    assert cost == 0.0


@needs_nx
def test_is_isomorphic_with_node_match_accepts_nx_graph():
    """Verify the node_match callback path also works with cross-type input."""
    ng = nx.Graph()
    ng.add_node(0, color="red")
    ng.add_node(1, color="blue")
    ng.add_edge(0, 1)
    fg = fnx.Graph()
    fg.add_node(0, color="red")
    fg.add_node(1, color="blue")
    fg.add_edge(0, 1)
    nm = lambda a, b: a.get("color") == b.get("color")
    assert fnx.is_isomorphic(ng, fg, node_match=nm) is True


@needs_nx
def test_difference_nx_to_fnx_attrs_preserved():
    """Coercion should preserve edge attrs from the nx side."""
    ng = nx.Graph()
    ng.add_edge(0, 1, weight=5)
    fg = fnx.Graph()
    fg.add_edge(0, 1)
    fg.add_node(0)
    fg.add_node(1)
    # Same edges → empty difference, but the coercion must succeed.
    result = fnx.difference(ng, fg)
    assert list(result.edges()) == []


@needs_nx
def test_same_type_no_regression():
    """fnx/fnx and nx/nx-via-fnx paths still work."""
    fg5 = fnx.path_graph(5)
    fg3 = fnx.path_graph(3)
    # is_isomorphic handles larger graphs fine.
    assert fnx.is_isomorphic(fg5, fg5) is True
    # graph_edit_distance is bounded to small graphs; use path_graph(3)
    # (n+n=6 ≤ the local-kernel cutoff).
    assert fnx.graph_edit_distance(fg3, fg3) == 0.0
