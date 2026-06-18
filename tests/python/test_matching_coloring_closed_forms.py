"""Closed-form matching and chromatic values on structured graphs.

Exact graph-theory ground truth, no networkx oracle:

* maximum matching: K_n / P_n / C_n have ``floor(n/2)`` edges;
  K_{m,n} has ``min(m, n)``
* Gallai: ``|min edge cover| == n - |max matching|`` (no isolated nodes)
* chromatic: greedy colours K_n with exactly n colours; a bipartite graph
  with a connected strategy uses <= 2; an odd cycle needs >= 3

br-r37-c1-sxghw
"""

from __future__ import annotations

import pytest
import franken_networkx as fnx


def _matching_size(g):
    return len(fnx.max_weight_matching(g, maxcardinality=True))


def _n_colors(g, strategy="largest_first"):
    coloring = fnx.greedy_color(g, strategy=strategy)
    return len(set(coloring.values())) if coloring else 0


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_matching_number_complete_path_cycle(n):
    assert _matching_size(fnx.complete_graph(n)) == n // 2
    assert _matching_size(fnx.path_graph(n)) == n // 2
    assert _matching_size(fnx.cycle_graph(n)) == n // 2


@pytest.mark.parametrize("m,n", [(2, 3), (3, 3), (2, 5), (4, 2)])
def test_matching_number_complete_bipartite(m, n):
    assert _matching_size(fnx.complete_bipartite_graph(m, n)) == min(m, n)


@pytest.mark.parametrize("n", [4, 5, 6])
def test_gallai_edge_cover_on_path(n):
    g = fnx.path_graph(n)
    # Gallai: matching + edge cover == n (no isolated nodes).
    assert len(fnx.min_edge_cover(g)) == n - _matching_size(g)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_complete_graph_chromatic_colors(n):
    # Every pair adjacent -> exactly n colours.
    assert _n_colors(fnx.complete_graph(n)) == n


@pytest.mark.parametrize("builder", [
    lambda: fnx.path_graph(6),
    lambda: fnx.cycle_graph(6),
    lambda: fnx.complete_bipartite_graph(3, 3),
])
def test_bipartite_graphs_two_colorable(builder):
    assert _n_colors(builder(), strategy="connected_sequential_bfs") <= 2


@pytest.mark.parametrize("n", [5, 7, 9])
def test_odd_cycle_needs_three_colors(n):
    assert _n_colors(fnx.cycle_graph(n)) >= 3
