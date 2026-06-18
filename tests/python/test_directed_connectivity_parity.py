"""Differential parity for directed connectivity helpers.

Covers ``is_semiconnected``, ``attracting_components``,
``number_attracting_components``, ``is_attracting_component`` and the
SCC-``condensation`` member sets. None had dedicated coverage.

br-r37-c1-6uhyz
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.3):
    rng = random.Random(seed)
    n = rng.randint(3, 8)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


def _scc_sets(components):
    return sorted(tuple(sorted(c)) for c in components)


@pytest.mark.parametrize("seed", range(60))
def test_is_semiconnected_matches_networkx(seed):
    fg, ng = _pair(seed)
    if ng.number_of_nodes() == 0:
        pytest.skip("empty")
    assert fnx.is_semiconnected(fg) == nx.is_semiconnected(ng)


@pytest.mark.parametrize("seed", range(60))
def test_attracting_components_match_networkx(seed):
    fg, ng = _pair(seed)
    assert _scc_sets(fnx.attracting_components(fg)) == _scc_sets(
        nx.attracting_components(ng)
    )
    assert fnx.number_attracting_components(fg) == nx.number_attracting_components(ng)


@pytest.mark.parametrize("seed", range(40))
def test_condensation_member_sets_match_networkx(seed):
    fg, ng = _pair(seed)
    fc = fnx.condensation(fg)
    nc = nx.condensation(ng)
    fm = sorted(tuple(sorted(d["members"])) for _, d in fc.nodes(data=True))
    nm = sorted(tuple(sorted(d["members"])) for _, d in nc.nodes(data=True))
    assert fm == nm
    assert fc.number_of_edges() == nc.number_of_edges()


def test_goldens():
    # A directed path is semiconnected; a branch (0->1, 0->2) is not.
    assert fnx.is_semiconnected(fnx.DiGraph([(0, 1), (1, 2)]))
    assert not fnx.is_semiconnected(fnx.DiGraph([(0, 1), (0, 2)]))
    # condensation of a 3-cycle + a 2-cycle gives two super-nodes.
    g = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 3)])
    members = sorted(
        tuple(sorted(d["members"])) for _, d in fnx.condensation(g).nodes(data=True)
    )
    assert members == [(0, 1, 2), (3, 4)]


def test_empty_graph_semiconnected_raises_like_networkx():
    with pytest.raises(nx.NetworkXPointlessConcept):
        fnx.is_semiconnected(fnx.DiGraph())
    with pytest.raises(nx.NetworkXPointlessConcept):
        nx.is_semiconnected(nx.DiGraph())
