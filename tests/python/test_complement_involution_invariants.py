"""Graph complement: involution + degree relationship invariants.

The complement swaps present and absent edges (within K_n). Its defining
properties cross-check complement against the degree sequence and edge count:
  - involution: complement(complement(G)) == G;
  - degree: deg_complement(v) = (n-1) - deg_G(v);
  - edge count: |E(G)| + |E(complement(G))| = C(n, 2);
  - the node set is unchanged;
  - complement(K_n) is empty; complement(empty) is K_n.
These differ from the set-algebra (cluiw) and clique-duality (z0f6q) views.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import itertools
import math
import random

import networkx as nx
import pytest
import franken_networkx as fnx


def _edges(g):
    return sorted(tuple(sorted((u, v))) for u, v in g.edges())


@pytest.mark.parametrize("seed", range(40))
def test_complement_involution_and_degree(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    comp = fnx.complement(g)

    # Involution: complementing twice recovers the original.
    assert _edges(fnx.complement(comp)) == _edges(g)
    assert set(comp.nodes()) == set(g.nodes())
    # Degree relationship in the complement.
    dg = dict(g.degree())
    dc = dict(comp.degree())
    for v in g:
        assert dc[v] == (n - 1) - dg[v]
    # Edge counts partition K_n.
    assert g.number_of_edges() + comp.number_of_edges() == math.comb(n, 2)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complement_of_complete_and_empty(n):
    # complement(K_n) has no edges.
    assert fnx.complement(fnx.complete_graph(n)).number_of_edges() == 0
    # complement(empty graph) is the complete graph.
    e = fnx.empty_graph(n)
    assert fnx.complement(e).number_of_edges() == math.comb(n, 2)


@pytest.mark.parametrize("seed", range(40))
def test_complement_adjacency_is_exactly_inverted(seed):
    """The defining rule. Degrees and counts constrain HOW MANY edges move,
    not WHICH: two graphs can share a per-node degree map and differ in
    adjacency."""
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    comp = fnx.complement(g)

    for u, v in itertools.combinations(sorted(g.nodes()), 2):
        assert comp.has_edge(u, v) == (not g.has_edge(u, v))
    # No node acquires a self-loop, which the pair-wise sweep above cannot see.
    assert fnx.number_of_selfloops(comp) == 0


def test_complement_is_an_independent_mutable_graph():
    """Unlike a subgraph, the complement is a snapshot and is not frozen."""
    g = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    comp = fnx.complement(g)
    before = _edges(comp)

    # Removing a parent edge would ADD it to a live complement; a new parent
    # node would add several. Neither reaches this result.
    g.remove_edge(0, 1)
    g.add_node(9)
    assert _edges(comp) == before
    assert 9 not in comp.nodes()

    comp.add_edge(100, 101)          # a real graph, not a frozen view
    assert comp.has_edge(100, 101)


def test_complement_drops_attributes_like_networkx():
    """Surprising but shared: the complement keeps the NODES and nothing else."""
    g = fnx.Graph()
    g.add_node(0, colour="red")
    g.add_edge(0, 1, weight=5)
    g.graph["name"] = "probe"

    ng = nx.Graph()
    ng.add_node(0, colour="red")
    ng.add_edge(0, 1, weight=5)
    ng.graph["name"] = "probe"

    comp, ncomp = fnx.complement(g), nx.complement(ng)
    assert set(comp.nodes()) == set(g.nodes())          # node SET survives...
    assert all(not data for _, data in comp.nodes(data=True))   # ...its attrs do not
    assert comp.graph == {}
    # Same on both sides, so this is contract rather than divergence.
    assert all(not data for _, data in ncomp.nodes(data=True))
    assert ncomp.graph == {}


def test_complement_ignores_self_loops():
    """The random family is built with u < v, so loops never occur in it."""
    g = fnx.Graph([(0, 1), (1, 2)])
    g.add_edge(0, 0)
    ng = nx.Graph([(0, 1), (1, 2)])
    ng.add_edge(0, 0)

    comp = fnx.complement(g)
    assert _edges(comp) == [(0, 2)]                 # the loop is neither kept nor created
    assert _edges(comp) == sorted(tuple(sorted(e)) for e in nx.complement(ng).edges())


def test_directed_and_multigraph_complements():
    d = fnx.DiGraph([(0, 1), (1, 2)])
    nd = nx.DiGraph([(0, 1), (1, 2)])
    # Directed: every ordered pair that is not an arc becomes one.
    assert sorted(fnx.complement(d).edges()) == [(0, 2), (1, 0), (2, 0), (2, 1)]
    assert sorted(fnx.complement(d).edges()) == sorted(nx.complement(nd).edges())

    m = fnx.MultiGraph(); m.add_edge(0, 1); m.add_edge(0, 1); m.add_edge(1, 2)
    nm = nx.MultiGraph(); nm.add_edge(0, 1); nm.add_edge(0, 1); nm.add_edge(1, 2)
    mc, nmc = fnx.complement(m), nx.complement(nm)
    # Multiplicity carries into the complement in both libraries.
    assert mc.is_multigraph()
    assert sorted(mc.edges()) == sorted(nmc.edges()) == [(0, 2), (0, 2)]
