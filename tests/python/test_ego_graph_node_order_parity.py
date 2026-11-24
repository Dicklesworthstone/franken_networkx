"""Parity for ``ego_graph`` node iteration order.

Bead br-r37-c1-fauol. fnx.ego_graph constructed nodes_within as a set
and iterated in arbitrary hash order. nx.ego_graph uses
``G.subgraph(sp).copy()`` which iterates in G's original insertion
order (filtered to the ego set).

Drop-in code that iterates ``list(ego_graph(G, n, r).nodes())`` got
different orders.
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


def _make_str_graph(lib):
    g = lib.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
    return g


@needs_nx
@pytest.mark.parametrize("radius", [1, 2, 3])
def test_ego_graph_node_order_matches_networkx(radius):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.ego_graph(g, "c", radius=radius).nodes())
    n = list(nx.ego_graph(gx, "c", radius=radius).nodes())
    assert f == n


@needs_nx
def test_ego_graph_center_false_node_order():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.ego_graph(g, "c", radius=2, center=False).nodes())
    n = list(nx.ego_graph(gx, "c", radius=2, center=False).nodes())
    assert f == n


@needs_nx
def test_ego_graph_path_graph_int_nodes():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.ego_graph(g, 2, radius=2).nodes())
    n = list(nx.ego_graph(gx, 2, radius=2).nodes())
    assert f == n == [0, 1, 2, 3, 4]


@needs_nx
def test_ego_graph_digraph_node_order():
    dg = fnx.DiGraph([(0, 1), (1, 2), (0, 3)])
    dgx = nx.DiGraph([(0, 1), (1, 2), (0, 3)])
    f = list(fnx.ego_graph(dg, 0, radius=2).nodes())
    n = list(nx.ego_graph(dgx, 0, radius=2).nodes())
    assert f == n == [0, 1, 2, 3]


@needs_nx
def test_ego_graph_undirected_kwarg_on_digraph():
    dg = fnx.DiGraph([(0, 1), (1, 2), (3, 0)])
    dgx = nx.DiGraph([(0, 1), (1, 2), (3, 0)])
    f = list(fnx.ego_graph(dg, 0, radius=1, undirected=True).nodes())
    n = list(nx.ego_graph(dgx, 0, radius=1, undirected=True).nodes())
    assert f == n


@needs_nx
def test_ego_graph_weighted_distance():
    g = fnx.Graph()
    gx = nx.Graph()
    g.add_edge("a", "b", weight=1)
    g.add_edge("b", "c", weight=2)
    gx.add_edge("a", "b", weight=1)
    gx.add_edge("b", "c", weight=2)
    f = list(fnx.ego_graph(g, "a", radius=2, distance="weight").nodes())
    n = list(nx.ego_graph(gx, "a", radius=2, distance="weight").nodes())
    assert f == n


@needs_nx
def test_ego_graph_edges_match_networkx():
    """Sanity: edges still match (not just nodes)."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.ego_graph(g, 2, radius=1).edges())
    n = list(nx.ego_graph(gx, 2, radius=1).edges())
    assert sorted(f) == sorted(n)


