"""BackendInterface.convert_from_nx honours networkx's attribute hints (sfq4w.2).

networkx tells a backend which attributes a dispatched algorithm reads
(``edge_attrs`` / ``node_attrs`` as {name: default}) or that it keeps all of
them (``preserve_*_attrs``). fnx copied every attribute dict regardless, and
walked the adjacency in Python; that was most of the backend-mode conversion
toll. The conversion must still keep node order and every node's neighbor
order exactly, since algorithms break ties by them.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx._fnx import nx_adjacency_edge_batch
from franken_networkx.backend import (
    BackendInterface,
    _nx_to_fnx_for_dispatch,
    _topo_emit_edges_by_adj,
)
from franken_networkx.readwrite import _from_nx_graph

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _churned(cls, seed):
    """A graph whose adjacency order is NOT its edge-list order: edges added in
    random orientation, some removed and re-added, self-loops, attributes."""
    rng = random.Random(seed)
    g = getattr(nx, cls)()
    g.graph["name"] = f"g{seed}"
    n = rng.randint(1, 30)
    for i in rng.sample(range(n), n):
        g.add_node(i, color=rng.choice(["r", "g"]), size=i)
    for _ in range(rng.randint(0, 4 * n)):
        u, v = rng.randrange(n), rng.randrange(n)
        data = {}
        if rng.random() < 0.7:
            data["weight"] = rng.randint(1, 9)
        if rng.random() < 0.3:
            data["label"] = "x"
        g.add_edge(u, v, **data)
    for u, v in rng.sample(list(g.edges()), len(g.edges()) // 4):
        if g.has_edge(u, v):
            g.remove_edge(u, v)
    for _ in range(n // 2):
        u, v = rng.randrange(n), rng.randrange(n)
        g.add_edge(v, u, weight=1)
    return g


def _shape(g):
    adj = [(repr(u), [repr(v) for v in g.adj[u]]) for u in g]
    if g.is_multigraph():
        edges = [(repr(u), repr(v), repr(k), sorted(d.items())) for u, v, k, d in g.edges(keys=True, data=True)]
    else:
        edges = [(repr(u), repr(v), sorted(d.items())) for u, v, d in g.edges(data=True)]
    nodes = [(repr(n), sorted(d.items())) for n, d in g.nodes(data=True)]
    return type(g).__name__, dict(g.graph), nodes, adj, edges


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_native_edge_order_equals_the_python_helper(cls):
    for seed in range(200):
        g = _churned(cls, seed)
        native = [(u, v) for u, v, *_ in nx_adjacency_edge_batch(g._adj, g.is_directed())]
        assert native == list(_topo_emit_edges_by_adj(g)), seed


@pytest.mark.parametrize("cls", CLASSES)
def test_preserving_everything_equals_the_full_converter(cls):
    for seed in range(120):
        g = _churned(cls, seed)
        hinted = _nx_to_fnx_for_dispatch(
            g,
            edge_attrs=None,
            node_attrs=None,
            preserve_edge_attrs=True,
            preserve_node_attrs=True,
            preserve_graph_attrs=True,
        )
        assert _shape(hinted) == _shape(_from_nx_graph(g)), seed


@pytest.mark.parametrize("cls", CLASSES)
def test_hints_carry_only_what_networkx_asks_for(cls):
    g = _churned(cls, 7)
    assert any(d for *_, d in g.edges(data=True)) and any(d for _, d in g.nodes(data=True))
    full = _shape(_from_nx_graph(g))

    bare = BackendInterface.convert_from_nx(g)
    shape = _shape(bare)
    assert shape[3] == full[3]  # every node's neighbor order is kept
    assert all(not d for *_, d in shape[4]) and all(not d for _, d in shape[2])
    assert shape[1] == {}
    # the old converter carried everything: the hint is what drops it
    assert any(d for *_, d in full[4])

    weighted = BackendInterface.convert_from_nx(g, edge_attrs={"weight": 1})
    for *_, d in weighted.edges(data=True):
        assert set(d) == {"weight"}  # missing weights filled with the default
    present = BackendInterface.convert_from_nx(g, edge_attrs={"weight": None})
    for u, v, *rest in present.edges(data=True, keys=True) if g.is_multigraph() else present.edges(data=True):
        assert set(rest[-1]) <= {"weight"}
    assert sum("weight" in d for *_, d in present.edges(data=True)) == sum(
        "weight" in d for *_, d in g.edges(data=True)
    )

    colored = BackendInterface.convert_from_nx(g, node_attrs={"color": None}, preserve_graph_attrs=True)
    assert [d for _, d in colored.nodes(data=True)] == [{"color": d["color"]} for _, d in g.nodes(data=True)]
    assert dict(colored.graph) == dict(g.graph)


def test_views_and_subclasses_keep_the_full_conversion():
    g = _churned("Graph", 3)

    class Sub(nx.Graph):
        pass

    sub = Sub(g)
    view = g.subgraph(list(g)[: len(g) // 2])
    for graph in (sub, view):
        converted = _nx_to_fnx_for_dispatch(
            graph,
            edge_attrs=None,
            node_attrs=None,
            preserve_edge_attrs=True,
            preserve_node_attrs=True,
            preserve_graph_attrs=True,
        )
        assert _shape(converted)[2:] == _shape(_from_nx_graph(graph))[2:]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_dispatched_results_still_equal_networkx(cls):
    for seed in range(20):
        g = _churned(cls, seed)
        source = next(iter(g))
        assert nx.single_source_shortest_path_length(
            g, source, backend="franken_networkx"
        ) == nx.single_source_shortest_path_length(g, source)
        assert nx.single_source_dijkstra_path_length(
            g, source, backend="franken_networkx"
        ) == nx.single_source_dijkstra_path_length(g, source)
        assert list(nx.bfs_edges(g, source, backend="franken_networkx")) == list(nx.bfs_edges(g, source))


# should_run's ski rental (sfq4w.2 part 2): a cheap kernel's first calls on a
# graph run in networkx (a cold conversion costs more than networkx's own
# run); the call that brings the graph's accumulated share of a conversion to
# one converts, and the cached conversion serves every later call.

from franken_networkx.backend import _CONVERT_AFTER_USES, _RENT_KEY


def _fresh():
    return nx.barabasi_albert_graph(200, 3, seed=5)


def test_a_cheap_kernel_declines_until_its_calls_pay_for_a_conversion():
    g = _fresh()
    k = _CONVERT_AFTER_USES["bfs_tree"]
    verdicts = [BackendInterface.should_run("bfs_tree", (g, 0), {}) for _ in range(k)]
    assert all(isinstance(v, str) for v in verdicts[:-1]), verdicts
    assert verdicts[-1] is True
    g.add_edge(0, 199)  # networkx clears the cache, and the running total with it
    assert _RENT_KEY not in g.__networkx_cache__
    assert isinstance(BackendInterface.should_run("bfs_tree", (g, 0), {}), str)


def test_calls_of_different_kernels_share_the_graph_s_total():
    g = _fresh()
    pagerank, core = 1 / _CONVERT_AFTER_USES["pagerank"], 1 / _CONVERT_AFTER_USES["core_number"]
    assert 2 * pagerank < 1.0 <= 2 * pagerank + core  # two pageranks, then core_number pays
    assert isinstance(BackendInterface.should_run("pagerank", (g,), {}), str)
    assert isinstance(BackendInterface.should_run("pagerank", (g,), {}), str)
    assert BackendInterface.should_run("core_number", (g,), {}) is True


def test_kernels_that_never_pay_and_heavy_kernels():
    g = _fresh()
    assert all(isinstance(BackendInterface.should_run("has_path", (g, 0, 1), {}), str) for _ in range(50))
    assert "betweenness_centrality" not in _CONVERT_AFTER_USES
    assert BackendInterface.should_run("betweenness_centrality", (g,), {}) is True


def test_a_cached_conversion_means_run_and_no_caching_means_decline():
    g = _fresh()
    nx.bfs_tree(g, 0, backend="franken_networkx")  # an explicit backend converts and caches
    assert g.__networkx_cache__["backends"]["franken_networkx"]
    assert BackendInterface.should_run("connected_components", (g,), {}) is True
    h = _fresh()
    h.__networkx_cache__ = None
    assert isinstance(BackendInterface.should_run("bfs_tree", (h, 0), {}), str)


def test_backend_priority_runs_networkx_until_the_conversion_pays():
    g = _fresh()
    saved = list(nx.config.backend_priority.algos)
    nx.config.backend_priority.algos = ["franken_networkx"]
    try:
        # core_number returns a dict, so networkx takes it from the algos list
        # (graph-returning functions use backend_priority.generators).
        k = _CONVERT_AFTER_USES["core_number"]
        for i in range(k - 1):
            assert nx.core_number(g) == nx.core_number(g, backend="networkx")
            assert not g.__networkx_cache__.get("backends", {}).get("franken_networkx"), i
        assert nx.core_number(g) == nx.core_number(g, backend="networkx")
        assert g.__networkx_cache__["backends"]["franken_networkx"]
    finally:
        nx.config.backend_priority.algos = saved


def test_every_threshold_names_a_function_fnx_dispatches():
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    assert set(_CONVERT_AFTER_USES) <= set(_SUPPORTED_ALGORITHMS)
    assert all(k is None or (isinstance(k, int) and k >= 2) for k in _CONVERT_AFTER_USES.values())
