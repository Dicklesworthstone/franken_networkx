"""br-r37-c1-c1gz0: node/edge_connectivity disconnected short-circuit parity.

nx's GLOBAL connectivity branch returns 0 for disconnected inputs
(is_weakly_connected for directed, is_connected for undirected) before
any flow computation. The fnx wrappers mirror that natively so
disconnected graphs that would otherwise DELEGATE (self-loops,
multigraphs, flow_func) don't pay the _fnx_to_nx conversion tax
(562x on a disconnected self-loop graph) — and, more importantly,
return the identical value/error surface.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

FNS = ["node_connectivity", "edge_connectivity"]


def _rand(mod, directed, multi, n, m, selfloops, seed=7):
    cls = (
        (mod.MultiDiGraph if multi else mod.DiGraph)
        if directed
        else (mod.MultiGraph if multi else mod.Graph)
    )
    g = cls()
    g.add_nodes_from(range(n))
    r = random.Random(seed)
    for _ in range(m):
        u, v = r.randrange(n), r.randrange(n)
        if not selfloops and u == v:
            continue
        g.add_edge(u, v)
    return g


@pytest.mark.parametrize("fn", FNS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multi", [False, True])
@pytest.mark.parametrize("selfloops", [False, True])
def test_disconnected_returns_zero_like_nx(fn, directed, multi, selfloops):
    # sparse: components guaranteed (n=30, m=25)
    gn = _rand(nx, directed, multi, 30, 25, selfloops)
    gf = _rand(fnx, directed, multi, 30, 25, selfloops)
    assert getattr(fnx, fn)(gf) == getattr(nx, fn)(gn) == 0


@pytest.mark.parametrize("fn", FNS)
@pytest.mark.parametrize("directed", [False, True])
def test_connected_values_unchanged(fn, directed):
    gn = _rand(nx, directed, False, 12, 100, False)
    gf = _rand(fnx, directed, False, 12, 100, False)
    expected = getattr(nx, fn)(gn)
    assert getattr(fnx, fn)(gf) == expected
    assert expected > 0


@pytest.mark.parametrize("fn", FNS)
def test_st_pair_on_disconnected_not_short_circuited(fn):
    # local (s, t) connectivity must NOT hit the global short-circuit
    gn = _rand(nx, False, False, 20, 10, False)
    gf = _rand(fnx, False, False, 20, 10, False)
    assert getattr(fnx, fn)(gf, 0, 19) == getattr(nx, fn)(gn, 0, 19)


@pytest.mark.parametrize("fn", FNS)
def test_flow_func_disconnected_returns_zero(fn):
    from networkx.algorithms.flow import edmonds_karp

    gn = _rand(nx, False, False, 20, 8, False)
    gf = _rand(fnx, False, False, 20, 8, False)
    assert (
        getattr(fnx, fn)(gf, flow_func=edmonds_karp)
        == getattr(nx, fn)(gn, flow_func=edmonds_karp)
        == 0
    )


def test_edge_connectivity_cutoff_disconnected():
    gn = _rand(nx, True, False, 20, 8, False)
    gf = _rand(fnx, True, False, 20, 8, False)
    assert fnx.edge_connectivity(gf, cutoff=2) == nx.edge_connectivity(gn, cutoff=2) == 0


@pytest.mark.parametrize("fn", FNS)
def test_null_graph_still_raises(fn):
    with pytest.raises(fnx.NetworkXPointlessConcept):
        getattr(fnx, fn)(fnx.Graph())
