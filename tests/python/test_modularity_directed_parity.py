"""Regression: community.modularity must use the directed (Leicht-Newman)
formula on DiGraphs, matching networkx.

For directed graphs nx computes
``Q = (1/m) * sum_ij [A_ij - gamma * k_i^out * k_j^in / m] delta(c_i, c_j)``
(in/out degrees, divisor m). fnx's unweighted path called a Rust kernel that
used the *undirected* formula (``k_i*k_j / 2m``, divisor 2m) even for DiGraphs,
so directed modularity disagreed with nx. The weighted path already delegated
to nx; directed graphs now delegate too. (br-r37-c1-moddir)
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _digraph(mod, edges):
    g = mod.DiGraph()
    for e in edges:
        g.add_edge(*e)
    return g


_EDGES = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3), (0, 3), (4, 1)]
_PART = [{0, 1, 2}, {3, 4, 5}]


def test_directed_modularity_matches_networkx():
    gn, gf = _digraph(nx, _EDGES), _digraph(fnx, _EDGES)
    assert abs(fnx.community.modularity(gf, _PART) - nx.community.modularity(gn, _PART)) <= 1e-9


def test_directed_modularity_differs_from_undirected_formula():
    # Guard the actual semantics: directed modularity here is NOT equal to the
    # undirected modularity of the same edge set (the old buggy value).
    gn, gf = _digraph(nx, _EDGES), _digraph(fnx, _EDGES)
    directed_q = fnx.community.modularity(gf, _PART)
    undirected_q = nx.community.modularity(gn.to_undirected(), _PART)
    assert abs(directed_q - undirected_q) > 1e-6
    assert abs(directed_q - nx.community.modularity(gn, _PART)) <= 1e-9


@pytest.mark.parametrize("resolution", [0.5, 1.0, 1.5, 2.0])
def test_directed_modularity_resolution_matches_networkx(resolution):
    gn, gf = _digraph(nx, _EDGES), _digraph(fnx, _EDGES)
    assert abs(
        fnx.community.modularity(gf, _PART, resolution=resolution)
        - nx.community.modularity(gn, _PART, resolution=resolution)
    ) <= 1e-9


def test_weighted_directed_modularity_matches_networkx():
    def build(mod):
        g = mod.DiGraph()
        for i, (u, v) in enumerate([(0, 1), (1, 2), (2, 0), (3, 4), (4, 3), (2, 3)]):
            g.add_edge(u, v, weight=float(i + 1))
        return g
    part = [{0, 1, 2}, {3, 4}]
    assert abs(
        fnx.community.modularity(build(fnx), part, weight="weight")
        - nx.community.modularity(build(nx), part, weight="weight")
    ) <= 1e-9


def test_multidigraph_modularity_matches_networkx():
    edges = [(0, 1), (0, 1), (1, 2), (2, 0), (3, 4), (4, 3)]
    gn = nx.MultiDiGraph(edges)
    gf = fnx.MultiDiGraph(edges)
    part = [{0, 1, 2}, {3, 4}]
    assert abs(fnx.community.modularity(gf, part) - nx.community.modularity(gn, part)) <= 1e-9


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_undirected_modularity_unchanged(seed):
    gn = nx.gnp_random_graph(9, 0.45, seed=seed)
    gf = fnx.gnp_random_graph(9, 0.45, seed=seed)
    part = [set(range(4)), set(range(4, 9))]
    assert abs(fnx.community.modularity(gf, part) - nx.community.modularity(gn, part)) <= 1e-9
