"""Differential + golden parity for ``is_semiconnected`` / ``is_aperiodic``.

``is_semiconnected(G)`` is True when for every node pair one reaches the
other; ``is_aperiodic(G)`` is True when the gcd of all cycle lengths is 1
(defined for strongly connected digraphs). Neither had a dedicated test
file.

br-r37-c1-63qdt
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _digraph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(3, 7)
    fg = fnx.DiGraph()
    fg.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                fg.add_edge(u, v)
    ng = nx.DiGraph(fg.edges())
    ng.add_nodes_from(range(n))
    return fg, ng


@pytest.mark.parametrize("seed", range(60))
def test_is_semiconnected_matches_networkx(seed):
    fg, ng = _digraph(seed)
    if fg.number_of_edges() == 0:
        pytest.skip("empty edge set")
    assert fnx.is_semiconnected(fg) == nx.is_semiconnected(ng)


@pytest.mark.parametrize("seed", range(60))
def test_is_aperiodic_matches_networkx(seed):
    fg, ng = _digraph(seed)
    if not nx.is_strongly_connected(ng):
        pytest.skip("is_aperiodic requires strong connectivity")
    assert fnx.is_aperiodic(fg) == nx.is_aperiodic(ng)


def test_goldens():
    # A linear chain is semiconnected (every pair comparable).
    assert fnx.is_semiconnected(fnx.DiGraph([(0, 1), (1, 2), (2, 3)]))
    # A 3-cycle has period 3 -> not aperiodic.
    assert not fnx.is_aperiodic(fnx.DiGraph([(0, 1), (1, 2), (2, 0)]))
    # Adding a self-loop makes gcd(1, 3) == 1 -> aperiodic.
    assert fnx.is_aperiodic(fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 0)]))


def test_error_contracts_match_networkx():
    # is_aperiodic on a non-strongly-connected digraph.
    fg = fnx.DiGraph([(0, 1)])
    ng = nx.DiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXError):
        fnx.is_aperiodic(fg)
    with pytest.raises(nx.NetworkXError):
        nx.is_aperiodic(ng)
    # is_semiconnected on the null graph.
    with pytest.raises(nx.NetworkXPointlessConcept):
        fnx.is_semiconnected(fnx.DiGraph())
    with pytest.raises(nx.NetworkXPointlessConcept):
        nx.is_semiconnected(nx.DiGraph())
