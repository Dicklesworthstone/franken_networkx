import math
import time

import franken_networkx as fnx
import networkx as nx
import pytest


def _rows(result):
    return [(repr(node), type(distance).__name__, distance) for node, distance in result.items()]


def _type_name(value):
    return value.__class__.__name__


def _build_graphs(graph_factory_f, graph_factory_n):
    gf = graph_factory_f()
    gn = graph_factory_n()
    for u, v, weight in (
        ("s", "a", 1),
        ("s", "b", 1),
        ("a", "c", 1),
        ("b", "d", 1),
        ("c", "z", 1),
        ("d", "z", 1),
        ("s", "flag", True),
        ("flag", "tail", 2),
        ("s", "float", 1.5),
        ("float", "mix", 2),
    ):
        gf.add_edge(u, v, weight=weight)
        gn.add_edge(u, v, weight=weight)
    return gf, gn


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
@pytest.mark.parametrize("cutoff", [None, 1, 2, -1, math.nan, math.inf])
def test_single_source_dijkstra_path_length_raw_matches_nx_types_and_cutoff(
    fnx_factory, nx_factory, cutoff
):
    gf, gn = _build_graphs(fnx_factory, nx_factory)

    public = fnx.single_source_dijkstra_path_length(
        gf, "s", cutoff=cutoff, weight="weight"
    )
    raw = fnx._raw_single_source_dijkstra_path_length(
        gf, "s", weight="weight", cutoff=cutoff
    )
    expected = nx.single_source_dijkstra_path_length(
        gn, "s", cutoff=cutoff, weight="weight"
    )

    assert _rows(public) == _rows(expected)
    assert _rows(raw) == _rows(expected)


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
def test_single_source_dijkstra_path_length_large_int_sum_does_not_saturate(
    fnx_factory, nx_factory
):
    weight = 1 << 62
    expected_distance = 1 << 63
    gf = fnx_factory()
    gn = nx_factory()
    for graph in (gf, gn):
        graph.add_edge("s", "a", weight=weight)
        graph.add_edge("a", "z", weight=weight)

    public = fnx.single_source_dijkstra_path_length(gf, "s", weight="weight")
    raw = fnx._raw_single_source_dijkstra_path_length(gf, "s", weight="weight")
    expected = nx.single_source_dijkstra_path_length(gn, "s", weight="weight")

    assert public["z"] == expected_distance
    assert raw["z"] == expected_distance
    assert _rows(public) == _rows(expected)
    assert _rows(raw) == _rows(expected)


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
def test_dijkstra_path_length_target_only_raw_matches_nx_types(
    monkeypatch, fnx_factory, nx_factory
):
    gf, gn = _build_graphs(fnx_factory, nx_factory)

    def fail_path_build(*args, **kwargs):
        raise AssertionError("dijkstra_path_length should not construct a path")

    monkeypatch.setattr(fnx, "_raw_dijkstra_path", fail_path_build)

    for target in ("z", "mix", "s"):
        public = fnx.dijkstra_path_length(gf, "s", target, weight="weight")
        raw = fnx._raw_dijkstra_path_length(gf, "s", target, weight="weight")
        expected = nx.dijkstra_path_length(gn, "s", target, weight="weight")

        assert public == expected
        assert raw == expected
        assert _type_name(public) == _type_name(expected)
        assert _type_name(raw) == _type_name(expected)


def _build_weighted_multidigraphs():
    gf = fnx.MultiDiGraph()
    gn = nx.MultiDiGraph()
    for graph in (gf, gn):
        graph.add_edge("s", "a", key=0, weight=7)
        graph.add_edge("s", "a", key=1, weight=1)
        graph.add_edge("a", "z", key=0, weight=2)
        graph.add_edge("s", "z", key=0, weight=10.0)
        graph.add_edge("s", "flag", key=0, weight=True)
        graph.add_edge("flag", "tail", key=0, weight=2)
    return gf, gn


def test_multidigraph_dijkstra_path_length_target_raw_skips_projection(monkeypatch):
    gf, gn = _build_weighted_multidigraphs()

    def fail_collapse(*args, **kwargs):
        raise AssertionError("directed multigraph target query should not collapse")

    monkeypatch.setattr(fnx, "_multigraph_collapse_min_weight", fail_collapse)

    for target in ("z", "tail", "s"):
        public = fnx.dijkstra_path_length(gf, "s", target, weight="weight")
        raw = fnx._raw_multidigraph_dijkstra_path_length_target(
            gf, "s", target, weight="weight"
        )
        expected = nx.dijkstra_path_length(gn, "s", target, weight="weight")

        assert public == expected
        assert raw == expected
        assert _type_name(public) == _type_name(expected)
        assert _type_name(raw) == _type_name(expected)


