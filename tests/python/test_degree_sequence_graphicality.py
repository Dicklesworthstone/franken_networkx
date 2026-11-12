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


@pytest.mark.parametrize("seed", range(60))
def test_graphical_sequences_are_actually_realizable(seed):
    """The other half of realizability: BUILD the graph, do not just predict it.

    The file checks that a real graph's degree sequence is graphical. The
    converse — that a sequence called graphical can be realized by some simple
    graph — is what makes the predicate meaningful, and nothing constructed one.
    """
    r = random.Random(seed)
    n = r.randint(4, 9)
    seq = [r.randint(0, n - 1) for _ in range(n)]
    if not fnx.is_graphical(seq):
        pytest.skip("not graphical — nothing is claimed to be realizable")

    realized = fnx.havel_hakimi_graph(seq)
    assert sorted((d for _, d in realized.degree()), reverse=True) == sorted(seq, reverse=True)

    # The realization must be SIMPLE — graphicality is about simple graphs.
    listed = list(realized.edges())
    assert fnx.number_of_selfloops(realized) == 0
    assert len(listed) == len({frozenset(e) for e in listed})

    # networkx realizes the same degree sequence.
    assert sorted((d for _, d in realized.degree()), reverse=True) == sorted(
        (d for _, d in nx.havel_hakimi_graph(list(seq)).degree()), reverse=True
    )


def test_random_sequence_family_contains_both_verdicts():
    """Guards the three-way agreement: eg == hh == graphical is trivially true
    if every sequence lands on the same side."""
    graphical = sum(
        1
        for seed in range(60)
        for r in [random.Random(seed)]
        for n in [r.randint(4, 9)]
        if fnx.is_graphical([r.randint(0, n - 1) for _ in range(n)])
    )
    # Measured 11 graphical of 60.
    assert 5 <= graphical <= 55, f"{graphical} of 60 graphical — the family has gone one-sided"


@pytest.mark.parametrize(
    "seq", [[], [0], [0, 0], [-1, 1], [1, 1], [5, 1, 1]],
    ids=["empty", "single_zero", "two_zeros", "negative", "one_edge", "degree_exceeds_n"],
)
def test_boundary_sequences_agree_across_methods_and_networkx(seq):
    """The sweep draws degrees in 0..n-1 with n >= 4; these are outside it."""
    results = (
        fnx.is_valid_degree_sequence_erdos_gallai(list(seq)),
        fnx.is_valid_degree_sequence_havel_hakimi(list(seq)),
        fnx.is_graphical(list(seq)),
    )
    assert len(set(results)) == 1                 # the three methods still agree
    assert results == (
        nx.is_valid_degree_sequence_erdos_gallai(list(seq)),
        nx.is_valid_degree_sequence_havel_hakimi(list(seq)),
        nx.is_graphical(list(seq)),
    )
