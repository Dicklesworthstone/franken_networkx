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


def _lazy_weighted_with(lib, cls, extra):
    graph = getattr(lib, cls)()
    ring = [(i, (i + 1) % 12, float(i % 4) + 1.5) for i in range(12)]
    graph.add_weighted_edges_from(ring + extra)
    return graph


def _outcome(call):
    try:
        return ("ok", call())
    except Exception as exc:  # noqa: BLE001 - the raise is the contract
        return (type(exc).__name__, exc.args)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_dijkstra_sees_a_negative_weight_held_only_in_the_store(cls):
    """The delegation check scanned only the Python mirrors, so a negative
    weight on a lazily mirrored DiGraph ran the native kernel (distance 1.0)
    where networkx raises."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = _lazy_weighted_with(lib, cls, [(20, 21, -7.0), (21, 20, 3.0)])
        outcomes[name] = _outcome(lambda: lib.single_source_dijkstra_path_length(graph, 20))
    assert outcomes["fnx"] == outcomes["nx"]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_floyd_warshall_numpy_reads_weights_held_only_in_the_store(cls):
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = _lazy_weighted_with(lib, cls, [])
        outcomes[name] = lib.floyd_warshall_numpy(graph).tolist()
    assert outcomes["fnx"] == outcomes["nx"]


@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka"])
@pytest.mark.parametrize("which", ["minimum_spanning_edges", "maximum_spanning_edges"])
def test_spanning_edges_of_a_partly_mirrored_graph_keep_every_edges_data(which, algorithm):
    """Reading an edge mirrors only that edge; the emitter read the mirror
    alone and yielded {} for every other edge, and the wrapper's re-run
    fired only when NO emitted edge had a mirror. (0, 1) is in the minimum
    tree and (29, 0) in the maximum one, so each tree holds a mirrored edge."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = _lazy_spanning_input(lib)
        _ = graph[0][1], graph[29][0]
        edges = getattr(lib, which)(graph, algorithm=algorithm, data=True)
        outcomes[name] = sorted((min(u, v), max(u, v), sorted(d.items())) for u, v, d in edges)
    assert outcomes["fnx"] == outcomes["nx"]


@pytest.mark.parametrize("call", ["single_source", "all_pairs"])
def test_dijkstra_sees_a_negative_weight_on_a_reversed_multidigraph(call):
    """A MultiDiGraph batch mirrors every edge, but reverse() leaves the result
    store-only; the multigraph arms of the delegation check scanned the mirrors
    alone, so the native kernel ran on the negative weight."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = _lazy_weighted_with(lib, "MultiDiGraph", [(20, 21, -7.0), (21, 20, 3.0)]).reverse()
        if call == "single_source":
            outcomes[name] = _outcome(lambda: lib.single_source_dijkstra_path_length(graph, 20))
        else:
            outcomes[name] = _outcome(lambda: dict(lib.all_pairs_dijkstra_path_length(graph)))
    assert outcomes["fnx"] == outcomes["nx"]


def _store_only_graph(lib, cls, node_attrs):
    """Edge attributes held only in the store, with NO mirror at all: a weighted
    batch leaves Graph and DiGraph so; a MultiDiGraph batch mirrors, but reverse()
    of round-tripping dicts does not. (5, 0) repeats (0, 5): one undirected edge,
    and two arcs that to_undirected merges."""
    graph = getattr(lib, cls)()
    ring = [(i, (i + 1) % 12, float(i % 4) + 1.5) for i in range(12)]
    graph.add_weighted_edges_from(ring + [(0, 5, 2.5), (5, 0, 3.5)])
    if cls == "MultiDiGraph":
        graph = graph.reverse()
    if node_attrs:
        for node in graph:
            graph.nodes[node]["color"] = node % 3
    return graph


@pytest.mark.parametrize(
    "cls, method",
    [
        ("Graph", "to_directed"),
        ("DiGraph", "to_undirected"),
        ("MultiDiGraph", "to_directed"),
        ("MultiDiGraph", "to_undirected"),
    ],
)
@pytest.mark.parametrize("node_attrs", [False, True])
def test_conversion_of_a_store_only_graph_keeps_edge_attributes(cls, method, node_attrs):
    """The deep-copy kernels read an EMPTY mirror map as "no edge attributes"
    (MultiDiGraph: {} for any arc without a mirror). node_attrs=True is the shape
    a removed re-run wrapper made slower than networkx."""
    rows = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        result = getattr(_store_only_graph(lib, cls, node_attrs), method)()
        keys = {"keys": True} if result.is_multigraph() else {}
        rows[name] = sorted(map(repr, result.edges(data=True, **keys)))
    assert rows["fnx"] == rows["nx"]


# Seven more edges make a batch of eight: the native batch paths start there.
_BATCH_TAIL = [(20 + i, 21 + i, {"w": 1}) for i in range(7)]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("via", ["add_edges_from", "update"])
def test_attributed_batch_merges_into_a_store_only_edge(cls, via):
    """networkx updates the edge's dict; the batch started an EMPTY mirror for an
    edge whose weight lived only in the store, and reads trust the mirror."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = _lazy_weighted_with(lib, cls, [])
        batch = [(0, 1, {"b": "x"})] + _BATCH_TAIL
        if via == "update":
            graph.update(edges=batch)
        else:
            graph.add_edges_from(batch)
        outcomes[name] = dict(graph[0][1])
    assert outcomes["fnx"] == outcomes["nx"] == {"weight": 1.5, "b": "x"}


