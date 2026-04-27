"""Parity for shortest_simple_paths missing-source/target wording.

Bead br-r37-c1-hpeix.

Pre-fix the Rust binding emitted::

    NodeNotFound: Source 99 is not in G
    NodeNotFound: Target 99 is not in G

…while nx uses lowercase title-less wording matching its
underlying ``_bidirectional_shortest_path`` helper::

    NodeNotFound: source node 99 not in graph
    NodeNotFound: target node 99 not in graph

Drop-in code that matches on the message string (logging filters,
test assertions) breaks otherwise.
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
def test_shortest_simple_paths_missing_source_message():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NodeNotFound, match=r"^source node 99 not in graph$"):
        list(fnx.shortest_simple_paths(G, 99, 2))
    with pytest.raises(nx.NodeNotFound, match=r"^source node 99 not in graph$"):
        list(nx.shortest_simple_paths(GX, 99, 2))


@needs_nx
def test_shortest_simple_paths_missing_target_message():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NodeNotFound, match=r"^target node 99 not in graph$"):
        list(fnx.shortest_simple_paths(G, 1, 99))
    with pytest.raises(nx.NodeNotFound, match=r"^target node 99 not in graph$"):
        list(nx.shortest_simple_paths(GX, 1, 99))


@needs_nx
def test_shortest_simple_paths_hashable_unchanged():
    """Real run still yields paths in length order."""
    G = fnx.Graph([(1, 2), (2, 3), (1, 3)])
    GX = nx.Graph([(1, 2), (2, 3), (1, 3)])
    f = sorted(map(tuple, fnx.shortest_simple_paths(G, 1, 3)), key=len)
    n = sorted(map(tuple, nx.shortest_simple_paths(GX, 1, 3)), key=len)
    assert f == n


@needs_nx
def test_shortest_simple_paths_callable_weight_unchanged():
    """Callable weight delegates to nx — verify it still works."""
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = list(fnx.shortest_simple_paths(G, 1, 3, weight=lambda u, v, d: 1.0))
    n = list(nx.shortest_simple_paths(GX, 1, 3, weight=lambda u, v, d: 1.0))
    assert f == n


@needs_nx
def test_shortest_simple_paths_multigraph_still_not_implemented():
    """Multigraph guard stays in place (br-r37-c1-682kr)."""
    MG = fnx.MultiGraph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        list(fnx.shortest_simple_paths(MG, 1, 3))
