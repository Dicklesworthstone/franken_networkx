"""node/edge_disjoint_paths exception-contract parity with networkx.

When s and t are disconnected, networkx's disjoint-path generators raise
``NetworkXNoPath`` on iteration; the Rust fast path used to yield an empty
generator instead (silent divergence). The degenerate ``s == t`` case for
``node_disjoint_paths`` (nx yields one trivial path) was also wrong. Both are
now delegated to nx when the kernel returns no paths.

Found via the Menger disjoint-paths cross-check (the same metamorphic method
that surfaced the two P1 node_connectivity bugs).

br-r37-c1-xn2ho
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
from networkx.exception import NetworkXNoPath
import franken_networkx as fnx


def _outcome(fn, *args):
    try:
        return ("ok", list(fn(*args)))
    except Exception as exc:  # noqa: BLE001 — exception-type parity is the point
        return ("err", type(exc).__name__)


def test_disconnected_raises_networkx_no_path():
    g = fnx.Graph([(0, 1), (2, 3)])
    with pytest.raises(NetworkXNoPath):
        list(fnx.node_disjoint_paths(g, 0, 3))
    with pytest.raises(NetworkXNoPath):
        list(fnx.edge_disjoint_paths(g, 0, 3))


def test_directed_disconnected_raises():
    d = fnx.DiGraph([(0, 1), (1, 0), (2, 3)])
    with pytest.raises(NetworkXNoPath):
        list(fnx.node_disjoint_paths(d, 0, 3))
    with pytest.raises(NetworkXNoPath):
        list(fnx.edge_disjoint_paths(d, 0, 3))


def test_node_disjoint_same_source_sink_matches_networkx():
    g = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    assert _outcome(fnx.node_disjoint_paths, g, 0, 0) == _outcome(
        nx.node_disjoint_paths, ng, 0, 0
    )


@pytest.mark.parametrize("seed", range(70))
def test_exception_contract_and_count_parity(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    directed = r.random() < 0.5
    G = fnx.DiGraph() if directed else fnx.Graph()
    NG = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(range(n))
    NG.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and r.random() < 0.45:
                G.add_edge(u, v)
                NG.add_edge(u, v)
    for _ in range(3):
        s, t = r.sample(range(n), 2)
        for ff, nf in [
            (fnx.node_disjoint_paths, nx.node_disjoint_paths),
            (fnx.edge_disjoint_paths, nx.edge_disjoint_paths),
        ]:
            f_kind, f_val = _outcome(ff, G, s, t)
            n_kind, n_val = _outcome(nf, NG, s, t)
            assert f_kind == n_kind
            if f_kind == "ok":
                # Menger: same number of disjoint paths (order may differ).
                assert len(f_val) == len(n_val)
