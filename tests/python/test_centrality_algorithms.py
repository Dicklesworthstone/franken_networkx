"""Tests for additional centrality algorithm bindings.

Tests cover:
- in_degree_centrality
- out_degree_centrality
- local_reaching_centrality
- global_reaching_centrality
- group_degree_centrality
- group_in_degree_centrality
- group_out_degree_centrality
"""

import inspect

import networkx as nx
import pytest
import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def directed_chain():
    """a->b->c."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


@pytest.fixture
def directed_cycle():
    """a->b->c->a."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


@pytest.fixture
def triangle():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


# ---------------------------------------------------------------------------
# in_degree_centrality
# ---------------------------------------------------------------------------

class TestInDegreeCentrality:
    def test_chain(self, directed_chain):
        dc = fnx.in_degree_centrality(directed_chain)
        assert dc["a"] == pytest.approx(0.0)
        assert dc["b"] == pytest.approx(0.5)
        assert dc["c"] == pytest.approx(0.5)

    def test_cycle(self, directed_cycle):
        dc = fnx.in_degree_centrality(directed_cycle)
        # Each node has in-degree 1, n-1=2
        for v in ["a", "b", "c"]:
            assert dc[v] == pytest.approx(0.5)

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.in_degree_centrality(triangle)


# ---------------------------------------------------------------------------
# out_degree_centrality
# ---------------------------------------------------------------------------

class TestOutDegreeCentrality:
    def test_chain(self, directed_chain):
        dc = fnx.out_degree_centrality(directed_chain)
        assert dc["a"] == pytest.approx(0.5)
        assert dc["b"] == pytest.approx(0.5)
        assert dc["c"] == pytest.approx(0.0)

    def test_complementary(self, directed_cycle):
        """In a regular digraph, in and out degree centrality should match."""
        in_dc = fnx.in_degree_centrality(directed_cycle)
        out_dc = fnx.out_degree_centrality(directed_cycle)
        for v in ["a", "b", "c"]:
            assert in_dc[v] == pytest.approx(out_dc[v])


# ---------------------------------------------------------------------------
# local_reaching_centrality
# ---------------------------------------------------------------------------

