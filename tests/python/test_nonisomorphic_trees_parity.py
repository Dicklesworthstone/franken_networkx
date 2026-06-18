"""Differential + golden parity for non-isomorphic tree enumeration.

``nonisomorphic_trees(order)`` yields every tree on ``order`` nodes up to
isomorphism; ``number_of_nonisomorphic_trees(order)`` counts them. Neither
had a dedicated test file.

br-r37-c1-otgms
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

# OEIS A000055: number of trees on n nodes, n = 1..10.
_KNOWN_COUNTS = [1, 1, 1, 2, 3, 6, 11, 23, 47, 106]


@pytest.mark.parametrize("order", range(2, 9))
def test_nonisomorphic_trees_count_matches_networkx(order):
    fnx_trees = list(fnx.nonisomorphic_trees(order))
    nx_trees = list(nx.nonisomorphic_trees(order))
    assert len(fnx_trees) == len(nx_trees)
    assert fnx.number_of_nonisomorphic_trees(order) == (
        nx.number_of_nonisomorphic_trees(order)
    )
    assert len(fnx_trees) == fnx.number_of_nonisomorphic_trees(order)


@pytest.mark.parametrize("order", range(2, 9))
def test_emitted_trees_pairwise_isomorphic_to_networkx(order):
    fnx_trees = list(fnx.nonisomorphic_trees(order))
    nx_trees = list(nx.nonisomorphic_trees(order))
    # Emitted in the same canonical order, so corresponding trees are
    # isomorphic, and each is a valid tree.
    for ft, nt in zip(fnx_trees, nx_trees):
        assert nx.is_tree(ft)
        assert nx.is_isomorphic(ft, nt)


@pytest.mark.parametrize("order", range(1, 9))
def test_known_count_goldens(order):
    assert fnx.number_of_nonisomorphic_trees(order) == _KNOWN_COUNTS[order - 1]


def test_create_matrix_kwarg_rejected_like_networkx():
    # The legacy ``create='matrix'`` kwarg was removed upstream; both reject it.
    with pytest.raises(TypeError):
        list(fnx.nonisomorphic_trees(4, create="matrix"))
    with pytest.raises(TypeError):
        list(nx.nonisomorphic_trees(4, create="matrix"))
