"""Parity for ``dijkstra_predecessor_and_distance`` pred dict order.

Bead br-r37-c1-0l76i. nx populates the predecessor dict in
edge-relaxation insertion order during traversal: pred[v] appears
in the dict at the moment a tentative shortest path to v is found,
not when v's distance is finalized. The previous local
implementation built ``pred = {node: predecessors[node] for node
in distances}`` which forced pred-key order to match distances-
iteration order — drifting from nx.

Repro:
  edges = [(a,b,1),(b,c,2),(c,d,1),(a,d,5),(b,d,3)]
  fnx (pre-fix) pred -> {a:[], b:[a], c:[b], d:[b,c]}
  nx pred             -> {a:[], b:[a], d:[b,c], c:[b]}

(d lands before c because (b,d) edge relaxation happens before
c is popped from the heap.)
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_weighted(lib, edges):
    g = lib.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
def test_repro_pred_dict_keys_match_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5), ("b", "d", 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, f_dist = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, n_dist = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred
    assert list(f_dist.keys()) == list(n_dist.keys())
    assert f_dist == n_dist


@needs_nx
def test_pred_keys_match_with_cutoff():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, f_dist = fnx.dijkstra_predecessor_and_distance(g, "a", cutoff=3)
    n_pred, n_dist = nx.dijkstra_predecessor_and_distance(gx, "a", cutoff=3)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred
    assert f_dist == n_dist


@needs_nx
def test_pred_keys_match_int_nodes():
    edges = [(0, 1, 1), (1, 2, 2), (2, 3, 1), (0, 3, 5), (1, 3, 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_directed():
    edges = [(0, 1, 1), (1, 2, 2), (2, 3, 1), (0, 3, 5), (1, 3, 3)]
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v, w in edges:
        dg.add_edge(u, v, weight=w)
        dgx.add_edge(u, v, weight=w)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(dg, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(dgx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_path_graph():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_unweighted_graph():
    """With no weights, default weight=1; algorithm reduces to BFS."""
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, 0)
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, 0)
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_custom_weight_attr():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, custom=w)
        gx.add_edge(u, v, custom=w)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a", weight="custom")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a", weight="custom")
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_isolated_source():
    """Source with no edges: pred should be {source: []}."""
    g = fnx.Graph()
    g.add_node("a")
    gx = nx.Graph()
    gx.add_node("a")
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert f_pred == n_pred


@needs_nx
def test_pred_keys_match_disconnected_graph():
    """Source in one component; other component nodes shouldn't be in pred."""
    edges = [("a", "b", 1), ("c", "d", 1)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert list(f_pred.keys()) == list(n_pred.keys())
    assert f_pred == n_pred


@needs_nx
def test_missing_source_raises():
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NodeNotFound):
        fnx.dijkstra_predecessor_and_distance(g, "missing")


@needs_nx
def test_pred_values_match_when_keys_already_match():
    """Triangle: a-b, b-c, a-c with various weights to force ties."""
    edges = [("a", "b", 1), ("b", "c", 1), ("a", "c", 2)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f_pred, _ = fnx.dijkstra_predecessor_and_distance(g, "a")
    n_pred, _ = nx.dijkstra_predecessor_and_distance(gx, "a")
    assert f_pred == n_pred
    assert list(f_pred.keys()) == list(n_pred.keys())


@needs_nx
@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
def test_native_predecessor_path_matches_nx_without_parity_fallback(
    monkeypatch, fnx_factory, nx_factory
):
    edges = [
        ("s", "a", 1),
        ("s", "b", 1),
        ("a", "t", 2),
        ("b", "t", 2),
        ("a", "c", 1),
        ("b", "c", 1),
        ("c", "u", 1.5),
    ]
    g = fnx_factory()
    gx = nx_factory()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)

    def fail_parity(*args, **kwargs):
        raise AssertionError("native dijkstra_predecessor_and_distance should not delegate")

    monkeypatch.setattr(fnx, "_call_networkx_for_parity", fail_parity)
    f_pred, f_dist = fnx.dijkstra_predecessor_and_distance(g, "s", weight="weight")
    n_pred, n_dist = nx.dijkstra_predecessor_and_distance(gx, "s", weight="weight")

    assert list(f_pred.items()) == list(n_pred.items())
    assert [(node, type(dist).__name__, dist) for node, dist in f_dist.items()] == [
        (node, type(dist).__name__, dist) for node, dist in n_dist.items()
    ]


@needs_nx
def test_native_predecessor_cutoff_and_int_float_distance_types():
    edges = [
        ("s", "a", 1),
        ("a", "b", 2),
        ("b", "c", 1.25),
        ("s", "d", 4),
        ("d", "c", 0.25),
        ("c", "z", 1),
    ]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)

    f_pred, f_dist = fnx.dijkstra_predecessor_and_distance(
        g, "s", cutoff=4.25, weight="weight"
    )
    n_pred, n_dist = nx.dijkstra_predecessor_and_distance(
        gx, "s", cutoff=4.25, weight="weight"
    )

    assert list(f_pred.items()) == list(n_pred.items())
    assert [(node, type(dist).__name__, dist) for node, dist in f_dist.items()] == [
        (node, type(dist).__name__, dist) for node, dist in n_dist.items()
    ]


@needs_nx
def test_predecessor_callable_weight_keeps_parity_fallback():
    edges = [("s", "a", 1), ("a", "z", 2), ("s", "z", 5)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)

    def weight(_u, _v, attrs):
        return attrs["weight"]

    f_pred, f_dist = fnx.dijkstra_predecessor_and_distance(g, "s", weight=weight)
    n_pred, n_dist = nx.dijkstra_predecessor_and_distance(gx, "s", weight=weight)
    assert list(f_pred.items()) == list(n_pred.items())
    assert list(f_dist.items()) == list(n_dist.items())


