"""Attribute reads must not depend on whether the lazy Python mirror was materialised.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.2: fnx keeps edge attributes in
the native store and materialises the per-edge Python dicts (``edge_py_attrs``)
lazily. Several readers trusted the mirror alone, so on a graph built natively
(every generator) they saw "no attributes" until something like
``edges(data=True)`` ran:

* ``community.modularity(karate_club_graph(), comms)`` returned the unweighted
  0.3905 instead of 0.4266;
* ``DiGraph(G)`` / ``MultiGraph(G)`` of such a graph silently dropped every edge
  attribute (so to_scipy_sparse_array / pagerank of the converted graph were
  unweighted);
* ``MultiDiGraph.size(weight=...)`` summed only materialised edges.

Every assertion below runs on a FRESH generator-built graph (mirror empty) and
again after touching the attribute view — the untouched column is the negative
case a mirror-only implementation fails.
"""

from __future__ import annotations

import numpy as np
import networkx as nx
import pytest

import franken_networkx as fnx

pytest.importorskip("scipy")


def _touch(G):
    list(G.edges(data=True))
    return G


@pytest.fixture(params=["untouched", "touched"])
def touch(request):
    return (lambda G: G) if request.param == "untouched" else _touch


GENERATORS = ["karate_club_graph", "les_miserables_graph"]


@pytest.mark.parametrize("gen", GENERATORS)
def test_modularity_uses_weights_on_generator_graphs(gen, touch):
    gnx = getattr(nx, gen)()
    comms = [set(c) for c in nx.community.louvain_communities(gnx, seed=7)]
    gfx = touch(getattr(fnx, gen)())
    assert fnx.community.modularity(gfx, comms) == pytest.approx(
        nx.community.modularity(gnx, comms), abs=1e-12
    )


def _karate_rows():
    return list(nx.karate_club_graph().edges(data=True))


def _via_add_edges_from():
    G = fnx.Graph()
    G.add_edges_from(_karate_rows())
    return G


def _via_add_weighted_edges_from():
    G = fnx.Graph()
    G.add_weighted_edges_from((u, v, d["weight"]) for u, v, d in _karate_rows())
    return G


# Every construction path the graph core has for weighted edges; each yields a
# graph whose Python attr mirror may or may not be materialised.
PROVENANCE = {
    "generator": fnx.karate_club_graph,
    "add_edges_from": _via_add_edges_from,
    "add_weighted_edges_from": _via_add_weighted_edges_from,
    "from_networkx": lambda: fnx.Graph(nx.karate_club_graph()),
    "copy": lambda: fnx.karate_club_graph().copy(),
    "subgraph_copy": lambda: fnx.karate_club_graph().subgraph(range(34)).copy(),
}


@pytest.mark.parametrize("provenance", sorted(PROVENANCE))
def test_weight_readers_agree_across_provenance(provenance, touch):
    gnx = nx.karate_club_graph()
    comms = [set(c) for c in nx.community.louvain_communities(gnx, seed=7)]
    gfx = touch(PROVENANCE[provenance]())
    assert fnx.community.modularity(gfx, comms) == pytest.approx(
        nx.community.modularity(gnx, comms), abs=1e-12
    )
    # Edge-list builds order nodes by first appearance, so fix the node order.
    nodelist = list(range(34))
    np.testing.assert_allclose(
        fnx.to_scipy_sparse_array(fnx.DiGraph(gfx), nodelist=nodelist).toarray(),
        nx.to_scipy_sparse_array(nx.DiGraph(gnx), nodelist=nodelist).toarray(),
    )
    assert fnx.MultiGraph(gfx).size(weight="weight") == pytest.approx(gnx.size(weight="weight"))


def _edge_rows(G):
    if G.is_multigraph():
        return [(str(u), str(v), k, dict(d)) for u, v, k, d in G.edges(keys=True, data=True)]
    return [(str(u), str(v), dict(d)) for u, v, d in G.edges(data=True)]


@pytest.mark.parametrize("gen", GENERATORS)
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_class_constructor_preserves_edge_attrs(gen, cls, touch):
    src = touch(getattr(fnx, gen)())
    got = getattr(fnx, cls)(src)
    want = getattr(nx, cls)(getattr(nx, gen)())
    assert _edge_rows(got) == _edge_rows(want)
    # the native store must carry the weights too (kernels read it)
    assert got.size(weight="weight") == pytest.approx(want.size(weight="weight"))


@pytest.mark.parametrize("gen", GENERATORS)
def test_converted_digraph_matrix_and_pagerank_are_weighted(gen, touch):
    dfx = fnx.DiGraph(touch(getattr(fnx, gen)()))
    dnx = nx.DiGraph(getattr(nx, gen)())
    np.testing.assert_allclose(
        fnx.to_scipy_sparse_array(dfx).toarray(), nx.to_scipy_sparse_array(dnx).toarray()
    )
    pf, pn = fnx.pagerank(dfx), nx.pagerank(dnx)
    assert list(pf) == list(pn)
    np.testing.assert_allclose(list(pf.values()), list(pn.values()), rtol=1e-9)


@pytest.mark.parametrize("gen", GENERATORS)
def test_multidigraph_size_weight_counts_unmaterialised_edges(gen):
    mfx = fnx.MultiDiGraph(getattr(fnx, gen)())
    mnx = nx.MultiDiGraph(getattr(nx, gen)())
    assert mfx.size(weight="weight") == pytest.approx(mnx.size(weight="weight"))
    # partially materialised: touch one edge's dict, mutate it, sum again
    u, v, k = next(iter(mfx.edges(keys=True)))
    mfx[u][v][k]["weight"] = 1000
    mnx[u][v][k]["weight"] = 1000
    assert mfx.size(weight="weight") == pytest.approx(mnx.size(weight="weight"))


def test_random_spanning_tree_missing_weight_key_raises_like_networkx():
    G = fnx.karate_club_graph()  # mirror unmaterialised, every edge has 'weight'
    with pytest.raises(KeyError):
        nx.random_spanning_tree(nx.karate_club_graph(), weight="missing", seed=1)
    with pytest.raises(KeyError):
        fnx.random_spanning_tree(G, weight="missing", seed=1)
