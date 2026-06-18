"""``franken_networkx.bipartite.is_bipartite`` routes to the fnx native.

``from networkx.algorithms.bipartite import *`` left ``is_bipartite`` bound
to networkx's implementation instead of fnx's native version (the many
bipartite helpers are already explicit overrides).

br-r37-c1-2qsqf
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import bipartite as fnx_bipartite


def test_is_bipartite_is_not_networkx_version():
    assert fnx_bipartite.is_bipartite is not nx.is_bipartite


def test_is_bipartite_goldens():
    assert fnx_bipartite.is_bipartite(fnx.complete_bipartite_graph(2, 3))
    assert fnx_bipartite.is_bipartite(fnx.cycle_graph(6))      # even cycle
    assert not fnx_bipartite.is_bipartite(fnx.cycle_graph(5))  # odd cycle
    assert not fnx_bipartite.is_bipartite(fnx.complete_graph(3))


@pytest.mark.parametrize("seed", range(30))
def test_is_bipartite_matches_networkx(seed):
    g = fnx.gnp_random_graph(8, 0.3, seed=seed)
    ng = nx.Graph(list(g.edges()))
    ng.add_nodes_from(range(8))
    assert fnx_bipartite.is_bipartite(g) == nx.bipartite.is_bipartite(ng)
