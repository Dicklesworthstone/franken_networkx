"""Seeded parity for the last two untested-by-name generators.

``navigable_small_world_graph`` and ``k_random_intersection_graph`` were
the final generators without dedicated coverage. Both reproduce a fixed
seed and match networkx byte-for-byte.

br-r37-c1-5v73o
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _edge_signature(g):
    if g.is_directed():
        return sorted((str(u), str(v)) for u, v in g.edges())
    return sorted(tuple(sorted((str(u), str(v)))) for u, v in g.edges())


def _node_signature(g):
    return sorted(map(str, g.nodes()))


@pytest.mark.parametrize("seed", range(15))
def test_navigable_small_world_seeded_parity(seed):
    g1 = fnx.navigable_small_world_graph(4, seed=seed)
    g2 = fnx.navigable_small_world_graph(4, seed=seed)
    ng = nx.navigable_small_world_graph(4, seed=seed)
    # Reproducible and byte-exact vs networkx.
    assert _edge_signature(g1) == _edge_signature(g2)
    assert _edge_signature(g1) == _edge_signature(ng)
    assert _node_signature(g1) == _node_signature(ng)
    # n=4, dim=2 -> 16 grid nodes, directed.
    assert g1.number_of_nodes() == 16
    assert g1.is_directed()


@pytest.mark.parametrize("seed", range(15))
def test_k_random_intersection_seeded_parity(seed):
    g1 = fnx.k_random_intersection_graph(8, 5, 2, seed=seed)
    g2 = fnx.k_random_intersection_graph(8, 5, 2, seed=seed)
    ng = nx.k_random_intersection_graph(8, 5, 2, seed=seed)
    assert _edge_signature(g1) == _edge_signature(g2)
    assert _edge_signature(g1) == _edge_signature(ng)
    assert g1.number_of_nodes() == 8
