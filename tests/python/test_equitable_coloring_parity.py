"""Differential + golden parity for equitable graph coloring.

``equitable_color(G, num_colors)`` returns an equitable coloring (color
class sizes differ by at most one) when ``num_colors > max_degree``;
``is_equitable`` validates a coloring. Neither had a dedicated test file.

br-r37-c1-1k6jy
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms.coloring.equitable_coloring import (
    is_equitable as fnx_is_equitable,
)
from networkx.algorithms.coloring.equitable_coloring import (
    is_equitable as nx_is_equitable,
)


def _pair(seed, p=0.3):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(50))
def test_equitable_color_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    max_degree = max((d for _, d in ng.degree()), default=0)
    num_colors = max_degree + 1
    fr = fnx.equitable_color(fg, num_colors)
    nr = nx.equitable_color(ng, num_colors)
    assert fr == nr
    # The coloring fnx returns is a valid equitable coloring per nx.
    assert nx_is_equitable(ng, fr)


@pytest.mark.parametrize("seed", range(40))
def test_is_equitable_matches_networkx(seed):
    fg, ng, n = _pair(seed)
    rng = random.Random(seed * 7 + 1)
    coloring = {i: rng.randint(0, 2) for i in range(n)}
    assert fnx_is_equitable(fg, coloring) == nx_is_equitable(ng, coloring)


def test_equitable_color_golden():
    # K4 needs 4 colors; each node gets a distinct color.
    fr = fnx.equitable_color(fnx.complete_graph(4), 4)
    assert len(set(fr.values())) == 4
    assert fr == nx.equitable_color(nx.complete_graph(4), 4)


def test_too_few_colors_raises_like_networkx():
    with pytest.raises(nx.NetworkXAlgorithmError):
        fnx.equitable_color(fnx.complete_graph(4), 2)
    with pytest.raises(nx.NetworkXAlgorithmError):
        nx.equitable_color(nx.complete_graph(4), 2)