class TestLocalReachingCentrality:
    def test_signature_matches_networkx(self):
        assert str(inspect.signature(fnx.local_reaching_centrality)) == str(
            inspect.signature(nx.local_reaching_centrality)
        )

    def test_connected_undirected(self, triangle):
        assert fnx.local_reaching_centrality(triangle, "a") == pytest.approx(1.0)

    def test_disconnected_undirected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_node("c")
        assert fnx.local_reaching_centrality(g, "a") == pytest.approx(0.5)

    def test_directed_chain(self, directed_chain):
        assert fnx.local_reaching_centrality(directed_chain, "a") == pytest.approx(1.0)
        assert fnx.local_reaching_centrality(directed_chain, "c") == pytest.approx(0.0)

    def test_directed_middle(self, directed_chain):
        assert fnx.local_reaching_centrality(directed_chain, "b") == pytest.approx(0.5)

    def test_path_graph_matches_networkx(self):
        fg = fnx.path_graph(5)
        ng = nx.path_graph(5)
        for node in fg:
            assert fnx.local_reaching_centrality(fg, node) == pytest.approx(
                nx.local_reaching_centrality(ng, node)
            )

    def test_weighted_path_matches_networkx(self):
        fg = fnx.path_graph(5)
        ng = nx.path_graph(5)
        for i, (u, v) in enumerate(fg.edges()):
            fg[u][v]["weight"] = i + 1
        for i, (u, v) in enumerate(ng.edges()):
            ng[u][v]["weight"] = i + 1
        for node in fg:
            assert fnx.local_reaching_centrality(
                fg, node, weight="weight"
            ) == pytest.approx(nx.local_reaching_centrality(ng, node, weight="weight"))

    def test_backend_keyword_surface_matches_networkx(self):
        fg = fnx.path_graph(4)
        ng = nx.path_graph(4)

        for backend in (None, "networkx"):
            assert fnx.local_reaching_centrality(fg, 0, backend=backend) == pytest.approx(
                nx.local_reaching_centrality(ng, 0, backend=backend)
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.local_reaching_centrality(fg, 0, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.local_reaching_centrality(ng, 0, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.local_reaching_centrality(fg, 0, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.local_reaching_centrality(ng, 0, backend_kwargs={"x": 1})


# ---------------------------------------------------------------------------
# global_reaching_centrality
# ---------------------------------------------------------------------------

class TestGlobalReachingCentrality:
    def test_signature_matches_networkx(self):
        assert str(inspect.signature(fnx.global_reaching_centrality)) == str(
            inspect.signature(nx.global_reaching_centrality)
        )

    def test_connected_undirected(self, triangle):
        # All nodes reach all others: GRC = 0
        assert fnx.global_reaching_centrality(triangle) == pytest.approx(0.0)

    def test_directed_chain(self, directed_chain):
        # local reaching = [1.0, 0.5, 0.0], max=1.0
        # GRC = ((0) + (0.5) + (1.0)) / 2 = 0.75
        assert fnx.global_reaching_centrality(directed_chain) == pytest.approx(0.75)

    def test_path_graph_matches_networkx(self):
        fg = fnx.path_graph(5)
        ng = nx.path_graph(5)
        assert fnx.global_reaching_centrality(fg) == pytest.approx(
            nx.global_reaching_centrality(ng)
        )

    def test_weighted_path_matches_networkx(self):
        fg = fnx.path_graph(5)
        ng = nx.path_graph(5)
        for i, (u, v) in enumerate(fg.edges()):
            fg[u][v]["weight"] = i + 1
        for i, (u, v) in enumerate(ng.edges()):
            ng[u][v]["weight"] = i + 1
        assert fnx.global_reaching_centrality(fg, weight="weight") == pytest.approx(
            nx.global_reaching_centrality(ng, weight="weight")
        )

    def test_backend_keyword_surface_matches_networkx(self):
        fg = fnx.path_graph(4)
        ng = nx.path_graph(4)

        for backend in (None, "networkx"):
            assert fnx.global_reaching_centrality(fg, backend=backend) == pytest.approx(
                nx.global_reaching_centrality(ng, backend=backend)
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.global_reaching_centrality(fg, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.global_reaching_centrality(ng, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.global_reaching_centrality(fg, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.global_reaching_centrality(ng, backend_kwargs={"x": 1})


# ---------------------------------------------------------------------------
# laplacian_centrality
# ---------------------------------------------------------------------------

class TestLaplacianCentrality:
    def test_signature_matches_networkx(self):
        assert str(inspect.signature(fnx.laplacian_centrality)) == str(
            inspect.signature(nx.laplacian_centrality)
        )

    def test_path_graph_matches_networkx(self):
        fg = fnx.path_graph(5)
        ng = nx.path_graph(5)
        assert fnx.laplacian_centrality(fg) == pytest.approx(
            nx.laplacian_centrality(ng)
        )

    def test_directed_graph_matches_networkx(self):
        fg = fnx.DiGraph()
        fg.add_edges_from([(0, 1), (1, 2), (0, 2), (2, 3)])
        ng = nx.DiGraph()
        ng.add_edges_from([(0, 1), (1, 2), (0, 2), (2, 3)])
        assert fnx.laplacian_centrality(fg) == pytest.approx(
            nx.laplacian_centrality(ng)
        )

    def test_directed_walk_type_and_alpha_match_networkx(self):
        fg = fnx.DiGraph()
        fg.add_edges_from([(0, 1), (1, 2), (0, 2), (2, 3)])
        ng = nx.DiGraph()
        ng.add_edges_from([(0, 1), (1, 2), (0, 2), (2, 3)])
        assert fnx.laplacian_centrality(
            fg, walk_type="pagerank", alpha=0.85
        ) == pytest.approx(
            nx.laplacian_centrality(ng, walk_type="pagerank", alpha=0.85)
        )

    def test_backend_keyword_surface_matches_networkx(self):
        fg = fnx.path_graph(4)
        ng = nx.path_graph(4)

        for backend in (None, "networkx"):
            assert fnx.laplacian_centrality(fg, backend=backend) == pytest.approx(
                nx.laplacian_centrality(ng, backend=backend)
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.laplacian_centrality(fg, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.laplacian_centrality(ng, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.laplacian_centrality(fg, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.laplacian_centrality(ng, backend_kwargs={"x": 1})

    def test_null_graph_error_matches_networkx(self):
        fg = fnx.Graph()
        ng = nx.Graph()

        with pytest.raises(fnx.NetworkXPointlessConcept, match="null graph has no centrality defined"):
            fnx.laplacian_centrality(fg)
        with pytest.raises(nx.NetworkXPointlessConcept, match="null graph has no centrality defined"):
            nx.laplacian_centrality(ng)

    def test_edgeless_graph_contract_matches_networkx(self):
        fg = fnx.Graph()
        fg.add_nodes_from([1, 2, 3])
        ng = nx.Graph()
        ng.add_nodes_from([1, 2, 3])

        with pytest.raises(ZeroDivisionError, match="graph with no edges has zero full energy"):
            fnx.laplacian_centrality(fg)
        with pytest.raises(ZeroDivisionError, match="graph with no edges has zero full energy"):
            nx.laplacian_centrality(ng)

        assert fnx.laplacian_centrality(fg, normalized=False) == pytest.approx(
            nx.laplacian_centrality(ng, normalized=False)
        )


# ---------------------------------------------------------------------------
# approximate_current_flow_betweenness_centrality
# ---------------------------------------------------------------------------

class TestApproximateCurrentFlowBetweennessCentrality:
    def test_signature_matches_networkx(self):
        assert str(
            inspect.signature(fnx.approximate_current_flow_betweenness_centrality)
        ) == str(inspect.signature(nx.approximate_current_flow_betweenness_centrality))

    def test_fixed_seed_matches_networkx(self):
        fg = fnx.path_graph(4)
        ng = nx.path_graph(4)
        assert fnx.approximate_current_flow_betweenness_centrality(
            fg, seed=1
        ) == pytest.approx(
            nx.approximate_current_flow_betweenness_centrality(ng, seed=1)
        )

    def test_extended_parameters_match_networkx(self):
        fg = fnx.path_graph(4)
        ng = nx.path_graph(4)
        kwargs = {
            "seed": 1,
            "normalized": False,
            "epsilon": 1.0,
            "solver": "lu",
            "dtype": float,
            "sample_weight": 1,
        }
        assert fnx.approximate_current_flow_betweenness_centrality(
            fg, **kwargs
        ) == pytest.approx(
            nx.approximate_current_flow_betweenness_centrality(ng, **kwargs)
        )

    def test_backend_keyword_surface_matches_networkx(self):
        fg = fnx.path_graph(4)
        ng = nx.path_graph(4)

        for backend in (None, "networkx"):
            assert fnx.approximate_current_flow_betweenness_centrality(
                fg, seed=1, backend=backend
            ) == pytest.approx(
                nx.approximate_current_flow_betweenness_centrality(
                    ng, seed=1, backend=backend
                )
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.approximate_current_flow_betweenness_centrality(
                fg, seed=1, backend="parallel"
            )
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.approximate_current_flow_betweenness_centrality(
                ng, seed=1, backend="parallel"
            )

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.approximate_current_flow_betweenness_centrality(
                fg, seed=1, backend_kwargs={"x": 1}
            )
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.approximate_current_flow_betweenness_centrality(
                ng, seed=1, backend_kwargs={"x": 1}
            )

    def test_directed_error_matches_networkx(self):
        fg = fnx.DiGraph()
        fg.add_edge(0, 1)
        ng = nx.DiGraph()
        ng.add_edge(0, 1)

        with pytest.raises(fnx.NetworkXNotImplemented, match="not implemented for directed type"):
            fnx.approximate_current_flow_betweenness_centrality(fg, seed=1)
        with pytest.raises(nx.NetworkXNotImplemented, match="not implemented for directed type"):
            nx.approximate_current_flow_betweenness_centrality(ng, seed=1)

    def test_disconnected_error_matches_networkx(self):
        fg = fnx.Graph()
        fg.add_edges_from([(0, 1), (2, 3)])
        ng = nx.Graph()
        ng.add_edges_from([(0, 1), (2, 3)])

        with pytest.raises(fnx.NetworkXError, match="Graph not connected\\."):
            fnx.approximate_current_flow_betweenness_centrality(fg, seed=1)
        with pytest.raises(nx.NetworkXError, match="Graph not connected\\."):
            nx.approximate_current_flow_betweenness_centrality(ng, seed=1)

    def test_invalid_solver_matches_networkx(self):
        fg = fnx.path_graph(4)
        ng = nx.path_graph(4)

        with pytest.raises(KeyError, match="bogus"):
            fnx.approximate_current_flow_betweenness_centrality(
                fg, seed=1, solver="bogus"
            )
        with pytest.raises(KeyError, match="bogus"):
            nx.approximate_current_flow_betweenness_centrality(
                ng, seed=1, solver="bogus"
            )


# ---------------------------------------------------------------------------
# group_degree_centrality
# ---------------------------------------------------------------------------

class TestGroupDegreeCentrality:
    def test_single_node_triangle(self, triangle):
        # {a} neighbors outside = {b,c}, non-group=2, so 1.0
        assert fnx.group_degree_centrality(triangle, ["a"]) == pytest.approx(1.0)

    def test_disconnected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_node("c")
        # {a} neighbors outside = {b}, non-group=2, so 0.5
        assert fnx.group_degree_centrality(g, ["a"]) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# group_in_degree_centrality
# ---------------------------------------------------------------------------

class TestGroupInDegreeCentrality:
    def test_simple(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("c", "b")
        # Group {b}: predecessors outside = {a,c}, non-group=2
        assert fnx.group_in_degree_centrality(g, ["b"]) == pytest.approx(1.0)

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.group_in_degree_centrality(triangle, ["a"])


# ---------------------------------------------------------------------------
# group_out_degree_centrality
# ---------------------------------------------------------------------------

class TestGroupOutDegreeCentrality:
    def test_simple(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        # Group {a}: successors outside = {b,c}, non-group=2
        assert fnx.group_out_degree_centrality(g, ["a"]) == pytest.approx(1.0)

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.group_out_degree_centrality(triangle, ["a"])
