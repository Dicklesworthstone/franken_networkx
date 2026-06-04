"""Parity for the O(sum) bucket Havel-Hakimi degree-sequence check.

br-hhbucket: is_valid_degree_sequence_havel_hakimi re-sorted the whole list on
every reduction step -- O(n^2 log n). It now uses the standard bucket method
(count array + stub reduction in O(sum of degrees), plus the
Zverovich-Zverovich early-accept). The boolean result is identical; N=1000:
1.66ms -> 0.14ms (12x, faster than nx).
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cases():
    yield from [
        [],
        [0],
        [1],
        [2, 2],
        [3, 3, 3],
        [1, 1, 1],
        [5, 1, 1, 1, 1, 1],
        [4, 4, 4, 4],
        [0, 0],
        [1, 0],
        [6] * 7,
        [3, 3, 2, 2, 2],
    ]
    rnd = random.Random(20240601)
    for _ in range(4000):
        n = rnd.randint(1, 18)
        yield [rnd.randint(0, n + 1) for _ in range(n)]
    for seed in range(80):
        g = nx.gnm_random_graph(rnd.randint(2, 22), rnd.randint(0, 60), seed=seed)
        yield [d for _, d in g.degree()]


def test_havel_hakimi_matches_networkx():
    for seq in _cases():
        assert fnx.is_valid_degree_sequence_havel_hakimi(
            list(seq)
        ) == nx.is_valid_degree_sequence_havel_hakimi(list(seq)), seq[:10]


def test_is_graphical_hh_matches_networkx():
    for seq in _cases():
        assert fnx.is_graphical(list(seq), method="hh") == nx.is_graphical(
            list(seq), method="hh"
        ), seq[:10]


def test_eg_and_hh_agree():
    # Both methods test graphicality, so they must return the same boolean.
    for seq in _cases():
        assert fnx.is_graphical(list(seq), method="eg") == fnx.is_graphical(
            list(seq), method="hh"
        ), seq[:10]


def test_known_results():
    assert fnx.is_valid_degree_sequence_havel_hakimi([2, 2, 2])  # triangle
    assert fnx.is_valid_degree_sequence_havel_hakimi([3, 3, 3, 3])  # K4
    assert not fnx.is_valid_degree_sequence_havel_hakimi([1, 1, 1])  # odd sum
    assert not fnx.is_valid_degree_sequence_havel_hakimi([3, 1, 1])  # over-degree
    assert fnx.is_valid_degree_sequence_havel_hakimi([])  # empty
    assert fnx.is_valid_degree_sequence_havel_hakimi([0, 0, 0])  # all isolated
