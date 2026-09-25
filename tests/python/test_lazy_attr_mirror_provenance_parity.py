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


# A graph whose edge attributes sit only in the native store until a read: the
# attributed batch (20 edges, past its minimum), parse_edgelist, and copy()
# all leave the mirror lazy. On such a DiGraph the dict-of-dicts cache,
# adjacency() and the pandas edgelist used to treat the missing mirror as `{}`
# - and the first two then INSTALLED that empty dict, so the attributes were
# gone for every later read too.
LAZY_EDGES = [(i, i + 1, float(i) + 0.5) for i in range(20)]


def _lazy_weighted(lib, cls):
    graph = getattr(lib, cls)()
    graph.add_weighted_edges_from(LAZY_EDGES)
    return graph


def _lazy_parsed(lib, cls):
    lines = [f"{u} {v} {w}" for u, v, w in LAZY_EDGES]
    return lib.parse_edgelist(
        lines, nodetype=int, data=[("weight", float)], create_using=getattr(lib, cls)
    )


def _lazy_copied(lib, cls):
    return _lazy_weighted(lib, cls).copy()


LAZY_PROVENANCE = {"add_weighted_edges_from": _lazy_weighted, "parse_edgelist": _lazy_parsed, "copy": _lazy_copied}

READERS_FIRST = {
    "to_dict_of_dicts": lambda lib, g: lib.to_dict_of_dicts(g),
    "is_weighted": lambda lib, g: lib.is_weighted(g),
    "is_negatively_weighted": lambda lib, g: lib.is_negatively_weighted(g),
    "adjacency": lambda lib, g: [(n, dict(row)) for n, row in g.adjacency()],
    "to_edgelist": lambda lib, g: sorted((u, v, dict(d)) for u, v, d in lib.to_edgelist(g)),
    "to_pandas_edgelist": lambda lib, g: lib.to_pandas_edgelist(g)
    .sort_values(["source", "target"])
    .to_dict("records"),
}


@pytest.mark.parametrize("reader", sorted(READERS_FIRST))
@pytest.mark.parametrize("provenance", sorted(LAZY_PROVENANCE))
@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_first_reader_of_a_lazy_mirror_sees_and_keeps_the_attributes(cls, provenance, reader):
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = LAZY_PROVENANCE[provenance](lib, cls)
        first = READERS_FIRST[reader](lib, graph)
        after = sorted((u, v, dict(d)) for u, v, d in graph.edges(data=True))
        outcomes[name] = (first, after)
    assert outcomes["fnx"][0] == outcomes["nx"][0], f"{reader} read the lazy edges wrongly"
    assert outcomes["fnx"][1] == outcomes["nx"][1], f"{reader} erased the edge attributes"


# The native store keys attributes by String and keeps them in a BTreeMap, so
# a dict rebuilt from it has str keys, sorted, and scalar values of bounded
# size. A site may leave an edge to be rebuilt only when that loses nothing.
NON_STR_KEY_DATA = {"int key": {5: 1.5}, "tuple key": {(1, 2): 3.0}, "mixed": {5: 1.5, "w": 2.0}}


@pytest.mark.parametrize("shape", sorted(NON_STR_KEY_DATA))
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_non_str_attr_keys_survive_the_attributed_batch(cls, shape):
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = getattr(lib, cls)()
        graph.add_edges_from([(i, i + 1, dict(NON_STR_KEY_DATA[shape])) for i in range(20)])
        data = graph[0][1][0] if graph.is_multigraph() else graph[0][1]
        outcomes[name] = [(key, type(key).__name__, value) for key, value in data.items()]
    assert outcomes["fnx"] == outcomes["nx"]


STORE_REBUILT_EDGE_DATA = {
    "big int": {"weight": 2, "tag": 2**70},
    "unsorted keys": {"weight": 1, "color": "red"},
    "no weight, later key": {"zeta": 1},
    "sorted scalars": {"alpha": 1, "weight": 3.0},
}


@pytest.mark.parametrize("shape", sorted(STORE_REBUILT_EDGE_DATA))
@pytest.mark.parametrize("op", ["reverse", "stochastic_graph"])
def test_store_rebuilt_multidigraph_edges_keep_value_type_and_order(op, shape):
    data = STORE_REBUILT_EDGE_DATA[shape]
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = lib.MultiDiGraph()
        graph.add_edge(0, 1, **data)
        graph.add_edge(0, 2, **{**data, "weight": 5} if "weight" in data else data)
        result = graph.reverse() if op == "reverse" else lib.stochastic_graph(graph)
        outcomes[name] = [
            (u, v, k, [(key, type(value).__name__, value) for key, value in d.items()])
            for u, v, k, d in sorted(result.edges(keys=True, data=True), key=repr)
        ]
    assert outcomes["fnx"] == outcomes["nx"]


def _lazy_spanning_input(lib):
    graph = lib.Graph()
    ring = [(i, (i + 1) % 30, float(i % 5) + 1) for i in range(30)]
    chords = [(i, (i + 7) % 30, float(i % 3) + 2) for i in range(30)]
    graph.add_weighted_edges_from(ring + chords)
    return graph


def test_partition_spanning_tree_of_a_lazy_mirror_keeps_edge_attributes():
    trees = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        trees[name] = sorted(lib.partition_spanning_tree(_lazy_spanning_input(lib)).edges(data=True))
    assert trees["fnx"] == trees["nx"]


def test_random_spanning_tree_of_a_lazy_mirror_samples_by_its_weights():
    """networkx returns the tree WITHOUT attributes; the weights only drive the
    sampling, so a run that lost them would sample a different tree."""
    trees = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        tree = lib.random_spanning_tree(_lazy_spanning_input(lib), weight="weight", seed=3)
        trees[name] = sorted(tree.edges(data=True))
    assert trees["fnx"] == trees["nx"]


def test_nan_attribute_keeps_the_callers_object():
    """A NaN rebuilt from the store is a different object and NaN != NaN, so a
    dict holding it stops comparing equal to networkx's; the batch keeps it."""
    nan = float("nan")
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = lib.Graph()
        graph.add_edges_from([(i, i + 1, {"w": nan}) for i in range(20)])
        data = graph[0][1]
        outcomes[name] = (data["w"] is nan, data == {"w": nan})
    assert outcomes["fnx"] == outcomes["nx"] == (True, True)