@pytest.mark.parametrize("nodes", ["contiguous", "scrambled"])
def test_repeated_undirected_pair_in_one_batch_merges(nodes):
    """(u, v) then (v, u) is ONE undirected edge. The batches onto pre-added int
    nodes de-duplicated on the ordered pair, so the second dict replaced the
    first. DiGraph-subclass .to_undirected() rebuilds through this very call."""
    order = list(range(40)) if nodes == "contiguous" else [(i * 7) % 40 for i in range(40)]
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = lib.Graph()
        graph.add_nodes_from(order)
        graph.add_edges_from(
            [(30, 31, {"weight": 1.5, "a": 1}), (31, 30, {"weight": 9.0, "b": "x"})] + _BATCH_TAIL[:6]
        )
        outcomes[name] = dict(graph[30][31])
    assert outcomes["fnx"] == outcomes["nx"] == {"weight": 9.0, "a": 1, "b": "x"}


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_mixed_pairs_and_triples_touching_an_existing_edge(cls):
    """An early (u, v) that already exists made the batch replay every edge as a
    pair - ValueError on the first 3-tuple after it."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = _lazy_weighted_with(lib, cls, [])
        outcome = _outcome(lambda: graph.add_edges_from([(0, 1)] + _BATCH_TAIL))
        outcomes[name] = (outcome, sorted(map(repr, graph.edges(data=True))))
    assert outcomes["fnx"] == outcomes["nx"]


_WEIGHT_KINDS = {
    "float": lambda i: float(i % 5) + 1.5,
    "int": lambda i: i % 5 + 1,
    "mixed": lambda i: float(i % 5) + 1.5 if i % 2 else i % 5 + 1,
}


@pytest.mark.parametrize("kind", sorted(_WEIGHT_KINDS))
def test_weighted_degree_of_a_reversed_multidigraph_after_one_edge_is_read(kind):
    """reverse() leaves a MultiDiGraph store-only; reading ONE edge gives it a
    mirror and marks the graph dirty, and the dirty readers counted every edge
    WITHOUT a mirror as weight 1 - size(weight=) was 24.5 against 82.0."""
    ring = [(i, (i + 1) % 24, _WEIGHT_KINDS[kind](i)) for i in range(24)]
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = lib.MultiDiGraph()
        graph.add_weighted_edges_from(ring)
        graph = graph.reverse()
        _ = graph.get_edge_data(1, 0, 0)
        outcomes[name] = (
            sorted(graph.degree(weight="weight")),
            sorted(graph.in_degree(weight="weight")),
            sorted(graph.out_degree(weight="weight")),
            sorted(graph.degree([0, 5, 9], weight="weight")),
            sorted(graph.in_degree([0, 5, 9], weight="weight")),
            graph.degree(3, weight="weight"),
            graph.size(weight="weight"),
        )
    assert outcomes["fnx"] == outcomes["nx"]


def _reversed_multidigraph(lib):
    graph = lib.MultiDiGraph()
    graph.add_weighted_edges_from([(i, (i + 1) % 12, float(i % 4) + 1.5) for i in range(12)])
    return graph.reverse()


def _pickle_round_trip(graph):
    """What pickle.loads(pickle.dumps(graph)) rebuilds, without unpickling."""
    reduced = graph.__reduce_ex__(2)
    rebuild, args = reduced[0], reduced[1]
    state = reduced[2] if len(reduced) > 2 else None
    clone = rebuild(*args)
    if state is not None:
        setstate = getattr(clone, "__setstate__", None)
        if setstate is not None:
            setstate(state)
        else:  # pickle's own fallback for a plain Python object
            clone.__dict__.update(state)
    return clone


def _keyed_rows(graph):
    return sorted(map(repr, graph.edges(keys=True, data=True)))


def _adjacency_rows(pairs):
    return sorted(
        repr((u, v, sorted((k, sorted(d.items())) for k, d in keydict.items())))
        for u, nbrs in pairs
        for v, keydict in nbrs.items()
    )


_STORE_ONLY_READS = {
    "pickle": lambda g: _keyed_rows(_pickle_round_trip(g)),
    "adjacency": lambda g: _adjacency_rows(g.adjacency()),
    "pred": lambda g: _adjacency_rows(g.pred.items()),
    "subgraph_copy": lambda g: _keyed_rows(g.subgraph(list(range(8))).copy()),
}


@pytest.mark.parametrize("read", sorted(_STORE_ONLY_READS))
def test_store_only_multidigraph_hands_out_its_edge_attributes(read):
    """reverse() leaves every MultiDiGraph edge store-only; readers that hand an
    edge's dict out used the mirror or a fresh EMPTY dict, so a pickled or
    subgraph-copied reverse() came back with every edge {}."""
    rows = {
        name: _STORE_ONLY_READS[read](_reversed_multidigraph(lib))
        for name, lib in (("nx", nx), ("fnx", fnx))
    }
    assert rows["fnx"] == rows["nx"]
    assert "'weight'" in repr(rows["fnx"])


@pytest.mark.parametrize(
    "cls, source",
    [
        ("DiGraph", "batch"),
        ("DiGraph", "reverse"),
        ("MultiDiGraph", "reverse"),
        ("MultiGraph", "ctor"),
        ("MultiDiGraph", "ctor"),
    ],
)
@pytest.mark.parametrize("form", ["dict", "dict_of_dicts", "scalar_all"])
def test_set_edge_attributes_on_a_store_only_edge_keeps_its_other_attributes(cls, source, form):
    """The native setters started an EMPTY mirror for an edge whose attributes
    lived only in the store, so setting one attribute replaced them all - the
    weight vanished. scalar_all is the control (a different path)."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = getattr(lib, cls)()
        graph.add_weighted_edges_from([(i, (i + 1) % 12, float(i % 4) + 1.5) for i in range(12)])
        if source == "reverse":
            graph = graph.reverse()
        elif source == "ctor":  # the class constructor leaves a MultiGraph store-only
            graph = getattr(lib, cls)(lib.Graph(graph))
        edge = next(iter(graph.edges(keys=True) if graph.is_multigraph() else graph.edges()))
        if form == "dict":
            lib.set_edge_attributes(graph, {edge: "red"}, "color")
        elif form == "dict_of_dicts":
            lib.set_edge_attributes(graph, {edge: {"color": "red"}})
        else:
            lib.set_edge_attributes(graph, "red", "color")
        keys = {"keys": True} if graph.is_multigraph() else {}
        outcomes[name] = sorted(map(repr, graph.edges(data=True, **keys)))
    assert outcomes["fnx"] == outcomes["nx"]


