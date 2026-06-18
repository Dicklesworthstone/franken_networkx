"""Degree-sequence graphicality: cross-method agreement + realizability.

Three independent tests decide whether an integer sequence is the degree
sequence of some simple graph: the Erdos-Gallai inequality, the Havel-Hakimi
reduction, and ``is_graphical``. They must ALL agree on every sequence — a
strong cross-method invariant. Additionally, the degree sequence of any actual
graph is, by construction, graphical. networkx parity is also checked.

No mocks: real fnx and real networkx on random sequences and graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(60))
def test_graphicality_methods_agree_and_match_nx(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    seq = [r.randint(0, n - 1) for _ in range(n)]

    eg = fnx.is_valid_degree_sequence_erdos_gallai(seq)
    hh = fnx.is_valid_degree_sequence_havel_hakimi(seq)
    graphical = fnx.is_graphical(seq)

    # All three methods decide graphicality identically.
    assert eg == hh == graphical

    # And each matches networkx.
    assert eg == nx.is_valid_degree_sequence_erdos_gallai(list(seq))
    assert hh == nx.is_valid_degree_sequence_havel_hakimi(list(seq))
    assert graphical == nx.is_graphical(list(seq))


@pytest.mark.parametrize("seed", range(40))
def test_real_graph_degree_sequence_is_graphical(seed):
    r = random.Random(seed)
    n = r.randint(4, 10)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.4:
                g.add_edge(u, v)
    seq = sorted((d for _, d in g.degree()), reverse=True)
    # A real graph's degree sequence is realizable by definition.
    assert fnx.is_graphical(seq)
    # Handshaking: the degree sum is even (= 2|E|).
    assert sum(seq) % 2 == 0
    assert sum(seq) == 2 * g.number_of_edges()


def test_known_non_graphical_sequences():
    # [3, 0]: a degree-3 node needs 3 neighbors but only 1 other node exists.
    assert not fnx.is_graphical([3, 0])
    # Odd degree sum can never be graphical.
    assert not fnx.is_graphical([1, 1, 1])
    # [2, 2, 2] is the triangle — graphical.
    assert fnx.is_graphical([2, 2, 2])
