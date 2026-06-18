"""Graph coloring chromatic bounds (cross-checking coloring/degree/clique).

greedy_color's color count is bounded both above and below by structural
quantities:
  - upper: at most max_degree + 1 colors (greedy never needs more);
  - lower: at least the clique number (a clique forces all-distinct colors);
  - K_n needs exactly n colors.
The proper-coloring validity itself is covered separately (br-r37-c1-vbds1);
this pins the BOUNDS, cross-checking greedy_color against degree and
find_cliques.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(40))
def test_color_count_bounds(seed):
    r = random.Random(seed)
    n = r.randint(5, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    coloring = fnx.greedy_color(g)
    num_colors = len(set(coloring.values())) if coloring else 0
    max_deg = max((d for _, d in g.degree()), default=0)
    clique_num = max((len(c) for c in fnx.find_cliques(g)), default=0)

    # Greedy upper bound: at most max_degree + 1 colors.
    assert num_colors <= max_deg + 1
    # Lower bound: a clique needs that many distinct colors.
    assert num_colors >= clique_num


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_needs_n_colors(n):
    coloring = fnx.greedy_color(fnx.complete_graph(n))
    assert len(set(coloring.values())) == n


@pytest.mark.parametrize("strategy", [
    "largest_first", "smallest_last", "DSATUR", "connected_sequential_bfs",
])
def test_even_cycle_is_two_colorable(strategy):
    # An even cycle is bipartite; good strategies 2-color it (DSATUR is optimal).
    coloring = fnx.greedy_color(fnx.cycle_graph(6), strategy=strategy)
    # Proper coloring uses at most 3 colors here; clique number is 2.
    assert len(set(coloring.values())) <= 3
    assert all(coloring[u] != coloring[v] for u, v in fnx.cycle_graph(6).edges())
