"""Conformance guard for common_neighbors (the link-prediction base).

common_neighbors underpins jaccard/AA/RA/CCPA/Soundarajan scoring. networkx
returns ``G._adj[u].keys() & G._adj[v].keys() - {u, v}``, a set whose
ITERATION ORDER is observable (``list(...)``, the scorers' summation order):
wherever hashes collide, it depends on how that set was built. br-r37-c1-ceqev
found fnx's order differing for ~2.6% of pairs on graphs with colliding labels;
these tests pin the order, the set, and the missing-node / directed contracts on
every route - the native kernel's walk of u's row, its walk of v's row with and
without colliding slots, the mixed-hash-key fallback, subclasses and views.

No mocks: real fnx vs real networkx, both graphs built from one edge stream.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _twins(edges, nodes=(), fnx_cls=fnx.Graph, nx_cls=nx.Graph):
    fg, ng = fnx_cls(), nx_cls()
    for g in (fg, ng):
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
    return fg, ng


def _order_diffs(fg, ng, pairs):
    diffs = []
    for u, v in pairs:
        got = fnx.common_neighbors(fg, u, v)
        want = nx.common_neighbors(ng, u, v)
        assert type(got) is set
        if list(got) != list(want):
            diffs.append((u, v, list(got), list(want)))
    return diffs


def _hub_pairs(ng, r, hubs=12, extra=150):
    by_degree = sorted(ng, key=ng.degree, reverse=True)
    top = by_degree[:hubs]
    nodes = list(ng)
    pairs = [(u, v) for u in top for v in top]
    pairs += [(u, r.choice(nodes)) for u in top for _ in range(6)]
    pairs += [(r.choice(nodes), u) for u in top for _ in range(6)]
    pairs += [(r.choice(nodes), r.choice(nodes)) for _ in range(extra)]
    return pairs


@pytest.mark.parametrize("seed", range(25))
def test_common_neighbors_set_matches_networkx(seed):
    r = random.Random(seed)
    n = r.randint(5, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    fg, ng = _twins(edges, range(n))
    for u in range(n):
        for v in range(u + 1, n):
            assert set(fnx.common_neighbors(fg, u, v)) == set(nx.common_neighbors(ng, u, v))


# x1024 puts every label in slot 0 of any table below 1024 slots; x37 and x8
# collide some; str labels hash per process, the same for both twins.
@pytest.mark.parametrize(
    "label", [lambda x: x, lambda x: 8 * x, lambda x: 37 * x, lambda x: 1024 * x, lambda x: f"n{x}"],
    ids=["int", "x8", "x37", "x1024", "str"],
)
@pytest.mark.parametrize("n, m", [(60, 3), (400, 4)])
@pytest.mark.parametrize("seed", range(3))
def test_common_neighbors_order_matches_networkx(label, n, m, seed):
    r = random.Random(seed)
    edges = [(label(a), label(b)) for a, b in nx.barabasi_albert_graph(n, m, seed=seed).edges()]
    edges = [(b, a) if r.random() < 0.5 else (a, b) for a, b in edges]
    r.shuffle(edges)
    fg, ng = _twins(edges)
    assert _order_diffs(fg, ng, _hub_pairs(ng, r)) == []


@pytest.mark.parametrize("scale", [1, 1024])
def test_common_neighbors_order_with_self_loops_and_u_equal_v(scale):
    r = random.Random(7)
    edges = [(scale * a, scale * b) for a, b in nx.barabasi_albert_graph(120, 5, seed=7).edges()]
    loops = [(scale * x, scale * x) for x in r.sample(range(120), 30)]
    fg, ng = _twins(edges + loops)
    nodes = list(ng)
    pairs = [(u, u) for u in nodes]
    pairs += [(u, w) for u, w in ng.edges()]
    pairs += [(r.choice(nodes), r.choice(nodes)) for _ in range(300)]
    assert _order_diffs(fg, ng, pairs) == []


def test_common_neighbors_order_after_node_removals():
    r = random.Random(11)
    edges = [(1024 * a, 1024 * b) for a, b in nx.barabasi_albert_graph(300, 4, seed=11).edges()]
    fg, ng = _twins(edges)
    gone = [1024 * x for x in r.sample(range(300), 60)]
    fg.remove_nodes_from(gone)
    ng.remove_nodes_from(gone)
    fg.add_edges_from([(1024 * 7, 1024 * 400), (1024 * 400, 1024 * 9)])
    ng.add_edges_from([(1024 * 7, 1024 * 400), (1024 * 400, 1024 * 9)])
    assert _order_diffs(fg, ng, _hub_pairs(ng, r)) == []


def test_common_neighbors_order_on_the_mixed_hash_key_fallback():
    # A row that shows 1024.0 for node 1024 (nx keeps the key object the edge
    # named) sends the kernel to the Python route.
    r = random.Random(3)
    edges = [(1024 * a, 1024 * b) for a, b in nx.barabasi_albert_graph(150, 5, seed=3).edges()]
    edges += [(1024.0, 1024 * x) for x in range(20, 60)]
    fg, ng = _twins(edges)
    assert fg._native_common_neighbors(0, 1024) is None
    assert _order_diffs(fg, ng, _hub_pairs(ng, r)) == []


def test_common_neighbors_order_on_a_subclass():
    class FnxSub(fnx.Graph):
        pass

    class NxSub(nx.Graph):
        pass

    r = random.Random(5)
    edges = [(1024 * a, 1024 * b) for a, b in nx.barabasi_albert_graph(200, 4, seed=5).edges()]
    fg, ng = _twins(edges, fnx_cls=FnxSub, nx_cls=NxSub)
    assert _order_diffs(fg, ng, _hub_pairs(ng, r)) == []


_KEEP = [1024 * x for x in range(250) if x % 5]
_CUT = [(1024 * a, 1024 * b) for a, b in list(nx.barabasi_albert_graph(250, 5, seed=4).edges())[::3]]


# networkx's rows are dicts on a graph and on copy(as_view=True) of one, and
# coreview Mappings (FilterAtlas, UnionAtlas) on filtered and undirected views,
# whose keys() set operations build their sets another way.
@pytest.mark.parametrize(
    "make",
    [
        lambda m, g: g.subgraph(_KEEP),
        lambda m, g: m.subgraph_view(g),
        lambda m, g: m.subgraph_view(g, filter_edge=lambda a, b: (a + b) % 3),
        lambda m, g: m.restricted_view(g, [1024 * 3], _CUT),
        lambda m, g: g.edge_subgraph(_CUT),
        lambda m, g: g.copy(as_view=True),
        lambda m, g: g.subgraph(_KEEP).copy(as_view=True),
        lambda m, g: g.copy(as_view=True).subgraph(_KEEP),
        lambda m, g: m.DiGraph(g.edges()).to_undirected(as_view=True),
        lambda m, g: g.to_undirected(as_view=True),
        lambda m, g: g.subgraph(_KEEP).to_undirected(as_view=True),
        lambda m, g: m.freeze(g.copy()),
    ],
    ids=[
        "subgraph", "subgraph_view", "subgraph_view_edge", "restricted_view", "edge_subgraph",
        "copy_view", "copy_view_of_subgraph", "subgraph_of_copy_view", "undirected_view_of_digraph",
        "undirected_view_of_graph", "undirected_view_of_subgraph", "freeze",
    ],
)
def test_common_neighbors_order_on_views(make):
    r = random.Random(4)
    edges = [(1024 * a, 1024 * b) for a, b in nx.barabasi_albert_graph(250, 5, seed=4).edges()]
    edges = [(b, a) if r.random() < 0.5 else (a, b) for a, b in edges]
    fg, ng = _twins(edges)
    fv, nv = make(fnx, fg), make(nx, ng)
    assert _order_diffs(fv, nv, _hub_pairs(nv, r, extra=600)) == []


@pytest.mark.parametrize(
    "make",
    [lambda g: g, lambda g: g.subgraph(_KEEP), lambda g: g.copy(as_view=True), lambda g: nx.DiGraph(g.edges()).to_undirected(as_view=True)],
    ids=["graph", "subgraph", "copy_view", "undirected_view_of_digraph"],
)
def test_common_neighbors_order_on_networkx_inputs(make):
    r = random.Random(9)
    edges = [(1024 * a, 1024 * b) for a, b in nx.barabasi_albert_graph(250, 5, seed=9).edges()]
    ng = nx.Graph(edges)
    nv = make(ng)
    diffs = [
        (u, v)
        for u, v in _hub_pairs(nv, r, extra=400)
        if list(fnx.common_neighbors(nv, u, v)) != list(nx.common_neighbors(nv, u, v))
    ]
    assert diffs == []


def test_common_neighbors_disjoint_and_missing():
    fg, ng = _twins([(0, 1), (2, 3)], range(4))
    # disjoint neighborhoods -> empty.
    assert set(fnx.common_neighbors(fg, 0, 2)) == set(nx.common_neighbors(ng, 0, 2))
    # missing or unhashable u / v -> networkx's exception, u checked first.
    for u, v in [(0, 99), (99, 0), (99, 98), ([0], 1), (0, [1])]:
        with pytest.raises(nx.NetworkXError) as want:
            nx.common_neighbors(ng, u, v)
        with pytest.raises(nx.NetworkXError) as got:
            fnx.common_neighbors(fg, u, v)
        assert got.value.args == want.value.args


@pytest.mark.parametrize("view", [False, True], ids=["digraph", "reverse_view"])
def test_common_neighbors_directed_is_not_implemented(view):
    fg, ng = _twins([(0, 1), (1, 2)], fnx_cls=fnx.DiGraph, nx_cls=nx.DiGraph)
    if view:
        fg, ng = fg.reverse(copy=False), ng.reverse(copy=False)
    with pytest.raises(nx.NetworkXNotImplemented) as want:
        nx.common_neighbors(ng, 0, 99)
    with pytest.raises(nx.NetworkXNotImplemented) as got:
        fnx.common_neighbors(fg, 0, 99)
    assert got.value.args == want.value.args


_LOCAL_PREDICTORS = [
    "common_neighbors",
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
    "preferential_attachment",
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "within_inter_cluster",
    "common_neighbor_centrality",
]


@pytest.mark.parametrize(
    "name,class_name",
    [(name, "Graph") for name in _LOCAL_PREDICTORS]
    + [("common_neighbors", "MultiGraph")],
)
@pytest.mark.parametrize("view_kind", ["filtered", "copy_filtered", "union_filtered"])
def test_common_neighbor_queries_do_not_read_unrelated_view_rows(name, class_name, view_kind):
    def run(module):
        parent_class = class_name
        if view_kind == "union_filtered":
            parent_class = "DiGraph" if class_name == "Graph" else "MultiDiGraph"
        graph = getattr(module, parent_class)()
        graph.add_nodes_from(range(6), community=0)
        graph.add_edges_from([(0, 1), (2, 1), (0, 3), (2, 3), (4, 5)])
        if view_kind == "union_filtered":
            graph = graph.to_undirected(as_view=True)

        def visible(u, v, *keys):
            if u >= 4 or v >= 4:
                raise AssertionError("a local query inspected an unrelated edge")
            return True

        view = module.subgraph_view(graph, filter_edge=visible)
        if view_kind == "copy_filtered":
            view = view.copy(as_view=True)
        if name == "common_neighbors":
            return list(module.common_neighbors(view, 0, 2))
        # Other CCPA settings intentionally compute all-pairs distances at
        # call time. The alpha=1 branch only needs the queried neighbor rows.
        kwargs = {"alpha": 1} if name == "common_neighbor_centrality" else {}
        return list(getattr(module, name)(view, [(0, 2)], **kwargs))

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
def test_common_neighbors_retains_left_keys_during_right_row_lookup(class_name):
    def run(module):
        graph = getattr(module, class_name)()
        graph.add_nodes_from(range(4))
        visits = []

        def edge_data():
            return {0: {}} if class_name == "MultiGraph" else {}

        class Rows(dict):
            def __getitem__(self, node):
                visits.append(node)
                if node == 2:
                    # The left keys view already exists. Its contents must
                    # reflect this write before the intersection is evaluated.
                    attrs = edge_data()
                    dict.__getitem__(self, 0)[3] = attrs
                    dict.__getitem__(self, 3)[0] = attrs
                return dict.__getitem__(self, node)

        graph._adj = Rows({
            0: {1: edge_data()},
            1: {0: edge_data(), 2: edge_data()},
            2: {1: edge_data(), 3: edge_data()},
            3: {2: edge_data()},
        })
        graph._node = {node: {} for node in range(4)}
        visits.clear()
        return list(module.common_neighbors(graph, 0, 2)), visits

    assert run(fnx) == run(nx) == ([1, 3], [0, 2])


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("u,v", [(99, 0), (0, 99), ([0], 1), (0, [1])])
def test_common_neighbors_validates_before_reading_assigned_rows(class_name, u, v):
    def run(module):
        graph = getattr(module, class_name)()
        graph.add_nodes_from([0, 1])
        visits = []

        class Rows(dict):
            def __getitem__(self, node):
                visits.append(node)
                raise AssertionError("invalid query read an adjacency row")

            def __iter__(self):
                visits.append("iterate")
                raise AssertionError("invalid query traversed the adjacency mapping")

        graph._adj = Rows({0: {}, 1: {}})
        graph._node = {0: {}, 1: {}}
        error_type = (
            nx.NetworkXNotImplemented if "DiGraph" in class_name else nx.NetworkXError
        )
        with pytest.raises(error_type) as error:
            module.common_neighbors(graph, u, v)
        return error.value.args, visits

    expected = run(nx)
    assert expected[1] == []
    assert run(fnx) == expected
