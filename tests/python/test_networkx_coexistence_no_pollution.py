"""franken_networkx must not pollute networkx (clean coexistence).

fnx submodules do ``from networkx... import *`` and manipulate sys.modules under
the ``franken_networkx`` prefix. None of that may leak into networkx's own
namespace: importing fnx (and its submodules) must leave nx's functions,
submodules, and behaviour untouched, so both libraries can be used together.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import importlib
import sys

import networkx as nx
import pytest

# Capture nx callables BEFORE fnx is imported anywhere in this module's chain.
_NX_BEFORE = {
    name: getattr(nx, name, None)
    for name in [
        "connected_components", "find_cliques", "node_connectivity",
        "adjacency_matrix", "core_number", "is_chordal", "bfs_tree",
        "pagerank", "betweenness_centrality",
    ]
}


@pytest.fixture(scope="module", autouse=True)
def _import_fnx_and_submodules():
    import franken_networkx  # noqa: F401
    for sub in ("centrality", "isomorphism", "components", "flow", "tree", "linalg"):
        try:
            importlib.import_module(f"franken_networkx.algorithms.{sub}")
        except ImportError:
            pass


@pytest.mark.parametrize("name", list(_NX_BEFORE))
def test_networkx_functions_unchanged(name):
    # nx's own attribute must be the SAME object after fnx import.
    assert getattr(nx, name, None) is _NX_BEFORE[name]


def test_networkx_centrality_dispersion_intact():
    import networkx.algorithms.centrality as nac
    assert callable(getattr(nac, "dispersion", None))


def test_networkx_submodules_not_redirected_to_fnx():
    for m in ("networkx.algorithms.centrality", "networkx.algorithms.components",
              "networkx.algorithms.isomorphism"):
        mod = sys.modules.get(m)
        if mod is not None:
            assert "franken_networkx" not in getattr(mod, "__name__", "")


def test_networkx_still_computes_correctly():
    g = nx.Graph([(0, 1), (1, 2), (2, 0)])
    assert sorted(map(sorted, nx.find_cliques(g))) == [[0, 1, 2]]
    assert nx.node_connectivity(nx.complete_graph(5)) == 4
    assert abs(sum(nx.pagerank(g).values()) - 1.0) < 1e-6
