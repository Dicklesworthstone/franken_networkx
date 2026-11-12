"""Regression: constraint / effective_size must respect direction on DiGraphs.

networkx computes Burt's structural-hole measures on directed graphs using the
mutual-weight convention — a node's neighbors are ``successors | predecessors``
and the tie weight between u and v is ``w(u->v) + w(v->u)``. fnx's unweighted
path used a Rust kernel that ignored direction and returned uniform values on
DiGraphs. Directed graphs now delegate to networkx (the weighted path already
did). (br-r37-c1-shdir)
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _digraph(mod, edges):
    g = mod.DiGraph()
    for e in edges:
        g.add_edge(*e)
    return g


_EDGES = [(0, 1), (1, 2), (2, 0), (0, 2), (2, 3), (3, 1), (1, 4), (4, 0)]


def _close(a, b):
    assert set(a) == set(b)
    for k in a:
        av, bv = a[k], b[k]
        if av != av and bv != bv:  # both NaN
            continue
        assert abs(av - bv) <= 1e-9, f"node {k}: nx={av} fnx={bv}"


def test_directed_constraint_matches_networkx():
    _close(nx.constraint(_digraph(nx, _EDGES)), fnx.constraint(_digraph(fnx, _EDGES)))


def test_directed_effective_size_matches_networkx():
    _close(nx.effective_size(_digraph(nx, _EDGES)), fnx.effective_size(_digraph(fnx, _EDGES)))


def test_directed_constraint_is_direction_sensitive():
    # A pure directed chain 0->1->2 must NOT yield the uniform values the old
    # undirected kernel produced; it must match nx's asymmetric result.
    gf = _digraph(fnx, [(0, 1), (1, 2), (2, 0), (0, 2)])
    gn = _digraph(nx, [(0, 1), (1, 2), (2, 0), (0, 2)])
    _close(nx.constraint(gn), fnx.constraint(gf))


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_undirected_structural_holes_unchanged(seed):
    gn = nx.gnp_random_graph(9, 0.45, seed=seed)
    gf = fnx.gnp_random_graph(9, 0.45, seed=seed)
    _close(nx.constraint(gn), fnx.constraint(gf))
    _close(nx.effective_size(gn), fnx.effective_size(gf))


def test_weighted_directed_constraint_matches_networkx():
    def build(mod):
        g = mod.DiGraph()
        for u, v in [(0, 1), (1, 2), (2, 0), (0, 2)]:
            g.add_edge(u, v, weight=2.0)
        return g
    _close(nx.constraint(build(nx), weight="weight"), fnx.constraint(build(fnx), weight="weight"))
