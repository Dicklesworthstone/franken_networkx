"""Parity for missing-source / missing-target wording and class
across single_source_bellman_ford_path / _path_length /
all_shortest_paths / bfs_layers.

Bead br-r37-c1-jxvsu.

Probe after k4pod surfaced four more drifts:

  single_source_bellman_ford_path        msg: 'Source \'99\' is not in G' vs 'Source 99 not in G'
  single_source_bellman_ford_path_length msg: same quoted-repr drift
  all_shortest_paths missing src         msg: 'Source node 99 is not in G' vs 'Source 99 not in G'
  all_shortest_paths missing tgt         CLASS: NodeNotFound vs NetworkXNoPath
  bfs_layers missing src                 fnx: <silent yields nothing>  nx: NetworkXError

The first three are quoted-repr / extra-word wording drifts in the
Rust bindings.  The fourth is a class drift: nx separates 'source
not present' (NodeNotFound) from 'no reachable target'
(NetworkXNoPath).  The fifth is fnx silently producing no output
where nx properly raises.
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


# ---------------------------------------------------------------------------
# single_source_bellman_ford_path / _path_length — message wording
# ---------------------------------------------------------------------------

@needs_nx
def test_single_source_bellman_ford_path_missing_source_message():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"^Source 99 not in G$"):
        fnx.single_source_bellman_ford_path(G, 99)
    with pytest.raises(nx.NodeNotFound, match=r"^Source 99 not in G$"):
        nx.single_source_bellman_ford_path(GX, 99)


@needs_nx
def test_single_source_bellman_ford_path_length_missing_source_message():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"^Source 99 not in G$"):
        fnx.single_source_bellman_ford_path_length(G, 99)
    with pytest.raises(nx.NodeNotFound, match=r"^Source 99 not in G$"):
        nx.single_source_bellman_ford_path_length(GX, 99)


# ---------------------------------------------------------------------------
# all_shortest_paths — wording for source, class for target
# ---------------------------------------------------------------------------

@needs_nx
def test_all_shortest_paths_missing_source_message():
    """Was emitting 'Source node 99 is not in G' (extra 'node' word)."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"^Source 99 not in G$"):
        list(fnx.all_shortest_paths(G, 99, 2))
    with pytest.raises(nx.NodeNotFound, match=r"^Source 99 not in G$"):
        list(nx.all_shortest_paths(GX, 99, 2))


@needs_nx
def test_all_shortest_paths_missing_target_raises_no_path():
    """Was raising NodeNotFound; nx raises NetworkXNoPath when the
    target isn't reachable (or absent)."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXNoPath, match=r"Target 99 cannot be reached"):
        list(fnx.all_shortest_paths(G, 1, 99))
    with pytest.raises(nx.NetworkXNoPath, match=r"Target 99 cannot be reached"):
        list(nx.all_shortest_paths(GX, 1, 99))


# ---------------------------------------------------------------------------
# bfs_layers — missing source raises NetworkXError
# ---------------------------------------------------------------------------

@needs_nx
def test_bfs_layers_missing_source_raises_networkxerror():
    """Pre-fix fnx silently yielded an empty layers iter; nx raises
    NetworkXError('The node X is not in the graph.')."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXError, match=r"The node 99 is not in the graph"):
        list(fnx.bfs_layers(G, [99]))
    with pytest.raises(nx.NetworkXError, match=r"The node 99 is not in the graph"):
        list(nx.bfs_layers(GX, [99]))


@needs_nx
def test_bfs_layers_missing_source_in_iterable_mixed():
    """One of multiple sources missing — first missing one triggers."""
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXError, match=r"The node 99 is not in the graph"):
        list(fnx.bfs_layers(G, [1, 99]))
    with pytest.raises(nx.NetworkXError, match=r"The node 99 is not in the graph"):
        list(nx.bfs_layers(GX, [1, 99]))


# ---------------------------------------------------------------------------
# Regressions — hashable / valid inputs unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_single_source_bellman_ford_path_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert dict(fnx.single_source_bellman_ford_path(G, 1)) == dict(nx.single_source_bellman_ford_path(GX, 1))


@needs_nx
def test_single_source_bellman_ford_path_length_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert dict(fnx.single_source_bellman_ford_path_length(G, 1)) == dict(nx.single_source_bellman_ford_path_length(GX, 1))


@needs_nx
def test_all_shortest_paths_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (1, 3)])
    GX = nx.Graph([(1, 2), (2, 3), (1, 3)])
    f = sorted(map(tuple, fnx.all_shortest_paths(G, 1, 3)))
    n = sorted(map(tuple, nx.all_shortest_paths(GX, 1, 3)))
    assert f == n


@needs_nx
def test_bfs_layers_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    f = [list(layer) for layer in fnx.bfs_layers(G, [1])]
    n = [list(layer) for layer in nx.bfs_layers(GX, [1])]
    assert f == n


@needs_nx
def test_bfs_layers_single_node_source_unchanged():
    """Scalar (not iterable) source still works after the missing-
    member check restructure."""
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = [list(layer) for layer in fnx.bfs_layers(G, 1)]
    n = [list(layer) for layer in nx.bfs_layers(GX, 1)]
    assert f == n
