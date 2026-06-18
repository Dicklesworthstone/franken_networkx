"""Oracle-free invariants for max-flow, centrality and spectral metrics.

Asserts properties that hold by definition/theorem (no networkx oracle):

* a maximum flow respects capacities, conserves flow at interior nodes,
  and its value equals the net flow out of the source
* pagerank sums to 1; degree_centrality[v] == deg(v) / (n - 1)
* transitivity == 3 * #triangles / #paths-of-length-2
* Fiedler bound: algebraic_connectivity <= node_connectivity <= min_degree
* normalized betweenness lies in [0, 1]; eigenvector centrality is
  L2-normalized

br-r37-c1-nr7bh
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _capacitated_digraph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                g.add_edge(u, v, capacity=rng.randint(1, 9))
    return g, n


def _connected_undirected(seed, p=0.5):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    ng = nx.Graph(g.edges())
    ng.add_nodes_from(range(n))
    return g, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_maximum_flow_is_valid(seed):
    g, n = _capacitated_digraph(seed)
    for s in range(min(2, n)):
        for t in range(n):
            if s == t:
                continue
            value, flow = fnx.maximum_flow(g, s, t)
            # Capacity + non-negativity.
            for u in flow:
                for v, f in flow[u].items():
                    assert -1e-9 <= f <= g[u][v]["capacity"] + 1e-9
            # Conservation at interior nodes.
            for node in range(n):
                if node in (s, t):
                    continue
                inflow = sum(flow[u].get(node, 0) for u in flow)
                outflow = sum(flow.get(node, {}).values())
                assert inflow == pytest.approx(outflow)
            # Value == net flow out of the source.
            net_source = sum(flow[s].values()) - sum(flow[u].get(s, 0) for u in flow)
            assert net_source == pytest.approx(value)


@pytest.mark.parametrize("seed", range(50))
def test_centrality_and_spectral_invariants(seed):
    g, ng, n = _connected_undirected(seed)
    if not nx.is_connected(ng) or g.number_of_edges() == 0:
        pytest.skip("disconnected or empty")
    # pagerank is a probability distribution.
    assert sum(fnx.pagerank(g).values()) == pytest.approx(1.0, abs=1e-6)
    # degree_centrality formula.
    dc = fnx.degree_centrality(g)
    assert all(dc[v] == pytest.approx(g.degree(v) / (n - 1)) for v in g)
    # transitivity identity.
    triangles = sum(fnx.triangles(g).values()) // 3
    triads = sum(d * (d - 1) // 2 for _, d in g.degree())
    expected = (3 * triangles / triads) if triads else 0.0
    assert fnx.transitivity(g) == pytest.approx(expected)
    # Fiedler bound.
    ac = fnx.algebraic_connectivity(g)
    nc = fnx.node_connectivity(g)
    assert ac <= nc + 1e-6
    assert nc <= min(d for _, d in g.degree())
    # Normalized betweenness in [0, 1].
    assert all(0 - 1e-9 <= b <= 1 + 1e-9 for b in fnx.betweenness_centrality(g).values())
    # Eigenvector centrality is L2-normalized.
    ec = fnx.eigenvector_centrality_numpy(g)
    assert sum(v * v for v in ec.values()) ** 0.5 == pytest.approx(1.0, abs=1e-6)