def test_multidigraph_dijkstra_path_target_raw_skips_projection(monkeypatch):
    gf, gn = _build_weighted_multidigraphs()

    def fail_collapse(*args, **kwargs):
        raise AssertionError("directed multigraph target path should not collapse")

    monkeypatch.setattr(fnx, "_multigraph_collapse_min_weight", fail_collapse)

    for target in ("z", "tail", "s"):
        public = fnx.dijkstra_path(gf, "s", target, weight="weight")
        raw = fnx._raw_multidigraph_dijkstra_path_target(
            gf, "s", target, weight="weight"
        )
        expected = nx.dijkstra_path(gn, "s", target, weight="weight")

        assert public == expected
        assert raw == expected


def test_multidigraph_dijkstra_path_length_target_raw_delegates_nonnumeric():
    gf = fnx.MultiDiGraph()
    gf.add_edge("s", "a", weight="bad")
    gf.add_edge("a", "z", weight=1)

    assert (
        fnx._raw_multidigraph_dijkstra_path_length_target(
            gf, "s", "z", weight="weight"
        )
        is None
    )


def test_multidigraph_dijkstra_path_target_raw_delegates_nonnumeric():
    gf = fnx.MultiDiGraph()
    gf.add_edge("s", "a", weight="bad")
    gf.add_edge("a", "z", weight=1)

    assert (
        fnx._raw_multidigraph_dijkstra_path_target(
            gf, "s", "z", weight="weight"
        )
        is None
    )


# br-r37-c1-qnj0n: single_source_dijkstra and dijkstra_predecessor_and_distance
# expand rows lazily, hold state only for what they reach, and bound the search
# by the cutoff during relaxation. They used to build a weighted CSR of every
# edge per call (33 ms against networkx's 10 us beside a 32k-node component).
# The rewrite rebuilt the path emitter and the predecessor-list bookkeeping, so
# order, int/float typing, display objects and tie lists are pinned exactly.

_CUTOFFS = [None, 0, 1, 2, 2.5, -1, math.nan, math.inf, 10**20]


def _tie_graphs(graph_factory_f, graph_factory_n):
    gf, gn = graph_factory_f(), graph_factory_n()
    edges = [
        ("gone", "s", 1), ("s", "a", 1), ("s", "b", 1), ("a", "c", 1), ("b", "c", 1),
        ("c", "z", 2), ("a", "z", 3), ("b", "d", 0), ("d", "c", 1), ("z", "s", 0),
        ("s", "half", 0.5), ("half", "c", 1.5), ("far", "s", 1),
        # "late" is first seen at 5 from s and IMPROVED to 2 through a: its
        # predecessor list must be replaced, not extended.
        ("s", "late", 5), ("a", "late", 1),
    ]
    for u, v, weight in edges:
        gf.add_edge(u, v, weight=weight)
        gn.add_edge(u, v, weight=weight)
    # A removal leaves node storage non-dense, so positions and slots differ -
    # the lazy rows must read neighbours by position.
    gf.remove_node("gone")
    gn.remove_node("gone")
    return gf, gn


def _typed(mapping):
    return [(repr(key), type(value).__name__, value) for key, value in mapping.items()]


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
@pytest.mark.parametrize("cutoff", _CUTOFFS)
@pytest.mark.parametrize("build", [_build_graphs, _tie_graphs])
def test_single_source_dijkstra_matches_nx_order_types_and_paths(
    fnx_factory, nx_factory, cutoff, build
):
    gf, gn = build(fnx_factory, nx_factory)
    dists, paths = fnx.single_source_dijkstra(gf, "s", cutoff=cutoff)
    nx_dists, nx_paths = nx.single_source_dijkstra(gn, "s", cutoff=cutoff)
    assert _typed(dists) == _typed(nx_dists)
    assert list(paths.items()) == list(nx_paths.items())


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
@pytest.mark.parametrize("cutoff", _CUTOFFS)
@pytest.mark.parametrize("build", [_build_graphs, _tie_graphs])
def test_dijkstra_predecessor_and_distance_matches_nx_tie_lists(
    fnx_factory, nx_factory, cutoff, build
):
    gf, gn = build(fnx_factory, nx_factory)
    pred, dist = fnx.dijkstra_predecessor_and_distance(gf, "s", cutoff=cutoff)
    nx_pred, nx_dist = nx.dijkstra_predecessor_and_distance(gn, "s", cutoff=cutoff)
    assert list(pred.items()) == list(nx_pred.items())
    assert _typed(dist) == _typed(nx_dist)


