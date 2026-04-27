"""Parity for local_node_connectivity (was broken on all inputs)
plus message-wording drift on single_source_dijkstra /
single_source_bellman_ford / multi_source_dijkstra.

Bead br-r37-c1-k4pod.

Defect 1 — ``local_node_connectivity`` raised ``TypeError("got an
unexpected keyword argument 'cutoff'")`` for ALL inputs because the
wrapper called fnx's own ``node_connectivity(G, s=s, t=t,
cutoff=cutoff)`` which doesn't accept ``cutoff``.  nx's
``local_node_connectivity`` uses max-flow with cutoff support and
lives in ``networkx.algorithms.connectivity`` — delegate there.

Defect 2 — single_source_dijkstra / single_source_bellman_ford /
multi_source_dijkstra raised ``NodeNotFound("Source '99' is not
in G")`` (note the quoted-repr value) when the Rust binding's
internal error path fired.  nx's exact wording differs per
function::

    single_source_dijkstra      "Node {s} not found in graph"
    single_source_bellman_ford  "Source {s} not in G"
    multi_source_dijkstra       "Node {s} not found in graph"

Drop-in users matching on the message string (e.g. for log
filtering) break otherwise.
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
# local_node_connectivity — was unconditionally broken
# ---------------------------------------------------------------------------

@needs_nx
def test_local_node_connectivity_basic_works():
    """Pre-fix this raised TypeError for ALL inputs."""
    from networkx.algorithms.connectivity import local_node_connectivity as nx_lnc
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert fnx.local_node_connectivity(G, 1, 4) == nx_lnc(GX, 1, 4)


@needs_nx
def test_local_node_connectivity_with_cutoff():
    from networkx.algorithms.connectivity import local_node_connectivity as nx_lnc
    G = fnx.Graph([(1, 2), (2, 3), (3, 4), (1, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4), (1, 4)])
    assert fnx.local_node_connectivity(G, 1, 4, cutoff=1) == nx_lnc(GX, 1, 4, cutoff=1)


@needs_nx
def test_local_node_connectivity_missing_node_raises_keyerror():
    """nx raises a bare KeyError(99) when the node isn't in the
    auxiliary digraph.  Match it."""
    from networkx.algorithms.connectivity import local_node_connectivity as nx_lnc
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(KeyError):
        fnx.local_node_connectivity(G, 99, 2)
    with pytest.raises(KeyError):
        nx_lnc(GX, 99, 2)


# ---------------------------------------------------------------------------
# Message-wording parity for single/multi source path fns
# ---------------------------------------------------------------------------

@needs_nx
def test_single_source_dijkstra_missing_source_message_matches_nx():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Node 99 not found in graph"):
        fnx.single_source_dijkstra(G, 99)
    with pytest.raises(nx.NodeNotFound, match=r"Node 99 not found in graph"):
        nx.single_source_dijkstra(GX, 99)


@needs_nx
def test_single_source_bellman_ford_missing_source_message_matches_nx():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Source 99 not in G"):
        fnx.single_source_bellman_ford(G, 99)
    with pytest.raises(nx.NodeNotFound, match=r"Source 99 not in G"):
        nx.single_source_bellman_ford(GX, 99)


@needs_nx
def test_multi_source_dijkstra_missing_source_message_matches_nx():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Node 99 not found in graph"):
        fnx.multi_source_dijkstra(G, [99])
    with pytest.raises(nx.NodeNotFound, match=r"Node 99 not found in graph"):
        nx.multi_source_dijkstra(GX, [99])


@needs_nx
def test_multi_source_dijkstra_mixed_missing_source_message_matches_nx():
    """First missing source in the iterable triggers the error."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Node 99 not found in graph"):
        fnx.multi_source_dijkstra(G, [1, 99])
    with pytest.raises(nx.NodeNotFound, match=r"Node 99 not found in graph"):
        nx.multi_source_dijkstra(GX, [1, 99])


# ---------------------------------------------------------------------------
# Regressions — hashable inputs unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_single_source_dijkstra_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.single_source_dijkstra(G, 1)
    n = nx.single_source_dijkstra(GX, 1)
    assert dict(f[0]) == dict(n[0]) and {k: list(v) for k, v in f[1].items()} == {k: list(v) for k, v in n[1].items()}


@needs_nx
def test_single_source_bellman_ford_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.single_source_bellman_ford(G, 1)
    n = nx.single_source_bellman_ford(GX, 1)
    assert dict(f[0]) == dict(n[0])


@needs_nx
def test_multi_source_dijkstra_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.multi_source_dijkstra(G, [1])
    n = nx.multi_source_dijkstra(GX, [1])
    assert dict(f[0]) == dict(n[0])
