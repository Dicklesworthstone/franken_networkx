"""Parity for ``edge_boundary`` and ``descendants_at_distance`` return types.

Bead br-r37-c1-ohxpp. Two return-type drifts:

- ``edge_boundary(G, nbunch1, nbunch2=None, ...)`` returned ``list``
  while nx returns ``generator`` — same iter contract issue as
  ``br-r37-c1-682kr``.
- ``descendants_at_distance(G, source, distance)`` returned
  ``frozenset`` while nx returns ``set``. Drop-in code calling
  ``.add()``/``.remove()`` on the result broke since frozenset is
  immutable.
"""

from __future__ import annotations

import types

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# edge_boundary
# ---------------------------------------------------------------------------

@needs_nx
def test_edge_boundary_returns_generator_like_networkx():
    G = fnx.path_graph(5)
    result = fnx.edge_boundary(G, [0, 1])
    assert isinstance(result, types.GeneratorType)


@needs_nx
def test_edge_boundary_values_match_networkx():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    fnx_edges = sorted([tuple(e) for e in fnx.edge_boundary(G, [0, 1, 2])])
    nx_edges = sorted([tuple(e) for e in nx.edge_boundary(GX, [0, 1, 2])])
    assert fnx_edges == nx_edges


@needs_nx
def test_edge_boundary_with_nbunch2():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = sorted([tuple(e) for e in fnx.edge_boundary(G, [0, 1], [2, 3])])
    n = sorted([tuple(e) for e in nx.edge_boundary(GX, [0, 1], [2, 3])])
    assert f == n


@needs_nx
def test_edge_boundary_empty():
    """When nbunch1 covers all nodes, no boundary edges exist."""
    G = fnx.path_graph(5)
    assert list(fnx.edge_boundary(G, [0, 1, 2, 3, 4])) == []


@needs_nx
def test_edge_boundary_data_path_also_generator():
    """The data=True branch goes through nx; it must also be a generator."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    G.add_edge(1, 2, weight=3.5)
    G.add_edge(0, 2, weight=4.5)
    result = fnx.edge_boundary(G, [0], data="weight")
    assert isinstance(result, types.GeneratorType)
    edges = list(result)
    # Expect (0,1) and (0,2) with weights.
    assert len(edges) == 2


@needs_nx
def test_edge_boundary_lazy_short_circuit():
    """next() returns one edge immediately."""
    G = fnx.complete_graph(20)
    gen = fnx.edge_boundary(G, list(range(5)))
    first = next(gen)
    assert isinstance(first, tuple)


# ---------------------------------------------------------------------------
# descendants_at_distance
# ---------------------------------------------------------------------------

@needs_nx
def test_descendants_at_distance_returns_set_not_frozenset():
    G = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    result = fnx.descendants_at_distance(G, 0, 2)
    assert type(result) is set
    assert result == {2}


@needs_nx
def test_descendants_at_distance_supports_add():
    """Drop-in code must be able to call .add() on the result."""
    G = fnx.DiGraph([(0, 1), (1, 2)])
    result = fnx.descendants_at_distance(G, 0, 1)
    result.add(99)
    assert 99 in result


@needs_nx
def test_descendants_at_distance_supports_remove():
    G = fnx.DiGraph([(0, 1), (0, 2)])
    result = fnx.descendants_at_distance(G, 0, 1)
    result.remove(next(iter(result)))


@needs_nx
def test_descendants_at_distance_values_match_networkx():
    G = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
    GX = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
    for d in range(4):
        assert fnx.descendants_at_distance(G, 0, d) == nx.descendants_at_distance(GX, 0, d)


@needs_nx
def test_descendants_at_distance_empty_when_distance_too_far():
    G = fnx.DiGraph([(0, 1)])
    result = fnx.descendants_at_distance(G, 0, 99)
    assert type(result) is set
    assert result == set()