@needs_nx
def test_ego_graph_radius_zero_only_center():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.ego_graph(g, 2, radius=0).nodes())
    n = list(nx.ego_graph(gx, 2, radius=0).nodes())
    assert f == n == [2]


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("radius", [-1, 0, 0.5, 1.5, float("inf"), float("nan")])
@pytest.mark.parametrize("distance", [None, "cost"])
@pytest.mark.parametrize("undirected", [False, True])
@pytest.mark.parametrize("center", [False, True])
def test_ego_radius_uses_shortest_path_cutoff_contract(
    graph_type, radius, distance, undirected, center
):
    results = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)()
        graph.add_edges_from(
            [(0, 1, {"cost": 0.5}), (1, 2, {"cost": 1}), (2, 3, {"cost": 2})]
        )
        ego = module.ego_graph(
            graph, 0, radius=radius, distance=distance,
            undirected=undirected, center=center,
        )
        results.append((list(ego), list(ego.edges(data=True))))
    assert results[1] == results[0]


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("outside_weight", [-1, "not-a-number"])
@pytest.mark.parametrize("undirected", [False, True])
def test_ego_weighted_radius_does_not_evaluate_excluded_rows(
    graph_type, outside_weight, undirected
):
    results = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)()
        graph.add_edges_from(
            [(0, 1, {"cost": 1}), (1, 2, {"cost": 10}), (2, 2, {"cost": outside_weight})]
        )
        # An unrestricted Dijkstra reaches node 2 and raises on its negative
        # self-loop or invalid arithmetic. The radius excludes that entire row.
        ego = module.ego_graph(graph, 0, radius=1, distance="cost", undirected=undirected)
        results.append((list(ego), list(ego.edges(data=True))))
    assert results[1] == results[0]
    assert results[0] == ([0, 1], [(0, 1, {"cost": 1})])


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("undirected", [False, True])
def test_ego_weight_callback_only_observes_admitted_search_rows(graph_type, undirected):
    results = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)()
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        visited = []

        def distance(source, target, data):
            visited.append((source, target))
            if source >= 2:
                raise AssertionError("the weighted radius excludes this source row")
            return 10 if target >= 2 else 1

        ego = module.ego_graph(
            graph, 0, radius=1, distance=distance, undirected=undirected
        )
        results.append((list(ego), list(ego.edges()), visited))
    assert results[1] == results[0]
    assert results[0][0] == [0, 1]
    assert results[0][2]


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("attribute_scope", ["node", "edge", "both"])
@pytest.mark.parametrize("distance", [None, "cost"])
def test_ego_induced_copy_preserves_arbitrary_attribute_keys(
    graph_type, attribute_scope, distance
):
    results = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)()
        graph.add_edges_from([(0, 1, {"cost": 1}), (1, 2, {"cost": 3})])
        if graph.is_multigraph():
            graph.add_edge(0, 1, key="parallel", cost=0.5)
        payload = ["shared"]
        graph.graph[17] = payload
        if attribute_scope in ("node", "both"):
            graph.nodes[0][23] = payload
            graph.nodes[1][("node", "key")] = "kept"
        if attribute_scope in ("edge", "both"):
            for _, _, attrs in graph.edges(data=True):
                attrs[29] = payload
                attrs["key"] = "attribute, not the parallel edge identifier"

        ego = module.ego_graph(graph, 0, radius=1, distance=distance)
        edges = list(ego.edges(keys=True, data=True)) if ego.is_multigraph() else list(ego.edges(data=True))
        results.append((list(ego.nodes(data=True)), edges, dict(ego.graph)))

        # Each outer attribute mapping is copied, while its values retain
        # NetworkX's shallow sharing. Editing the result cannot change the
        # source's mappings or its parallel-edge identifiers.
        assert ego.graph is not graph.graph
        assert ego.graph[17] is payload
        if attribute_scope in ("node", "both"):
            assert ego.nodes[0] is not graph.nodes[0]
            assert ego.nodes[0][23] is payload
            ego.nodes[0]["new"] = True
            assert "new" not in graph.nodes[0]
        if attribute_scope in ("edge", "both"):
            if graph.is_multigraph():
                assert list(ego[0][1]) == [0, "parallel"]
                attrs, original = ego[0][1][0], graph[0][1][0]
            else:
                attrs, original = ego[0][1], graph[0][1]
            assert attrs is not original
            assert attrs[29] is payload
            attrs["new"] = True
            assert "new" not in original
    assert results[1] == results[0]


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_ego_unweighted_search_uses_adjacency_not_replaced_neighbor_method(graph_type):
    results = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)([(0, 1), (1, 2)])
        calls = []

        def neighbors(node):
            calls.append(node)
            return iter(())

        graph.neighbors = neighbors
        if graph.is_directed():
            graph.successors = neighbors
        ego = module.ego_graph(graph, 0, radius=1)
        results.append((list(ego), list(ego.edges()), calls))
    assert results[1] == results[0] == ([0, 1], [(0, 1)], [])


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("distance", [None, "cost"])
@pytest.mark.parametrize("undirected", [False, True])
@pytest.mark.parametrize("source", ["absent", []])
def test_ego_source_errors_come_from_selected_shortest_path(
    graph_type, distance, undirected, source
):
    outcomes = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)([(0, 1)])
        with pytest.raises(Exception) as error:
            module.ego_graph(graph, source, distance=distance, undirected=undirected)
        outcomes.append((type(error.value).__name__, error.value.args))
    assert outcomes[1] == outcomes[0]


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("distance", [None, "cost"])
@pytest.mark.parametrize("action", ["add-source", "raise"])
def test_ego_undirected_conversion_precedes_source_lookup(graph_type, distance, action):
    outcomes = []
    for module in (nx, fnx):
        calls = []
        base = getattr(module, graph_type)

        class ProviderGraph(base):
            def to_undirected(self):
                calls.append("convert")
                if action == "raise":
                    raise ValueError("conversion before source lookup")
                self.add_edge("source", "neighbor", cost=1)
                return super().to_undirected()

        graph = ProviderGraph([(0, 1)])
        result = failure = None
        try:
            ego = module.ego_graph(graph, "source", distance=distance, undirected=True)
            result = (
                list(ego), list(ego.edges(data=True)),
                ego.is_directed(), ego.is_multigraph(),
            )
        except Exception as error:
            failure = (type(error).__name__, error.args)
        outcomes.append((result, failure, calls, "source" in graph))
    assert outcomes[1] == outcomes[0]
    assert outcomes[0][2] == ["convert"]
    if action == "raise":
        assert outcomes[0][1] == ("ValueError", ("conversion before source lookup",))
    else:
        assert outcomes[0][1] is None
        assert set(outcomes[0][0][0]) == {"source", "neighbor"}
        assert outcomes[0][3]
