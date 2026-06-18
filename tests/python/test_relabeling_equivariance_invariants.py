"""Oracle-free relabeling-equivariance of graph-returning operations.

A structural graph transformation must commute with node relabeling up to
isomorphism: ``op(relabel(G))`` is isomorphic to ``op(G)``. This guards the
label-dependence bug class for graph-RETURNING functions — the family where
the spanning-tree str-node defect lived.

br-r37-c1-rhkmf
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _to_nx(g):
    cls = nx.DiGraph if g.is_directed() else nx.Graph
    h = cls(list(g.edges()))
    h.add_nodes_from(g.nodes())
    return h


def _isomorphic(a, b):
    return nx.is_isomorphic(_to_nx(a), _to_nx(b))


def _random_graph(seed, directed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 8)
    g = (fnx.DiGraph if directed else fnx.Graph)()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < p:
                g.add_edge(u, v)
    return g, n


_UNDIRECTED_OPS = {
    "complement": lambda g: fnx.complement(g),
    "k_core": lambda g: fnx.k_core(g),
    "subgraph": lambda g: g.subgraph(list(g)[: max(1, len(g) - 1)]).copy(),
}

_DIRECTED_OPS = {
    "reverse": lambda g: fnx.reverse(g),
    "transitive_closure": lambda g: fnx.transitive_closure(g),
    "condensation": lambda g: fnx.condensation(g),
}


@pytest.mark.parametrize("op_name", list(_UNDIRECTED_OPS))
@pytest.mark.parametrize("seed", range(30))
def test_undirected_ops_relabeling_equivariant(op_name, seed):
    g, n = _random_graph(seed, directed=False)
    op = _UNDIRECTED_OPS[op_name]
    g_relabelled = fnx.relabel_nodes(g, {i: f"s{i}" for i in range(n)})
    assert _isomorphic(op(g), op(g_relabelled))


@pytest.mark.parametrize("op_name", list(_DIRECTED_OPS))
@pytest.mark.parametrize("seed", range(30))
def test_directed_ops_relabeling_equivariant(op_name, seed):
    g, n = _random_graph(seed, directed=True)
    op = _DIRECTED_OPS[op_name]
    g_relabelled = fnx.relabel_nodes(g, {i: f"s{i}" for i in range(n)})
    assert _isomorphic(op(g), op(g_relabelled))
