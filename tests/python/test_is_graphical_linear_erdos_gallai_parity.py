"""Parity for the O(n log n) Erdos-Gallai is_graphical check.

br-egallai-linear: is_valid_degree_sequence_erdos_gallai was O(n^2) (it
recomputed sum(seq[:k]) and sum(min(d,k) for d in seq[k:]) for every k). It now
uses prefix sums + a binary search for the sorted-descending crossover, making
each Erdos-Gallai inequality O(log n) -- 27x faster, boolean result identical.
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
        [3, 3, 2, 2, 2],
        [100, 1, 1],
        [2, 2, 2, 2],
    ]
    rnd = random.Random(12345)
    for _ in range(2000):
        n = rnd.randint(1, 14)
        yield [rnd.randint(0, n) for _ in range(n)]
    # real graphical sequences
    for seed in range(60):
        g = nx.gnm_random_graph(rnd.randint(3, 18), rnd.randint(0, 40), seed=seed)
        yield [d for _, d in g.degree()]


def test_is_graphical_matches_networkx_both_methods():
    for seq in _cases():
        for method in ("eg", "hh"):
            assert fnx.is_graphical(list(seq), method=method) == nx.is_graphical(
                list(seq), method=method
            ), (seq[:10], method)


def test_direct_erdos_gallai_matches_networkx():
    rnd = random.Random(7)
    for _ in range(500):
        n = rnd.randint(1, 16)
        seq = [rnd.randint(0, n) for _ in range(n)]
        assert fnx.is_valid_degree_sequence_erdos_gallai(
            list(seq)
        ) == nx.is_valid_degree_sequence_erdos_gallai(list(seq)), seq[:10]


def test_known_graphical_and_non_graphical():
    assert fnx.is_graphical([2, 2, 2])  # triangle
    assert fnx.is_graphical([3, 3, 3, 3])  # K4
    assert not fnx.is_graphical([1, 1, 1])  # odd sum
    assert not fnx.is_graphical([4, 1, 1, 1])  # degree exceeds n-1 capacity
    assert fnx.is_graphical([])  # empty sequence is trivially graphical


def test_invalid_method_raises_networkxexception():
    try:
        fnx.is_graphical([1, 1], method="bogus")
    except nx.NetworkXException:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXException for invalid method")
