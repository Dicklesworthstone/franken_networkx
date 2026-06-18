"""Exception-contract parity: fnx raises the same way networkx does.

Silent exception-contract divergence is a real bug class — the
node/edge_disjoint_paths ``NetworkXNoPath`` regression (xn2ho) yielded an empty
generator where nx raised. This sweeps missing-node arguments and
structural-precondition violations, asserting fnx and networkx agree on whether
a call succeeds AND on the raised exception *type*.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_MISSING = 99


def _outcome(fn, *args, **kwargs):
    try:
        r = fn(*args, **kwargs)
        if hasattr(r, "__iter__") and not isinstance(r, (int, float, dict, bool, str)):
            r = list(r)
        return ("ok", None)
    except Exception as exc:  # noqa: BLE001 — exception-type parity is the point
        return ("err", type(exc).__name__)


_MISSING_NODE_CASES = [
    ("shortest_path_src", lambda L, G: L.shortest_path(G, _MISSING, 1)),
    ("shortest_path_tgt", lambda L, G: L.shortest_path(G, 0, _MISSING)),
    ("dijkstra_path", lambda L, G: L.dijkstra_path(G, _MISSING, 1)),
    ("bfs_tree", lambda L, G: L.bfs_tree(G, _MISSING)),
    ("dfs_tree", lambda L, G: L.dfs_tree(G, _MISSING)),
    ("ego_graph", lambda L, G: L.ego_graph(G, _MISSING)),
    ("eccentricity", lambda L, G: L.eccentricity(G, _MISSING)),
    ("clustering", lambda L, G: L.clustering(G, _MISSING)),
    ("has_path", lambda L, G: L.has_path(G, _MISSING, 1)),
    ("single_source_dijkstra", lambda L, G: L.single_source_dijkstra_path_length(G, _MISSING)),
    ("dijkstra_pred_dist", lambda L, G: L.dijkstra_predecessor_and_distance(G, _MISSING)),
]


@pytest.mark.parametrize("name,call", _MISSING_NODE_CASES)
def test_missing_node_argument_contract(name, call):
    fg = fnx.Graph([(0, 1), (1, 2), (2, 3), (0, 3)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 3), (0, 3)])
    assert _outcome(call, fnx, fg) == _outcome(call, nx, ng)


_STRUCTURAL_CASES = [
    ("topological_sort", lambda L, G: L.topological_sort(G)),
    ("dag_longest_path", lambda L, G: L.dag_longest_path(G)),
    ("eulerian_circuit", lambda L, G: L.eulerian_circuit(G)),
    ("find_cycle", lambda L, G: L.find_cycle(G)),
    ("diameter", lambda L, G: L.diameter(G)),
    ("center", lambda L, G: L.center(G)),
    ("average_shortest_path_length", lambda L, G: L.average_shortest_path_length(G)),
    ("is_arborescence", lambda L, G: L.is_arborescence(G)),
    ("immediate_dominators", lambda L, G: L.immediate_dominators(G, 0)),
]


@pytest.mark.parametrize("name,call", _STRUCTURAL_CASES)
@pytest.mark.parametrize("seed", range(20))
def test_structural_precondition_contract(name, call, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    directed = r.random() < 0.4
    fg = fnx.DiGraph() if directed else fnx.Graph()
    ng = nx.DiGraph() if directed else nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and r.random() < 0.45:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    assert _outcome(call, fnx, fg) == _outcome(call, nx, ng)
