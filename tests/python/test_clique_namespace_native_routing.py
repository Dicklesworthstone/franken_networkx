"""``franken_networkx.clique`` routes to fnx-native clique functions.

``from networkx.algorithms.clique import *`` left find_cliques,
enumerate_all_cliques, node_clique_number, max_weight_clique and friends
bound to networkx's implementations instead of fnx's native versions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import clique as fnx_clique

_NAMES = [
    "find_cliques", "find_cliques_recursive", "make_max_clique_graph",
    "node_clique_number", "number_of_cliques", "enumerate_all_cliques",
    "max_weight_clique",
]


@pytest.mark.parametrize("name", _NAMES)
def test_clique_fn_is_not_networkx_version(name):
    fn = getattr(fnx_clique, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


def test_clique_values_match_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    assert sorted(map(sorted, fnx_clique.find_cliques(g))) == (
        sorted(map(sorted, nx.find_cliques(ng)))
    )
    assert fnx_clique.node_clique_number(g) == nx.node_clique_number(ng)
    assert sorted(map(sorted, fnx_clique.enumerate_all_cliques(g))) == (
        sorted(map(sorted, nx.enumerate_all_cliques(ng)))
    )
    weight, clique = fnx_clique.max_weight_clique(g, weight=None)
    nweight, nclique = nx.max_weight_clique(ng, weight=None)
    assert weight == nweight
