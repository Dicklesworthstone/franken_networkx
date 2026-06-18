"""Degree-sequence validity and realization.

Covers ``is_valid_degree_sequence_erdos_gallai``,
``is_valid_degree_sequence_havel_hakimi`` and ``havel_hakimi_graph``
(``is_graphical`` already has coverage). Combines differential parity vs
networkx with metamorphic checks:

* the Erdős–Gallai and Havel–Hakimi validity tests are equivalent theorems,
  so they must agree (and agree with ``is_graphical``)
* ``havel_hakimi_graph`` must realize exactly the requested degree sequence
* the complement of a realization must have degree sequence
  ``n - 1 - d`` and the complementary edge count

br-r37-c1-xy5mv
br-r37-c1-clzp1
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(80))
def test_validity_methods_agree_and_match_networkx(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 8)
    seq = [rng.randint(0, n - 1) for _ in range(n)]
    eg = fnx.is_valid_degree_sequence_erdos_gallai(seq)
    hh = fnx.is_valid_degree_sequence_havel_hakimi(seq)
    # Equivalent theorems -> identical verdict, and equal to is_graphical.
    assert eg == hh
    assert eg == fnx.is_graphical(seq)
    # And matches networkx.
    assert eg == nx.is_valid_degree_sequence_erdos_gallai(seq)
    assert hh == nx.is_valid_degree_sequence_havel_hakimi(seq)


@pytest.mark.parametrize("seed", range(60))
def test_havel_hakimi_graph_realizes_sequence(seed):
    g = nx.gnp_random_graph(random.Random(seed).randint(4, 9), 0.4, seed=seed)
    seq = sorted((d for _, d in g.degree()), reverse=True)
    if not nx.is_graphical(seq):
        pytest.skip("not graphical")
    h = fnx.havel_hakimi_graph(seq)
    assert sorted((d for _, d in h.degree()), reverse=True) == seq


@pytest.mark.parametrize("seed", range(50))
def test_havel_hakimi_complement_degree_invariant(seed):
    rng = random.Random(seed * 13 + 5)
    n = rng.randint(4, 10)
    source = nx.gnp_random_graph(n, 0.45, seed=seed)
    seq = sorted((d for _, d in source.degree()), reverse=True)

    realized = fnx.havel_hakimi_graph(seq)
    complement = fnx.complement(realized)

    expected_complement_seq = sorted((n - 1 - d for d in seq), reverse=True)
    actual_complement_seq = sorted(
        (d for _, d in complement.degree()), reverse=True
    )
    assert actual_complement_seq == expected_complement_seq
    assert (
        realized.number_of_edges() + complement.number_of_edges()
        == n * (n - 1) // 2
    )


def test_degree_sequence_goldens():
    # K4: every degree 3.
    assert fnx.is_graphical([3, 3, 3, 3])
    assert fnx.is_valid_degree_sequence_erdos_gallai([3, 3, 3, 3])
    # A star K_{1,3}.
    assert fnx.is_graphical([3, 1, 1, 1])
    # Odd sum / impossible degree -> not graphical.
    assert not fnx.is_graphical([1, 1, 1])
    assert not fnx.is_valid_degree_sequence_havel_hakimi([3, 0, 0])
    # Realize the star and check it is one.
    star = fnx.havel_hakimi_graph([3, 1, 1, 1])
    assert sorted((d for _, d in star.degree()), reverse=True) == [3, 1, 1, 1]
