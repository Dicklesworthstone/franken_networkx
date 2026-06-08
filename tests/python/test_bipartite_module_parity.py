"""Phase B certification: bipartite module — projections, matching,
vertex cover, centralities, clustering, redundancy, spectral
bipartivity. Identical fixed bipartite graphs. Zero divergences.
"""
import random

import networkx as nx
import networkx.algorithms.bipartite as nxb

import franken_networkx as fnx


def _mk(mod):
    # Dense, connected, every node degree >= 2 so node_redundancy and
    # bipartite_sets/matching are well-defined (a sparse random graph
    # yields isolated/degree-1 nodes -> both impls raise identically,
    # which is an nx contract, not a divergence).
    g = mod.Graph()
    for i in range(6):
        g.add_node(i, bipartite=0)
    for i in range(6, 12):
        g.add_node(i, bipartite=1)
    R = random.Random(53)
    # ring backbone guarantees connectivity + min degree 2
    for i in range(6):
        g.add_edge(i, 6 + i)
        g.add_edge(i, 6 + ((i + 1) % 6))
    for _ in range(10):
        g.add_edge(R.randrange(6), 6 + R.randrange(6))
    return g


_TOP = set(range(6))


def _D(d):
    return sorted((repr(k), round(float(v), 6)) for k, v in d.items())


def _EW(g, weighted=True):
    if weighted:
        return sorted(
            (min(repr(u), repr(v)), max(repr(u), repr(v)), round(d.get("weight"), 6))
            for u, v, d in g.edges(data=True)
        )
    return sorted((min(repr(u), repr(v)), max(repr(u), repr(v))) for u, v in g.edges())


def test_bipartite_basics_and_projection():
    bf, bn = _mk(fnx), _mk(nx)
    assert nx.is_bipartite(bf) == nx.is_bipartite(bn) is True
    assert round(nxb.density(bf, _TOP), 9) == round(nxb.density(bn, _TOP), 9)
    assert _EW(nxb.projected_graph(bf, _TOP), weighted=False) == _EW(
        nxb.projected_graph(bn, _TOP), weighted=False
    )
    assert _EW(nxb.weighted_projected_graph(bf, _TOP)) == _EW(nxb.weighted_projected_graph(bn, _TOP))
    assert _EW(nxb.overlap_weighted_projected_graph(bf, _TOP)) == _EW(
        nxb.overlap_weighted_projected_graph(bn, _TOP)
    )


def test_bipartite_matching_and_cover():
    bf, bn = _mk(fnx), _mk(nx)
    assert sorted((repr(k), repr(v)) for k, v in nxb.hopcroft_karp_matching(bf, top_nodes=_TOP).items()) == sorted(
        (repr(k), repr(v)) for k, v in nxb.hopcroft_karp_matching(bn, top_nodes=_TOP).items()
    )
    assert sorted(repr(x) for x in nxb.to_vertex_cover(bf, nxb.maximum_matching(bf, top_nodes=_TOP), _TOP)) == sorted(
        repr(x) for x in nxb.to_vertex_cover(bn, nxb.maximum_matching(bn, top_nodes=_TOP), _TOP)
    )


def test_bipartite_centrality_clustering_redundancy():
    bf, bn = _mk(fnx), _mk(nx)
    assert _D(nxb.degree_centrality(bf, _TOP)) == _D(nxb.degree_centrality(bn, _TOP))
    assert _D(nxb.betweenness_centrality(bf, _TOP)) == _D(nxb.betweenness_centrality(bn, _TOP))
    assert _D(nxb.closeness_centrality(bf, _TOP)) == _D(nxb.closeness_centrality(bn, _TOP))
    assert _D(nxb.clustering(bf)) == _D(nxb.clustering(bn))
    assert round(nxb.robins_alexander_clustering(bf), 9) == round(nxb.robins_alexander_clustering(bn), 9)
    assert _D(nxb.node_redundancy(bf)) == _D(nxb.node_redundancy(bn))
    assert round(nxb.spectral_bipartivity(bf), 6) == round(nxb.spectral_bipartivity(bn), 6)
