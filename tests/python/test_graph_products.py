"""Tests for line_graph, cartesian_product, and tensor_product."""

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triangle():
    """Triangle graph: 0-1, 1-2, 0-2."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(0, 2)
    return G


@pytest.fixture
def path3():
    """Path graph: 0-1-2."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    return G


@pytest.fixture
def k2():
    """Complete graph K2: 0-1."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    return G


@pytest.fixture
def path2_directed():
    """Directed path: 0->1."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    return D


# ---------------------------------------------------------------------------
# line_graph tests
# ---------------------------------------------------------------------------


class TestLineGraph:
    def test_line_graph_triangle(self, triangle):
        L = fnx.line_graph(triangle)
        # Triangle has 3 edges, so L has 3 nodes
        # All edges are adjacent (share vertices), so L is also a triangle
        assert L.number_of_nodes() == 3
        assert L.number_of_edges() == 3

    def test_line_graph_path(self, path3):
        L = fnx.line_graph(path3)
        # Path 0-1-2 has 2 edges, sharing vertex 1
        assert L.number_of_nodes() == 2
        assert L.number_of_edges() == 1

    def test_line_graph_single_edge(self, k2):
        L = fnx.line_graph(k2)
        assert L.number_of_nodes() == 1
        assert L.number_of_edges() == 0

    def test_line_graph_empty(self):
        G = fnx.Graph()
        G.add_node(0)
        L = fnx.line_graph(G)
        assert L.number_of_nodes() == 0
        assert L.number_of_edges() == 0

    def test_line_graph_directed(self, path2_directed):
        L = fnx.line_graph(path2_directed)
        # Single directed edge -> single node, no edges
        assert L.number_of_nodes() == 1
        assert L.number_of_edges() == 0

    def test_line_graph_directed_path(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        L = fnx.line_graph(D)
        # Two edges (0,1) and (1,2), head of first = tail of second
        assert L.number_of_nodes() == 2
        assert L.number_of_edges() == 1


# ---------------------------------------------------------------------------
# cartesian_product tests
# ---------------------------------------------------------------------------


class TestCartesianProduct:
    def test_cartesian_product_k2_k2(self, k2):
        # K2 x K2 = 4-cycle (C4)
        P = fnx.cartesian_product(k2, k2)
        assert P.number_of_nodes() == 4
        assert P.number_of_edges() == 4

    def test_cartesian_product_empty(self):
        G1 = fnx.Graph()
        G2 = fnx.Graph()
        G1.add_node(0)
        G2.add_node(0)
        P = fnx.cartesian_product(G1, G2)
        assert P.number_of_nodes() == 1
        assert P.number_of_edges() == 0

    def test_cartesian_product_one_edge(self, k2, path3):
        # K2 (1 edge) x P3 (2 edges)
        # Nodes: 2 x 3 = 6
        # Edges: for each of 2 nodes in K2, 2 edges in P3 = 4
        #      + for each of 3 nodes in P3, 1 edge in K2 = 3
        #      = 7 edges total
        P = fnx.cartesian_product(k2, path3)
        assert P.number_of_nodes() == 6
        assert P.number_of_edges() == 7

    def test_cartesian_product_directed(self, path2_directed):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        P = fnx.cartesian_product(path2_directed, D)
        assert P.number_of_nodes() == 4
        # 2 nodes in D1, 1 directed edge in D2 = 2 edges
        # 2 nodes in D2, 1 directed edge in D1 = 2 edges
        # Total = 4 directed edges
        assert P.number_of_edges() == 4


# ---------------------------------------------------------------------------
# tensor_product tests
# ---------------------------------------------------------------------------


class TestTensorProduct:
    def test_tensor_product_k2_k2(self, k2):
        # K2 x K2 has 4 nodes but forms 2 disjoint edges
        P = fnx.tensor_product(k2, k2)
        assert P.number_of_nodes() == 4
        # Edge {0,1} in both graphs creates edges:
        # (0,0)-(1,1) and (0,1)-(1,0)
        assert P.number_of_edges() == 2

    def test_tensor_product_empty_edges(self, k2):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        # No edges in G -> no edges in tensor product
        P = fnx.tensor_product(k2, G)
        assert P.number_of_nodes() == 4
        assert P.number_of_edges() == 0

    def test_tensor_product_triangle_edge(self, triangle, k2):
        # Triangle has 3 edges, K2 has 1 edge
        # For each pair of edges, we get 2 edges in tensor product
        # But we need to be careful about counting
        P = fnx.tensor_product(triangle, k2)
        assert P.number_of_nodes() == 6
        # Each edge in triangle (3) paired with edge in K2 (1)
        # gives 2 edges each = 6 edges
        assert P.number_of_edges() == 6

    def test_tensor_product_directed(self, path2_directed):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        P = fnx.tensor_product(path2_directed, D)
        assert P.number_of_nodes() == 4
        # Only (0,0) -> (1,1) edge
        assert P.number_of_edges() == 1


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrors:
    def test_mixed_types_cartesian(self, k2, path2_directed):
        # Cannot mix directed and undirected
        with pytest.raises(fnx.NetworkXError):
            fnx.cartesian_product(k2, path2_directed)

    def test_mixed_types_tensor(self, k2, path2_directed):
        with pytest.raises(fnx.NetworkXError):
            fnx.tensor_product(k2, path2_directed)


_LIVE_PRODUCTS = (
    "cartesian_product", "tensor_product", "strong_product", "lexicographic_product",
)


def _product_snapshot(graph):
    edges = graph.edges(keys=True, data=True) if graph.is_multigraph() else graph.edges(data=True)
    return (
        list(graph.nodes(data=True)), list(edges),
        [(node, list(graph.adj[node])) for node in graph], dict(graph.graph),
    )


@pytest.mark.parametrize("name", _LIVE_PRODUCTS)
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("library", [nx, fnx])
def test_product_node_mapping_reads_mutate_later_factor_layers(name, cls_name, library):
    def query(module, graph_library):
        right = getattr(graph_library, cls_name)()
        right.add_edge(0, 1, weight=1)
        calls = []

        class NodeAttrs(dict):
            def get(self, key, default=None):
                calls.append(key)
                right.add_edge(1, 2, weight=9)
                return super().get(key, default)

        left = getattr(graph_library, cls_name)()
        left.add_edge(0, 1)
        left._node = {0: NodeAttrs(value=11), 1: NodeAttrs()}
        result = getattr(module, name)(left, right)
        return _product_snapshot(result), calls, _product_snapshot(right)

    assert query(fnx, library) == query(nx, nx)


@pytest.mark.parametrize("name", ["tensor_product", "strong_product"])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("change_topology", [False, True])
def test_product_edge_mapping_get_keeps_later_layers_live(name, cls_name, change_topology):
    def query(module):
        right = getattr(nx, cls_name)()
        right.add_edge(0, 1, weight=2)
        calls = []

        class EdgeAttrs(dict):
            def get(self, key, default=None):
                calls.append(key)
                if change_topology:
                    right.add_edge(1, 2, weight=7)
                else:
                    attrs = right[0][1][0] if right.is_multigraph() else right[0][1]
                    attrs["weight"] = 7
                return super().get(key, default)

        class LeftGraph(getattr(nx, cls_name)):
            edge_attr_dict_factory = EdgeAttrs

        left = LeftGraph()
        left.add_edge(0, 1, weight=3)
        try:
            result = getattr(module, name)(left, right)
        except RuntimeError as error:
            result = (type(error), str(error))
        else:
            result = _product_snapshot(result)
        return result, calls, _product_snapshot(right)

    assert query(fnx) == query(nx)


@pytest.mark.parametrize("name", _LIVE_PRODUCTS)
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_product_live_factors_preserve_arbitrary_attributes_and_keys(name, cls_name):
    class Factor(getattr(nx, cls_name)):
        pass

    left, right = Factor(), Factor()
    shared = []
    for graph in (left, right):
        graph.add_nodes_from([(0, {None: shared, ("node",): 4}), (1, {})])
        if graph.is_multigraph():
            graph.add_edges_from([
                (0, 1, ("parallel", 0), {None: shared, "key": 3}),
                (0, 1, ("parallel", 1), {("edge",): 5}),
                (1, 1, ("loop",), {None: 7}),
            ])
        else:
            graph.add_edges_from([(0, 1, {None: shared, "key": 3}), (1, 1, {("edge",): 5})])
        graph.graph["excluded"] = "factor metadata"

    expected = getattr(nx, name)(left, right)
    actual = getattr(fnx, name)(left, right)
    assert _product_snapshot(actual) == _product_snapshot(expected)
    assert actual.nodes[(0, 0)][None][0] is shared
    assert actual.nodes[(0, 0)][None][1] is shared
    actual.nodes[(0, 0)]["new"] = True
    assert "new" not in left.nodes[0]
    assert "new" not in right.nodes[0]


@pytest.mark.parametrize("name", _LIVE_PRODUCTS)
def test_product_does_not_read_factor_graph_metadata(name):
    class UnreadableMetadata(dict):
        def keys(self):
            raise AssertionError("product read graph metadata")

        def __iter__(self):
            raise AssertionError("product read graph metadata")

    left, right = nx.path_graph(2), nx.path_graph(3)
    left.graph = UnreadableMetadata(secret=1)
    right.graph = UnreadableMetadata(secret=2)
    assert _product_snapshot(getattr(fnx, name)(left, right)) == _product_snapshot(
        getattr(nx, name)(left, right)
    )


@pytest.mark.parametrize("name", _LIVE_PRODUCTS)
@pytest.mark.parametrize("left_cls,right_cls", [
    ("Graph", "MultiGraph"), ("MultiGraph", "Graph"),
    ("DiGraph", "MultiDiGraph"), ("MultiDiGraph", "DiGraph"),
])
def test_product_live_mixed_multiplicity_keeps_parallel_keys(name, left_cls, right_cls):
    def factor(cls_name):
        class Factor(getattr(nx, cls_name)):
            pass

        graph = Factor()
        graph.add_nodes_from([(0, {None: []}), (1, {("node",): "value"})])
        if graph.is_multigraph():
            graph.add_edges_from([
                (0, 1, ("edge", 0), {None: 4, "key": 5}),
                (0, 1, ("edge", 1), {"other": 2}),
                (1, 1, ("loop",), {}),
            ])
        else:
            graph.add_edges_from([(0, 1, {None: 4, "key": 5}), (1, 1, {})])
        return graph

    left, right = factor(left_cls), factor(right_cls)
    assert _product_snapshot(getattr(fnx, name)(left, right)) == _product_snapshot(
        getattr(nx, name)(left, right)
    )
