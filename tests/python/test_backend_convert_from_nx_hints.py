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
