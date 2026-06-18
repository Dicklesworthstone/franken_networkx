"""No-path-between-s,t exception-contract parity across s,t functions.

When s and t lie in different components, networkx functions either raise
``NetworkXNoPath`` (path finders) or return a defined value (flow=0,
connectivity=0). The Rust fast paths must reproduce that exact contract — the
node/edge_disjoint_paths regression (xn2ho) was precisely a function that
returned empty instead of raising here. This sweeps the s,t family to confirm
the bug is isolated and stays fixed.

No mocks: real fnx and real networkx on a disconnected graph.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms.connectivity as fc
import networkx.algorithms.connectivity as nc

_S, _T = 0, 4  # different components below


def _disconnected_undirected():
    return (
        fnx.Graph([(0, 1), (1, 2), (3, 4), (4, 5)]),
        nx.Graph([(0, 1), (1, 2), (3, 4), (4, 5)]),
    )


def _disconnected_directed():
    return (
        fnx.DiGraph([(0, 1), (1, 2), (3, 4), (4, 5)]),
        nx.DiGraph([(0, 1), (1, 2), (3, 4), (4, 5)]),
    )


def _outcome(fn, *args):
    try:
        r = fn(*args)
        if hasattr(r, "__iter__") and not isinstance(r, (int, float, str, dict)):
            r = list(r)
        return ("ok", None)
    except Exception as exc:  # noqa: BLE001 — exception-type parity is the point
        return ("err", type(exc).__name__)


_UNDIRECTED_CASES = [
    ("all_simple_paths", lambda L, G: list(L.all_simple_paths(G, _S, _T))),
    ("all_shortest_paths", lambda L, G: list(L.all_shortest_paths(G, _S, _T))),
    ("shortest_simple_paths", lambda L, G: list(L.shortest_simple_paths(G, _S, _T))),
    ("bidirectional_dijkstra", lambda L, G: L.bidirectional_dijkstra(G, _S, _T)),
    ("dijkstra_path", lambda L, G: L.dijkstra_path(G, _S, _T)),
    ("astar_path", lambda L, G: L.astar_path(G, _S, _T)),
    ("resistance_distance", lambda L, G: L.resistance_distance(G, _S, _T)),
    ("has_path", lambda L, G: L.has_path(G, _S, _T)),
    ("node_disjoint_paths", lambda L, G: list(L.node_disjoint_paths(G, _S, _T))),
    ("edge_disjoint_paths", lambda L, G: list(L.edge_disjoint_paths(G, _S, _T))),
]

_CONN_CASES = [
    ("local_node_connectivity", fc.local_node_connectivity, nc.local_node_connectivity),
    ("local_edge_connectivity", fc.local_edge_connectivity, nc.local_edge_connectivity),
    ("minimum_st_node_cut", fc.minimum_st_node_cut, nc.minimum_st_node_cut),
    ("minimum_st_edge_cut", fc.minimum_st_edge_cut, nc.minimum_st_edge_cut),
]


@pytest.mark.parametrize("name,call", _UNDIRECTED_CASES)
def test_undirected_no_path_contract(name, call):
    fg, ng = _disconnected_undirected()
    assert _outcome(call, fnx, fg) == _outcome(call, nx, ng)


@pytest.mark.parametrize("name,ff,nf", _CONN_CASES)
def test_connectivity_no_path_contract(name, ff, nf):
    fg, ng = _disconnected_undirected()
    assert _outcome(ff, fg, _S, _T) == _outcome(nf, ng, _S, _T)


@pytest.mark.parametrize("name,call", [
    ("maximum_flow_value", lambda L, G: L.maximum_flow_value(G, _S, _T)),
    ("minimum_cut", lambda L, G: L.minimum_cut(G, _S, _T)),
])
def test_directed_flow_no_path_contract(name, call):
    fd, nd = _disconnected_directed()
    assert _outcome(call, fnx, fd) == _outcome(call, nx, nd)