# Eight weighted edges take the native batch, which leaves them store-only.
_STORE_ONLY_TAIL = [(10 + i, 11 + i, 1.0) for i in range(8)]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("store_only", ["G", "H"])
def test_compose_merges_an_overlapping_edge_held_only_in_the_store(cls, store_only):
    """networkx updates the overlapping edge's dict with H's; the native compose
    merged MIRRORS only, so H's dict replaced G's store-only attributes, or G's
    mirror never saw H's store-only values."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        G, H = getattr(lib, cls)(), getattr(lib, cls)()
        batch, mirrored = (G, H) if store_only == "G" else (H, G)
        batch.add_weighted_edges_from([(0, 1, 7.5)] + _STORE_ONLY_TAIL)
        mirrored.add_edge(0, 1, source="mirror", weight=None)
        outcomes[name] = (dict(lib.compose(G, H)[0][1]), dict(lib.compose(H, G)[0][1]))
    assert outcomes["fnx"] == outcomes["nx"]


def test_digraph_to_undirected_merges_a_mirrored_arc_with_its_store_only_reverse():
    """0->1 re-added gets a mirror, 1->0 stays store-only; networkx applies 1->0's
    dict last, the kernel merged it into the store only and read 0->1's 9.0.
    (Int nodes: the batch must take the store-only native path.)"""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = lib.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 1.0), (1, 0, 2.0)] + _STORE_ONLY_TAIL)
        graph.add_edge(0, 1, weight=9.0)
        outcomes[name] = dict(graph.to_undirected()[0][1])
    assert outcomes["fnx"] == outcomes["nx"] == {"weight": 2.0}


# THE PROVENANCE CONTRACT, over every public callable that takes a weight: two
# graphs with IDENTICAL content - one built edge by edge (each edge gets an
# eager Python mirror), one by add_weighted_edges_from (mirrors stay lazy, the
# attributes live only in the native store) - must give identical results. A
# difference is a reader that trusts the mirror alone. This found the Dijkstra
# delegation check and floyd_warshall_numpy (br-r37-c1-qry3d) and the spanning
# tree builder (br-r37-c1-7ila9); networkx is not needed as an oracle here.
import inspect as _inspect
import itertools as _itertools
import math as _math

_PROVENANCE_RING = [(i, (i + 1) % 24, float(i % 5) + 1.5) for i in range(24)]
_PROVENANCE_CHORDS = [(i, (i + 7) % 24, float(i % 3) + 2.25) for i in range(0, 24, 2)]
_PROVENANCE_EDGE_SETS = {
    "positive": _PROVENANCE_RING + _PROVENANCE_CHORDS,
    "negative": _PROVENANCE_RING + _PROVENANCE_CHORDS + [(30, 31, -7.0), (31, 30, 3.0)],
}
_PROVENANCE_FILL = {
    "source": 0, "target": 12, "s": 0, "t": 12, "u": 0, "v": 12, "n": 0, "node": 0,
    "k": 2, "seed": 1, "cutoff": None, "sources": [0, 3], "targets": [12],
    "max_iter": 200, "nodelist": None, "weight": "weight", "capacity": "weight",
    "nbunch": None, "normalized": True, "ebunch": [(0, 12), (3, 9)],
}


def _provenance_graph(cls, edges, mode):
    """`eager`: every edge mirrored; `lazy`: none; `partial`: lazy, then one
    edge read, so exactly one is mirrored - the state that defeated readers
    which re-ran only when NO edge had a mirror (minimum_spanning_edges)."""
    graph = getattr(fnx, cls)()
    if mode == "eager":
        for u, v, w in edges:
            graph.add_edge(u, v, weight=w)
        return graph
    graph.add_weighted_edges_from(edges)
    if mode == "partial":
        u, v, _w = edges[0]
        _ = graph[u][v]
    return graph


def _provenance_norm(value, depth=0):
    if depth > 4:
        return repr(type(value))
    if isinstance(value, float):
        return "nan" if _math.isnan(value) else round(value, 6)
    if isinstance(value, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)):
        return (sorted(map(repr, value.nodes(data=True))), sorted(map(repr, value.edges(data=True))))
    if isinstance(value, dict):
        return sorted(((repr(k), _provenance_norm(v, depth + 1)) for k, v in value.items()), key=repr)
    if isinstance(value, (list, tuple)):
        return [_provenance_norm(v, depth + 1) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(repr(_provenance_norm(v, depth + 1)) for v in value)
    if hasattr(value, "toarray"):
        return _provenance_norm(value.toarray().tolist(), depth + 1)
    if hasattr(value, "tolist"):
        return _provenance_norm(value.tolist(), depth + 1)
    if _inspect.isgenerator(value) or type(value).__name__ in ("generator", "map", "zip"):
        return _provenance_norm(list(_itertools.islice(value, 200)), depth + 1)
    return repr(value)


def _provenance_call(fn, graph):
    kwargs = {}
    for param in list(_inspect.signature(fn).parameters.values())[1:]:
        if param.name in _PROVENANCE_FILL:
            kwargs[param.name] = _PROVENANCE_FILL[param.name]
        elif param.default is _inspect.Parameter.empty and param.kind in (
            param.POSITIONAL_OR_KEYWORD,
            param.KEYWORD_ONLY,
        ):
            return None  # needs an argument this contract cannot invent
    try:
        return ("ok", _provenance_norm(fn(graph, **kwargs)))
    except Exception as exc:  # noqa: BLE001 - the raise is part of the answer
        return ("raise", type(exc).__name__, str(exc)[:80])


def _weighted_public_callables():
    names = []
    for name in sorted(dir(fnx)):
        fn = getattr(fnx, name)
        if name.startswith("_") or not callable(fn) or isinstance(fn, type):
            continue
        try:
            parameters = _inspect.signature(fn).parameters
        except (TypeError, ValueError):
            continue
        if "weight" in parameters or "capacity" in parameters:
            names.append(name)
    return names


@pytest.mark.parametrize("name", _weighted_public_callables())
def test_weighted_callable_does_not_depend_on_mirror_provenance(name):
    fn = getattr(fnx, name)
    for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        for label, edges in _PROVENANCE_EDGE_SETS.items():
            eager = _provenance_call(fn, _provenance_graph(cls, edges, "eager"))
            for mode in ("lazy", "partial"):
                other = _provenance_call(fn, _provenance_graph(cls, edges, mode))
                assert eager == other, (
                    f"{name} on {cls} ({label} weights): eager {eager!r:.160} {mode} {other!r:.160}"
                )
