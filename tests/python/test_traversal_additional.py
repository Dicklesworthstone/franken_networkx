"""Tests for additional traversal algorithm bindings.

Tests cover:
- edge_bfs
- edge_dfs
"""

import networkx as nx
import pytest
import franken_networkx as fnx

from franken_networkx.backend import _fnx_to_nx as _to_nx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def path3():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


@pytest.fixture
def triangle():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


@pytest.fixture
def directed_chain():
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


# ---------------------------------------------------------------------------
# edge_bfs
# ---------------------------------------------------------------------------

class TestEdgeBfs:
    def test_path(self, path3):
        edges = list(fnx.edge_bfs(path3, "a"))
        edge_set = {(u, v) for u, v in edges}
        assert ("a", "b") in edge_set
        assert ("b", "c") in edge_set

    def test_directed(self, directed_chain):
        edges = list(fnx.edge_bfs(directed_chain, "a"))
        edge_set = {(u, v) for u, v in edges}
        assert ("a", "b") in edge_set
        assert ("b", "c") in edge_set

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("a")
        edges = list(fnx.edge_bfs(g, "a"))
        assert edges == []


# ---------------------------------------------------------------------------
# edge_dfs
# ---------------------------------------------------------------------------

class TestEdgeDfs:
    def test_path(self, path3):
        edges = list(fnx.edge_dfs(path3, "a"))
        assert len(edges) >= 2

    def test_directed(self, directed_chain):
        edges = list(fnx.edge_dfs(directed_chain, "a"))
        edge_set = {(u, v) for u, v in edges}
        assert ("a", "b") in edge_set
        assert ("b", "c") in edge_set

    def test_triangle(self, triangle):
        edges = list(fnx.edge_dfs(triangle, "a"))
        # Triangle has 3 edges
        assert len(edges) == 3

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("a")
        edges = list(fnx.edge_dfs(g, "a"))
        assert edges == []


def test_edge_bfs_none_source_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 0), (1, 0), (2, 0), (2, 1), (3, 1)])

    expected = list(nx.edge_bfs(_to_nx(graph)))

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX edge_bfs fallback")

    monkeypatch.setattr(nx, "edge_bfs", fail)

    assert list(fnx.edge_bfs(graph)) == expected


def test_edge_bfs_orientation_ignore_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.MultiDiGraph()
    graph.add_edges_from([(0, 1), (1, 0), (1, 0), (2, 0), (2, 1), (3, 1)])

    expected = list(nx.edge_bfs(_to_nx(graph), [0, 1, 2, 3], orientation="ignore"))

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX edge_bfs fallback")

    monkeypatch.setattr(nx, "edge_bfs", fail)

    assert list(fnx.edge_bfs(graph, [0, 1, 2, 3], orientation="ignore")) == expected


def test_edge_dfs_none_source_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 0), (1, 0), (2, 0), (2, 1), (3, 1)])

    expected = list(nx.edge_dfs(_to_nx(graph)))

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX edge_dfs fallback")

    monkeypatch.setattr(nx, "edge_dfs", fail)

    assert list(fnx.edge_dfs(graph)) == expected


def test_edge_dfs_orientation_ignore_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.MultiDiGraph()
    graph.add_edges_from([(0, 1), (1, 0), (1, 0), (2, 0), (2, 1), (3, 1)])

    expected = list(nx.edge_dfs(_to_nx(graph), [0, 1, 2, 3], orientation="ignore"))

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX edge_dfs fallback")

    monkeypatch.setattr(nx, "edge_dfs", fail)

    assert list(fnx.edge_dfs(graph, [0, 1, 2, 3], orientation="ignore")) == expected


@pytest.mark.parametrize("function_name", ["edge_bfs", "edge_dfs"])
def test_edge_traversal_invalid_orientation_matches_networkx_without_fallback(
    monkeypatch, function_name
):
    graph = fnx.DiGraph()
    graph.add_edges_from([(0, 1), (1, 2)])
    nx_graph = _to_nx(graph)
    nx_function = getattr(nx, function_name)
    fnx_function = getattr(fnx, function_name)

    with pytest.raises(nx.NetworkXError, match="invalid orientation argument."):
        list(nx_function(nx_graph, 0, orientation="hello"))

    def fail(*args, **kwargs):
        raise AssertionError(f"unexpected NetworkX {function_name} fallback")

    monkeypatch.setattr(nx, function_name, fail)

    with pytest.raises(fnx.NetworkXError, match="invalid orientation argument."):
        list(fnx_function(graph, 0, orientation="hello"))
