"""Phase B certification: community detection (deterministic modularity
+ greedy/girvan-newman; seeded louvain/asyn-lpa — exact RNG parity) and
min-cost-flow / network-simplex. Zero divergences.
"""
import random

import networkx as nx
import networkx.algorithms.community as nxc
import pytest

import franken_networkx as fnx


def _mk():
    R = random.Random(43)
    ue = [(u, v) for u, v in ((R.randrange(20), R.randrange(20)) for _ in range(60)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def _C(communities):
    return sorted(sorted(repr(x) for x in c) for c in communities)


def _parts(g):
    # Partition the ACTUAL node set into 3 buckets (a fixed range may
    # reference nodes the random graph never created -> NotAPartition).
    nodes = sorted(g.nodes())
    third = max(1, len(nodes) // 3)
    return [set(nodes[:third]), set(nodes[third : 2 * third]), set(nodes[2 * third :])]


def test_modularity_and_partition_quality():
    gf, gn = _mk()
    pf, pn = _parts(gf), _parts(gn)
    assert pf == pn  # node sets identical -> identical partition
    assert round(nxc.modularity(gf, pf), 9) == round(nxc.modularity(gn, pn), 9)
    assert tuple(round(x, 9) for x in nxc.partition_quality(gf, pf)) == tuple(
        round(x, 9) for x in nxc.partition_quality(gn, pn)
    )


def test_greedy_and_girvan_newman_deterministic():
    gf, gn = _mk()
    assert _C(nxc.greedy_modularity_communities(gf)) == _C(nxc.greedy_modularity_communities(gn))
    assert _C(next(nxc.girvan_newman(gf))) == _C(next(nxc.girvan_newman(gn)))
    assert _C(nxc.label_propagation_communities(gf)) == _C(nxc.label_propagation_communities(gn))


@pytest.mark.parametrize("fn", ["asyn_lpa_communities", "louvain_communities"])
def test_seeded_community_detection(fn):
    gf, gn = _mk()
    assert _C(getattr(nxc, fn)(gf, seed=1)) == _C(getattr(nxc, fn)(gn, seed=1)), fn


def test_min_cost_flow_and_network_simplex():
    cf, cn = fnx.DiGraph(), nx.DiGraph()
    rc = random.Random(47)
    cap = [(u, v, rc.randrange(1, 9), rc.randrange(1, 5)) for u, v in ((rc.randrange(8), rc.randrange(8)) for _ in range(20)) if u != v]
    for u, v, c, w in cap:
        cf.add_edge(u, v, capacity=c, weight=w)
        cn.add_edge(u, v, capacity=c, weight=w)
    for g in (cf, cn):
        g.nodes[0]["demand"] = -5
        g.nodes[7]["demand"] = 5
    assert nx.min_cost_flow_cost(cf) == nx.min_cost_flow_cost(cn)
    assert nx.network_simplex(cf)[0] == nx.network_simplex(cn)[0]
