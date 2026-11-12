"""Metamorphic round-trip relations for the conversion subsystem.

For each codec, decoding the encoding recovers the original graph:

* ``from_dict_of_dicts(to_dict_of_dicts(G))`` preserves weighted edges
* ``from_dict_of_lists(to_dict_of_lists(G))`` preserves the edge set
* ``from_numpy_array(to_numpy_array(G))`` / scipy variant preserve edges
* ``node_link_graph(node_link_data(G))`` preserves nodes and edges

br-r37-c1-w3rje
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _graph(seed, directed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    g = (fnx.DiGraph if directed else fnx.Graph)()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < p:
                g.add_edge(u, v, weight=rng.randint(1, 9))
    return g


def _weighted_edges(g):
    return sorted((u, v, g[u][v].get("weight")) for u, v in g.edges())


def _plain_edges(g):
    if g.is_directed():
        return sorted((u, v) for u, v in g.edges())
    return sorted(tuple(sorted(e)) for e in g.edges())


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_dict_of_dicts_round_trip(directed, seed):
    g = _graph(seed, directed)
    cls = fnx.DiGraph if directed else fnx.Graph
    rg = fnx.from_dict_of_dicts(fnx.to_dict_of_dicts(g), create_using=cls())
    assert _weighted_edges(rg) == _weighted_edges(g)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_dict_of_lists_round_trip(directed, seed):
    g = _graph(seed, directed)
    cls = fnx.DiGraph if directed else fnx.Graph
    rg = fnx.from_dict_of_lists(fnx.to_dict_of_lists(g), create_using=cls())
    assert _plain_edges(rg) == _plain_edges(g)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_numpy_and_scipy_round_trip(directed, seed):
    g = _graph(seed, directed)
    cls = fnx.DiGraph if directed else fnx.Graph
    rg_np = fnx.from_numpy_array(fnx.to_numpy_array(g), create_using=cls())
    assert _plain_edges(rg_np) == _plain_edges(g)
    rg_sp = fnx.from_scipy_sparse_array(fnx.to_scipy_sparse_array(g), create_using=cls())
    assert _plain_edges(rg_sp) == _plain_edges(g)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_node_link_round_trip(directed, seed):
    g = _graph(seed, directed)
    data = fnx.node_link_data(g, edges="edges")
    rg = fnx.node_link_graph(data, directed=directed, edges="edges")
    assert sorted(map(str, rg.nodes())) == sorted(map(str, g.nodes()))
    assert rg.number_of_edges() == g.number_of_edges()
