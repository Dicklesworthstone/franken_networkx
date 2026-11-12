"""Parity for dijkstra_path_length / bellman_ford_path_length /
all_shortest_paths target-side and bfs_layers iterable on unhashable inputs.

Bead br-r37-c1-omjmu (seventh follow-up to the unhashable-node series).

Drifts found in the post-mz7g4 probe:

  dijkstra_path_length(target=...)        fnx: NetworkXNoPath  nx: TypeError
  bellman_ford_path_length(target=...)    fnx: NetworkXNoPath  nx: TypeError
  all_shortest_paths(target=...)          fnx: NodeNotFound    nx: TypeError
  bfs_layers(sources=[unhashable])        fnx: <silent ok>     nx: TypeError

The first three need ``hash(target)`` BEFORE the ``target not in G``
silent-False check.  ``bfs_layers`` needs hash-validation of every
source in the iterable (nx's inner loop builds a dict keyed on
sources, raising TypeError on the first unhashable one).
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

UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]


# ---------------------------------------------------------------------------
# *_path_length(target=unhashable) → TypeError parity
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_dijkstra_path_length_unhashable_target_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.dijkstra_path_length(G, 1, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.dijkstra_path_length(GX, 1, val)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bellman_ford_path_length_unhashable_target_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.bellman_ford_path_length(G, 1, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.bellman_ford_path_length(GX, 1, val)


# ---------------------------------------------------------------------------
# all_shortest_paths(target=unhashable) → TypeError parity
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_all_shortest_paths_unhashable_target_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(fnx.all_shortest_paths(G, 1, val))
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(nx.all_shortest_paths(GX, 1, val))


# ---------------------------------------------------------------------------
# bfs_layers(sources=[unhashable]) → TypeError parity
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bfs_layers_iterable_with_unhashable_typeerror(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(fnx.bfs_layers(G, [val]))
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(nx.bfs_layers(GX, [val]))


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bfs_layers_iterable_mixed_hashable_unhashable_typeerror(val):
    """Even with one valid hashable source, an unhashable in the
    iterable still raises TypeError (matches nx)."""
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(fnx.bfs_layers(G, [1, val]))
    with pytest.raises(TypeError, match=r"unhashable type"):
        list(nx.bfs_layers(GX, [1, val]))


# ---------------------------------------------------------------------------
# Regressions — hashable / scalar source / hashable-but-missing inputs
# ---------------------------------------------------------------------------

@needs_nx
def test_dijkstra_path_length_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert fnx.dijkstra_path_length(G, 1, 3) == nx.dijkstra_path_length(GX, 1, 3)


@needs_nx
def test_bellman_ford_path_length_hashable_unchanged():
    G = fnx.Graph([(1, 2, {"weight": 2.0}), (2, 3, {"weight": 1.0})])
    GX = nx.Graph([(1, 2, {"weight": 2.0}), (2, 3, {"weight": 1.0})])
    assert fnx.bellman_ford_path_length(G, 1, 3) == nx.bellman_ford_path_length(GX, 1, 3)


@needs_nx
def test_all_shortest_paths_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (1, 3)])
    GX = nx.Graph([(1, 2), (2, 3), (1, 3)])
    f = sorted(map(tuple, fnx.all_shortest_paths(G, 1, 3)))
    n = sorted(map(tuple, nx.all_shortest_paths(GX, 1, 3)))
    assert f == n


@needs_nx
def test_bfs_layers_iterable_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    f = [list(layer) for layer in fnx.bfs_layers(G, [1])]
    n = [list(layer) for layer in nx.bfs_layers(GX, [1])]
    assert f == n


@needs_nx
def test_bfs_layers_single_node_hashable_unchanged():
    """Scalar (single-node) source still works."""
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = [list(layer) for layer in fnx.bfs_layers(G, 1)]
    n = [list(layer) for layer in nx.bfs_layers(GX, 1)]
    assert f == n


@needs_nx
def test_dijkstra_path_length_missing_target_still_no_path():
    """Missing-but-hashable target still raises NetworkXNoPath."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXNoPath):
        fnx.dijkstra_path_length(G, 1, 99)
    with pytest.raises(nx.NetworkXNoPath):
        nx.dijkstra_path_length(GX, 1, 99)
