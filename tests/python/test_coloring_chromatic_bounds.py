"""Graph coloring chromatic bounds (cross-checking coloring/degree/clique).

greedy_color's color count is bounded both above and below by structural
quantities:
  - upper: at most max_degree + 1 colors (greedy never needs more);
  - lower: at least the clique number (a clique forces all-distinct colors);
  - K_n needs exactly n colors.
The proper-coloring validity itself is covered separately (br-r37-c1-vbds1);
this pins the BOUNDS, cross-checking greedy_color against degree and
find_cliques.

Both bounds hold for EVERY greedy strategy, not just the default one, so they
are swept over all seven. The bracket [clique number, max_degree + 1] is wider
than 2 on 22 of the 40 random draws, so named graphs whose chromatic number is
known exactly (K_n, even and odd cycles, complete bipartite) carry the exact
anchoring that a bracket cannot.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

STRATEGIES = [
    "largest_first",
    "smallest_last",
    "DSATUR",
    "connected_sequential_bfs",
    "connected_sequential_dfs",
    "independent_set",
    "saturation_largest_first",
]


def _random_graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


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
    # Exactly two: the test is named for 2-colorability and all four strategies
    # achieve it, so `<= 3` was slack the name itself contradicts.
    assert len(set(coloring.values())) == 2
    assert all(coloring[u] != coloring[v] for u, v in fnx.cycle_graph(6).edges())


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_bounds_hold_for_every_strategy(strategy, seed):
    """Delta+1 and the clique number bound greedy under ANY vertex order."""
    g = _random_graph(seed)
    coloring = fnx.greedy_color(g, strategy=strategy)

    # The count is read off this dict, so it has to describe the whole graph.
    assert set(coloring) == set(g.nodes())

    num_colors = len(set(coloring.values())) if coloring else 0
    max_deg = max((d for _, d in g.degree()), default=0)
    clique_num = max((len(c) for c in fnx.find_cliques(g)), default=0)
    assert clique_num <= num_colors <= max_deg + 1


@pytest.mark.parametrize("n", [5, 7, 9])
def test_odd_cycle_needs_exactly_three(n):
    """An odd cycle is the standard non-bipartite witness: chi = 3, not 2."""
    coloring = fnx.greedy_color(fnx.cycle_graph(n), strategy="DSATUR")
    assert len(set(coloring.values())) == 3
    assert all(coloring[u] != coloring[v] for u, v in fnx.cycle_graph(n).edges())


@pytest.mark.parametrize("a, b", [(2, 3), (3, 3), (2, 5), (4, 4)])
def test_complete_bipartite_needs_exactly_two(a, b):
    """DSATUR is optimal on bipartite graphs, and max_degree+1 is far looser here."""
    g = fnx.complete_bipartite_graph(a, b)
    coloring = fnx.greedy_color(g, strategy="DSATUR")
    assert len(set(coloring.values())) == 2
    # The upper bound alone would permit max(a, b) + 1 colors — hence the anchor.
    assert 2 < max(a, b) + 1