# br-r37-c1-7jysw: ``predecessor`` - networkx's level BFS, every predecessor on
# the previous level in frontier order, the dict in discovery order with the key
# objects networkx's row walk yields, from an index-space kernel on every class.
# The undirected route re-walked in Python with node objects, so a row keyed by
# an equal object of another type (1.0 in a row of int 1's graph) came out as
# the node object instead of the row key networkx yields.

PRED_CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
PRED_CUTOFFS = [None, 0, 1, 2, -1, 1.5, float("inf"), float("-inf"), float("nan")]


def _pred_shapes(lib, class_name):
    import networkx as _nx

    ba = _nx.barabasi_albert_graph(120, 3, seed=4)
    grid = _nx.grid_2d_graph(6, 7)
    shapes = {}
    g = getattr(lib, class_name)()
    g.add_edges_from(ba.edges())
    g.add_edges_from((v, u) for u, v in list(ba.edges())[::3])
    g.add_edge(5, 5)
    shapes["ba"] = (g, 0)
    g = getattr(lib, class_name)()
    g.add_edges_from(grid.edges())
    shapes["grid"] = (g, (0, 0))
    g = getattr(lib, class_name)()
    g.add_edges_from([("s", "a"), ("s", "b"), ("a", "t"), ("b", "t"), ("t", "u"), ("x", "y")])
    shapes["str diamond"] = (g, "s")
    g = getattr(lib, class_name)()
    g.add_edge(0, 1)
    g.add_edge(1.0, 2)  # row 2 keys the float 1.0, which networkx yields from it
    g.add_edge(2, 3)
    if g.is_directed():  # a successor row keying 1.0, reachable from 3
        g.add_edges_from([(3, 2), (2, 1.0), (1, 0)])
    shapes["equal keys"] = (g, 3)
    return shapes


def _typed(obj):
    if isinstance(obj, dict):
        return [(repr(k), type(k).__name__, _typed(v)) for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [(repr(x), type(x).__name__) for x in obj]
    return (repr(obj), type(obj).__name__)


@needs_nx
@pytest.mark.parametrize("class_name", PRED_CLASSES)
@pytest.mark.parametrize("cutoff", PRED_CUTOFFS, ids=repr)
def test_predecessor_matches_networkx(class_name, cutoff):
    fshapes, nshapes = _pred_shapes(fnx, class_name), _pred_shapes(nx, class_name)
    for label in fshapes:
        fg, source = fshapes[label]
        ng, _ = nshapes[label]
        f = fnx.predecessor(fg, source, cutoff=cutoff)
        n = nx.predecessor(ng, source, cutoff=cutoff)
        assert _typed(f) == _typed(n), label
        f_pred, f_seen = fnx.predecessor(fg, source, cutoff=cutoff, return_seen=True)
        n_pred, n_seen = nx.predecessor(ng, source, cutoff=cutoff, return_seen=True)
        assert _typed(f_pred) == _typed(n_pred) and _typed(f_seen) == _typed(n_seen), label
        for target in list(ng)[:: max(1, len(ng) // 7)] + [source]:
            assert _typed(fnx.predecessor(fg, source, target=target, cutoff=cutoff)) == _typed(
                nx.predecessor(ng, source, target=target, cutoff=cutoff)
            ), (label, target)
            assert fnx.predecessor(
                fg, source, target=target, cutoff=cutoff, return_seen=True
            ) == nx.predecessor(ng, source, target=target, cutoff=cutoff, return_seen=True)


@needs_nx
@pytest.mark.parametrize("class_name", PRED_CLASSES)
def test_predecessor_answers_from_the_index_kernel(class_name, monkeypatch):
    answered = []
    kernel = fnx._raw_predecessor_indexed

    def counting(*args):
        built = kernel(*args)
        answered.append(built is not None)
        return built

    monkeypatch.setattr(fnx, "_raw_predecessor_indexed", counting)
    graph, source = _pred_shapes(fnx, class_name)["ba"]
    fnx.predecessor(graph, source)
    fnx.predecessor(graph, source, cutoff=2, return_seen=True)
    assert answered == [True, True]


def _paths_outcome(call):
    try:
        return [[(repr(n), type(n).__name__) for n in path] for path in call()]
    except Exception as exc:  # noqa: BLE001 - the exception is part of the compared state
        return (type(exc).__name__, str(exc))


@needs_nx
@pytest.mark.parametrize("class_name", PRED_CLASSES)
def test_unweighted_all_shortest_paths_match_networkx(class_name):
    """br-r37-c1-7jysw: a multigraph's unweighted all_shortest_paths is networkx's
    predecessor + path build over the index kernel (the native enumerator
    projected the multigraph first, 0.12-0.59x); single_source_all_shortest_paths
    rides on predecessor on every class."""
    fshapes, nshapes = _pred_shapes(fnx, class_name), _pred_shapes(nx, class_name)
    for label in fshapes:
        fg, source = fshapes[label]
        ng, _ = nshapes[label]
        if fg.is_multigraph():
            first = next(iter(fg.edges()))
            fg.add_edge(*first)
            ng.add_edge(*first)
        for target in list(ng)[:: max(1, len(ng) // 9)] + [source, "absent"]:
            assert _paths_outcome(
                lambda: list(fnx.all_shortest_paths(fg, source, target))
            ) == _paths_outcome(lambda: list(nx.all_shortest_paths(ng, source, target))), (
                label,
                target,
            )
        assert _paths_outcome(
            lambda: [p for _, paths in fnx.single_source_all_shortest_paths(fg, source) for p in paths]
        ) == _paths_outcome(
            lambda: [p for _, paths in nx.single_source_all_shortest_paths(ng, source) for p in paths]
        ), label
