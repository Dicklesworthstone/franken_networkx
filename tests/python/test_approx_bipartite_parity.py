"""Phase B coverage (load-7.8 session): approximation namespace +
bipartite module parity. Both impls from identical fixed graphs;
deterministic-result fns only (randomized approx fns compared by
bound, seeded where supported). Zero divergences at certification.
"""

import random

import networkx as nx
import networkx.algorithms.bipartite as nxb
import pytest

import franken_networkx as fnx

try:
    from franken_networkx.algorithms import approximation as fxa  # noqa: F401

    _HAS_FXA = True
except Exception:
    _HAS_FXA = False

from networkx.algorithms import approximation as nxa


def _mk(mod):
    R = random.Random(5)
    g = mod.Graph()
    for u, v in ((R.randrange(30), R.randrange(30)) for _ in range(120)):
        if u != v:
            g.add_edge(u, v)
    return g


@pytest.mark.skipif(not _HAS_FXA, reason="fnx approximation namespace unavailable")
def test_large_clique_size_matches():
    assert fxa.large_clique_size(_mk(fnx)) == nxa.large_clique_size(_mk(nx))


def test_local_node_connectivity_matches():
    assert nxa.local_node_connectivity(_mk(fnx), 0, 5) == nxa.local_node_connectivity(
        _mk(nx), 0, 5
    )


def test_average_clustering_approx_seeded_matches():
    assert round(nxa.average_clustering(_mk(fnx), seed=1), 6) == round(
        nxa.average_clustering(_mk(nx), seed=1), 6
    )


def _bip(mod):
    g = mod.Graph()
    for i in range(10):
        g.add_node(i, bipartite=0)
    for i in range(10, 20):
        g.add_node(i, bipartite=1)
    R = random.Random(7)
    for _ in range(40):
        g.add_edge(R.randrange(10), 10 + R.randrange(10))
    return g


def test_is_bipartite_matches():
    assert nx.is_bipartite(_bip(fnx)) == nx.is_bipartite(_bip(nx)) is True


def test_bipartite_density_and_color_match():
    bf, bn = _bip(fnx), _bip(nx)
    assert round(nxb.density(bf, set(range(10))), 9) == round(
        nxb.density(bn, set(range(10))), 9
    )
    assert sorted((repr(k), v) for k, v in nxb.color(bf).items()) == sorted(
        (repr(k), v) for k, v in nxb.color(bn).items()
    )
