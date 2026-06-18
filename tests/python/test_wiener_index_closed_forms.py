"""Wiener index closed forms (ground-truth values for named graphs).

The Wiener index (sum of all unordered-pair shortest-path distances) has exact
closed forms, providing a ground-truth oracle independent of networkx (the
existing wiener tests are nx-parity/conformance):
  - path P_n:       n(n^2 - 1) / 6;
  - complete K_n:   C(n, 2)        (every pair at distance 1);
  - cycle C_n:      n^3/8 (even n), n(n^2 - 1)/8 (odd n);
  - star S_n (n leaves + center): n^2  (n pairs at distance 1, C(n,2) at 2).
Independent of networkx.

No mocks: real fnx against textbook formulas.
"""

from __future__ import annotations

import math

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
def test_path_wiener_index(n):
    assert fnx.wiener_index(fnx.path_graph(n)) == pytest.approx(n * (n * n - 1) / 6)


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_complete_graph_wiener_index(n):
    # Every pair is at distance 1, so the Wiener index is C(n, 2).
    assert fnx.wiener_index(fnx.complete_graph(n)) == pytest.approx(math.comb(n, 2))


@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
def test_cycle_wiener_index(n):
    expected = (n ** 3) / 8 if n % 2 == 0 else n * (n * n - 1) / 8
    assert fnx.wiener_index(fnx.cycle_graph(n)) == pytest.approx(expected)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_star_wiener_index(n):
    # Star with n leaves: n leaf-center pairs at distance 1, C(n,2) leaf-leaf
    # pairs at distance 2 -> n + 2*C(n,2) = n^2.
    assert fnx.wiener_index(fnx.star_graph(n)) == pytest.approx(n * n)
