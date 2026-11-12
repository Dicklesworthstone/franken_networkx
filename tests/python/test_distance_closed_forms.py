"""Closed-form distance / Wiener-index values on structured graphs.

Exact graph-theory ground truth, no networkx oracle:

* Wiener index: K_n is ``n(n-1)/2`` (all distances 1); P_n is ``C(n+1, 3)``
* diameter: P_n is ``n-1``; C_n is ``floor(n/2)``; the m×n grid is
  ``(m-1)+(n-1)``
* ``average_shortest_path_length``: K_n is 1; the star S_n has the
  closed-form ``(n + 2*C(n,2)) / C(n+1, 2)``

br-r37-c1-2l793
"""

from __future__ import annotations

import math

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_wiener_index_closed_forms(n):
    assert fnx.wiener_index(fnx.complete_graph(n)) == n * (n - 1) // 2
    assert fnx.wiener_index(fnx.path_graph(n)) == math.comb(n + 1, 3)


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_diameter_closed_forms(n):
    assert fnx.diameter(fnx.path_graph(n)) == n - 1
    assert fnx.diameter(fnx.cycle_graph(n)) == n // 2
    assert fnx.diameter(fnx.complete_graph(n)) == 1


@pytest.mark.parametrize("m,n", [(2, 3), (3, 3), (2, 4), (3, 4)])
def test_grid_diameter_closed_form(m, n):
    assert fnx.diameter(fnx.grid_2d_graph(m, n)) == (m - 1) + (n - 1)


@pytest.mark.parametrize("n", [4, 5, 6])
def test_complete_graph_average_path_length_is_one(n):
    assert fnx.average_shortest_path_length(fnx.complete_graph(n)) == pytest.approx(1.0)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_star_average_path_length_closed_form(n):
    g = fnx.star_graph(n)  # n leaves + centre
    # n centre-leaf pairs at distance 1, C(n,2) leaf-leaf pairs at distance 2.
    expected = (n * 1 + math.comb(n, 2) * 2) / math.comb(n + 1, 2)
    assert fnx.average_shortest_path_length(g) == pytest.approx(expected)
