"""Oracle-free output-validity for chordal completion and planarity.

* ``complete_to_chordal_graph`` returns a chordal supergraph of the input
* ``chordal_graph_cliques`` yields actual cliques on a chordal graph
* ``check_planarity`` returns a structurally valid embedding for planar
  graphs and agrees with ``is_planar``

br-r37-c1-nwgw4
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _graph(seed, p=0.35):
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
    return g, ng


@pytest.mark.parametrize("seed", range(50))
def test_complete_to_chordal_is_chordal_supergraph(seed):
    g, _ = _graph(seed)
    h, _alpha = fnx.complete_to_chordal_graph(g)
    assert fnx.is_chordal(h)
    # Every original edge survives (it is a supergraph).
    assert all(h.has_edge(u, v) for u, v in g.edges())


@pytest.mark.parametrize("seed", range(50))
def test_chordal_graph_cliques_are_cliques(seed):
    g, _ = _graph(seed)
    if not fnx.is_chordal(g):
        pytest.skip("not chordal")
    adj = {x: set(g.neighbors(x)) for x in g}
    for clique in fnx.chordal_graph_cliques(g):
        members = set(clique)
        assert all(b in adj[a] for a in members for b in members if a != b)


@pytest.mark.parametrize("seed", range(50))
def test_check_planarity_consistent_and_valid(seed):
    g, ng = _graph(seed)
    assert fnx.is_planar(g) == nx.is_planar(ng)
    is_planar, embedding = fnx.check_planarity(g)
    assert is_planar == fnx.is_planar(g)
    if is_planar and embedding is not None:
        # A valid combinatorial embedding passes its own structure check.
        embedding.check_structure()


def test_planarity_goldens():
    assert fnx.check_planarity(fnx.complete_graph(4))[0]       # K4 is planar
    assert not fnx.check_planarity(fnx.complete_graph(5))[0]   # K5 is not
    assert not fnx.is_planar(fnx.complete_bipartite_graph(3, 3))  # K_{3,3}
