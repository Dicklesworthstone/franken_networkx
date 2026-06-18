"""Induced subgraph + edge subgraph structural invariants.

``G.subgraph(S)`` is the node-induced subgraph: it has exactly the nodes S and
exactly the edges of G with BOTH endpoints in S. ``G.edge_subgraph(E)`` is the
edge-induced subgraph: exactly the edges E and the nodes incident to them. These
fundamental properties cross-check the subgraph views against the parent's
edges:
  - subgraph(S).nodes == S;
  - subgraph(S).edges == {(u,v) in G.edges : u in S and v in S};
  - edge_subgraph(E).edges == E, nodes == endpoints of E;
  - a node's degree in the subgraph is <= its degree in G.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(6, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n, r


def _edge_set(it):
    return {tuple(sorted((u, v))) for u, v in it}


@pytest.mark.parametrize("seed", range(40))
def test_node_induced_subgraph(seed):
    g, n, r = _graph(seed)
    S = set(r.sample(range(n), r.randint(2, n)))
    sub = g.subgraph(S)

    assert set(sub.nodes()) == S
    # Exactly the edges with both endpoints inside S.
    expected = {tuple(sorted((u, v))) for u, v in g.edges() if u in S and v in S}
    assert _edge_set(sub.edges()) == expected
    # Induced subgraph can only drop edges -> degree does not increase.
    for node in S:
        assert sub.degree(node) <= g.degree(node)


@pytest.mark.parametrize("seed", range(40))
def test_edge_induced_subgraph(seed):
    g, n, r = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    chosen = list(g.edges())[: max(1, g.number_of_edges() // 2)]
    esub = g.edge_subgraph(chosen)

    # Exactly the chosen edges, and exactly their incident nodes.
    assert _edge_set(esub.edges()) == _edge_set(chosen)
    incident = set()
    for u, v in chosen:
        incident.add(u); incident.add(v)
    assert set(esub.nodes()) == incident


def test_subgraph_of_complete_is_complete():
    # An induced subgraph of K_n on k nodes is K_k.
    k = fnx.complete_graph(6)
    sub = k.subgraph({0, 1, 2, 3})
    assert sub.number_of_edges() == 4 * 3 // 2   # C(4, 2)
