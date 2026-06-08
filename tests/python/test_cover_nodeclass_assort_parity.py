"""Phase B certification: covering, numeric/attribute assortativity,
average degree connectivity, node_classification (harmonic_function /
local_and_global_consistency), voronoi, group betweenness. Zero
divergences.
"""
import random

import networkx as nx
import networkx.algorithms.approximation as nxa
import networkx.algorithms.node_classification as nxnc

import franken_networkx as fnx


def _mk():
    R = random.Random(83)
    ue = [(u, v) for u, v in ((R.randrange(14), R.randrange(14)) for _ in range(45)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def test_covering_sizes():
    gf, gn = _mk()
    assert len(nx.min_edge_cover(gf)) == len(nx.min_edge_cover(gn))
    assert len(nxa.min_weighted_vertex_cover(gf)) == len(nxa.min_weighted_vertex_cover(gn))
    assert len(nxa.min_maximal_matching(gf)) == len(nxa.min_maximal_matching(gn))
    assert len(nxa.min_edge_dominating_set(gf)) == len(nxa.min_edge_dominating_set(gn))


def test_assortativity_and_connectivity():
    gf, gn = _mk()
    for n in gf.nodes():
        gf.nodes[n]["val"] = (n % 5) * 1.5
        gn.nodes[n]["val"] = (n % 5) * 1.5
    assert round(nx.numeric_assortativity_coefficient(gf, "val"), 9) == round(
        nx.numeric_assortativity_coefficient(gn, "val"), 9
    )
    assert round(nx.attribute_assortativity_coefficient(gf, "val"), 9) == round(
        nx.attribute_assortativity_coefficient(gn, "val"), 9
    )
    assert {k: round(v, 6) for k, v in nx.average_degree_connectivity(gf).items()} == {
        k: round(v, 6) for k, v in nx.average_degree_connectivity(gn).items()
    }
    assert {repr(k): round(v, 6) for k, v in nx.average_neighbor_degree(gf).items()} == {
        repr(k): round(v, 6) for k, v in nx.average_neighbor_degree(gn).items()
    }


def test_node_classification():
    R = random.Random(83)
    ue = [(u, v) for u, v in ((R.randrange(14), R.randrange(14)) for _ in range(45)) if u != v]
    gf, gn = fnx.Graph(ue), nx.Graph(ue)
    for g in (gf, gn):
        g.nodes[0]["label"] = "A"
        g.nodes[1]["label"] = "B"
    assert [repr(x) for x in nxnc.harmonic_function(gf)] == [repr(x) for x in nxnc.harmonic_function(gn)]
    assert [repr(x) for x in nxnc.local_and_global_consistency(gf)] == [
        repr(x) for x in nxnc.local_and_global_consistency(gn)
    ]


def test_voronoi_and_group_betweenness():
    gf, gn = _mk()
    assert {repr(k): sorted(repr(x) for x in v) for k, v in nx.voronoi_cells(gf, {0, 7}).items()} == {
        repr(k): sorted(repr(x) for x in v) for k, v in nx.voronoi_cells(gn, {0, 7}).items()
    }
    assert round(nx.group_betweenness_centrality(gf, [0, 1, 2]), 6) == round(
        nx.group_betweenness_centrality(gn, [0, 1, 2]), 6
    )