def _promoting_twins(directed, seed):
    """300 nodes: past the 64-entry point where the search's per-node tables
    turn from sparse to dense mid-search, with a removed node (non-dense
    storage) and int/float weights that produce ties."""
    import random

    rng = random.Random(seed)
    edges = [
        (u, v, rng.choice([1, 2, 2, 3, 1.5, 0.5]))
        for u in range(300)
        for v in rng.sample(range(300), 4)
        if u != v
    ]
    graphs = []
    for lib in (fnx, nx):
        g = lib.DiGraph() if directed else lib.Graph()
        g.add_node("gone")
        for u, v, w in edges:
            g.add_edge(u, v, weight=w)
        g.remove_node("gone")
        graphs.append(g)
    return graphs


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("cutoff", [None, 3, 6.5])
def test_searches_that_outgrow_the_sparse_tables_match_nx(directed, seed, cutoff):
    gf, gn = _promoting_twins(directed, seed)
    dists, paths = fnx.single_source_dijkstra(gf, 0, cutoff=cutoff)
    nx_dists, nx_paths = nx.single_source_dijkstra(gn, 0, cutoff=cutoff)
    assert _typed(dists) == _typed(nx_dists)
    assert list(paths.items()) == list(nx_paths.items())
    pred, dist = fnx.dijkstra_predecessor_and_distance(gf, 0, cutoff=cutoff)
    nx_pred, nx_dist = nx.dijkstra_predecessor_and_distance(gn, 0, cutoff=cutoff)
    assert list(pred.items()) == list(nx_pred.items())
    assert _typed(dist) == _typed(nx_dist)
    assert _typed(fnx.single_source_dijkstra_path_length(gf, 0, cutoff=cutoff)) == _typed(
        nx.single_source_dijkstra_path_length(gn, 0, cutoff=cutoff)
    )
    if not cutoff:
        assert len(nx_dists) > 64


def test_single_source_dijkstra_keys_are_the_graphs_own_objects():
    gf = fnx.Graph()
    gf.add_edge((0, 0), (1, 1), weight=2)
    gf.add_edge((1, 1), (2, 2), weight=1)
    dists, paths = fnx.single_source_dijkstra(gf, (0, 0), cutoff=5)
    stored = {node: node for node in gf}
    assert all(key is stored[key] for key in dists)
    assert all(node is stored[node] for path in paths.values() for node in path)


def _weighted_small_component(lib, parent_nodes):
    graph = lib.Graph()
    graph.add_edges_from((i, i + 1, {"weight": 1 + i % 3}) for i in range(9))
    graph.add_edges_from(
        (100 + i, 100 + (i + 1) % parent_nodes, {"weight": 1}) for i in range(parent_nodes)
    )
    return graph


def _best_of(fn, reps=50, rounds=7):
    fn()
    best = None
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            fn()
        elapsed = (time.perf_counter() - start) / reps
        best = elapsed if best is None else min(best, elapsed)
    return best


_SMALL_COMPONENT = {
    (lib.__name__, n): _weighted_small_component(lib, n)
    for lib in (fnx, nx)
    for n in (200, 12800)
}


@pytest.mark.parametrize(
    "call",
    [
        lambda m, g: m.single_source_dijkstra(g, 0, cutoff=4),
        lambda m, g: m.single_source_dijkstra(g, 0),
        lambda m, g: m.dijkstra_predecessor_and_distance(g, 0, cutoff=4),
        lambda m, g: m.dijkstra_predecessor_and_distance(g, 0),
    ],
    ids=["ss_dijkstra_cutoff", "ss_dijkstra", "pred_dist_cutoff", "pred_dist"],
)
def test_bounded_dijkstra_cost_does_not_grow_with_the_parent(call):
    """A search inside a 10-node component beside a disconnected ring of 200
    vs 12800 nodes: networkx is flat, and fnx's growth is judged against
    networkx's in the same process at the same moment, which calibrates the
    bound under load. The whole-graph weight CSR this replaced grew ~60x here;
    a lazy search grows ~1x."""
    growth = {}
    for lib in (fnx, nx):
        small = _SMALL_COMPONENT[(lib.__name__, 200)]
        large = _SMALL_COMPONENT[(lib.__name__, 12800)]
        growth[lib.__name__] = _best_of(lambda: call(lib, large)) / _best_of(
            lambda: call(lib, small)
        )
    assert growth["franken_networkx"] < 2.5 * max(growth["networkx"], 1.0), growth
