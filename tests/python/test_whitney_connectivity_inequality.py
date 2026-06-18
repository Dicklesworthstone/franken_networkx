"""Whitney's inequality: node connectivity <= edge connectivity <= min degree.

Whitney's theorem bounds the connectivity measures: for any graph,
  kappa(G) <= lambda(G) <= delta(G),
where kappa is node connectivity, lambda is edge connectivity, and delta is the
minimum degree. This cross-checks node_connectivity, edge_connectivity, and the
degree sequence against each other, plus closed forms (K_n: all equal n-1;
cycle: all equal 2). Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(50))
def test_whitney_chain(seed):
    r = random.Random(seed)
    n = r.randint(4, 10)
    p = r.choice([0.3, 0.5, 0.7])
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < p]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    if not fnx.is_connected(g):
        pytest.skip("disconnected")

    kappa = fnx.node_connectivity(g)
    lam = fnx.edge_connectivity(g)
    delta = min(d for _, d in g.degree())
    # Whitney: kappa <= lambda <= delta.
    assert kappa <= lam <= delta


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_complete_graph_connectivity_closed_form(n):
    k = fnx.complete_graph(n)
    # K_n is (n-1)-node-connected and (n-1)-edge-connected; min degree n-1.
    assert fnx.node_connectivity(k) == n - 1
    assert fnx.edge_connectivity(k) == n - 1
    assert min(d for _, d in k.degree()) == n - 1


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_cycle_connectivity_closed_form(n):
    c = fnx.cycle_graph(n)
    # A cycle is 2-node-connected and 2-edge-connected.
    assert fnx.node_connectivity(c) == 2
    assert fnx.edge_connectivity(c) == 2


def test_tree_connectivity_is_one():
    # A tree (with >= 2 nodes) has node and edge connectivity 1 (every edge is a bridge).
    t = fnx.path_graph(6)
    assert fnx.node_connectivity(t) == 1
    assert fnx.edge_connectivity(t) == 1
