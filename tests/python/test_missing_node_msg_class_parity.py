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


@needs_nx
@pytest.mark.parametrize(
    "kwargs",
    [
        {"weight": "weight"},
        {"weight": "weight", "method": "bellman-ford"},
    ],
)
def test_all_shortest_paths_weighted_missing_source_message(kwargs):
    G = fnx.Graph()
    G.add_edge("a", "b", weight=1)
    GX = nx.Graph()
    GX.add_edge("a", "b", weight=1)

    with pytest.raises(fnx.NodeNotFound) as fnx_exc:
        list(fnx.all_shortest_paths(G, "missing", "b", **kwargs))
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        list(nx.all_shortest_paths(GX, "missing", "b", **kwargs))

    assert str(fnx_exc.value) == "Node missing is not found in the graph"
    assert str(nx_exc.value) == "Node missing is not found in the graph"


@needs_nx
@pytest.mark.parametrize(
    "kwargs",
    [
        {"weight": "weight"},
        {"weight": "weight", "method": "bellman-ford"},
    ],
)
@pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
def test_all_shortest_paths_weighted_no_path_message(graph_cls, kwargs):
    G = graph_cls()
    G.add_edge("a", "b", weight=1)
    G.add_node("c")
    GX = getattr(nx, graph_cls.__name__)()
    GX.add_edge("a", "b", weight=1)
    GX.add_node("c")

    with pytest.raises(fnx.NetworkXNoPath) as fnx_exc:
        list(fnx.all_shortest_paths(G, "a", "c", **kwargs))
    with pytest.raises(nx.NetworkXNoPath) as nx_exc:
        list(nx.all_shortest_paths(GX, "a", "c", **kwargs))

    assert str(fnx_exc.value) == "Target c cannot be reached from given sources"
    assert str(nx_exc.value) == "Target c cannot be reached from given sources"


@needs_nx
@pytest.mark.parametrize(
    "kwargs",
    [
        {"weight": "weight"},
        {"weight": "weight", "method": "dijkstra"},
        {"weight": "weight", "method": "bellman-ford"},
    ],
)
def test_all_shortest_paths_weighted_missing_target_message(kwargs):
    G = fnx.Graph()
    G.add_edge("a", "b", weight=1)
    GX = nx.Graph()
    GX.add_edge("a", "b", weight=1)

    with pytest.raises(fnx.NetworkXNoPath) as fnx_exc:
        list(fnx.all_shortest_paths(G, "a", "missing", **kwargs))
    with pytest.raises(nx.NetworkXNoPath) as nx_exc:
        list(nx.all_shortest_paths(GX, "a", "missing", **kwargs))

    assert str(fnx_exc.value) == "Target missing cannot be reached from given sources"
    assert str(nx_exc.value) == "Target missing cannot be reached from given sources"


@needs_nx
def test_raw_all_shortest_paths_string_error_messages_match_nx():
    G = fnx.Graph()
    G.add_edge("a", "b", weight=1)
    G.add_node("c")
    GX = nx.Graph()
    GX.add_edge("a", "b", weight=1)
    GX.add_node("c")

    cases = [
        (
            lambda: list(fnx._raw_all_shortest_paths(G, "missing", "b")),
            lambda: list(nx.all_shortest_paths(GX, "missing", "b")),
            fnx.NodeNotFound,
            nx.NodeNotFound,
        ),
        (
            lambda: list(fnx._raw_all_shortest_paths(G, "missing", "b", weight="weight")),
            lambda: list(nx.all_shortest_paths(GX, "missing", "b", weight="weight")),
            fnx.NodeNotFound,
            nx.NodeNotFound,
        ),
        (
            lambda: list(fnx._raw_all_shortest_paths(G, "a", "missing")),
            lambda: list(nx.all_shortest_paths(GX, "a", "missing")),
            fnx.NetworkXNoPath,
            nx.NetworkXNoPath,
        ),
        (
            lambda: list(fnx._raw_all_shortest_paths(G, "a", "c", weight="weight")),
            lambda: list(nx.all_shortest_paths(GX, "a", "c", weight="weight")),
            fnx.NetworkXNoPath,
            nx.NetworkXNoPath,
        ),
    ]

    for fnx_call, nx_call, fnx_error, nx_error in cases:
        with pytest.raises(fnx_error) as fnx_exc:
            fnx_call()
        with pytest.raises(nx_error) as nx_exc:
            nx_call()

        assert str(fnx_exc.value) == str(nx_exc.value)


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
