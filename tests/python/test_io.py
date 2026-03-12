"""Tests for I/O functions: read/write_edgelist, read/write_adjlist,
read/write_graphml, node_link_data/graph."""

import os
import tempfile

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triangle():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(0, 2)
    return G


@pytest.fixture
def weighted_graph():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1.5)
    G.add_edge(1, 2, weight=2.5)
    return G


@pytest.fixture
def small_digraph():
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 2)
    return D


# ---------------------------------------------------------------------------
# node_link_data / node_link_graph
# ---------------------------------------------------------------------------


class TestNodeLinkFormat:
    def test_round_trip(self, triangle):
        data = fnx.node_link_data(triangle)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 3

        H = fnx.node_link_graph(data)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 3

    def test_with_attrs(self, weighted_graph):
        data = fnx.node_link_data(weighted_graph)
        H = fnx.node_link_graph(data)
        assert H.number_of_edges() == 2

    def test_digraph_round_trip(self, small_digraph):
        data = fnx.node_link_data(small_digraph)
        assert "nodes" in data
        assert "edges" in data
        H = fnx.node_link_graph(data)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 2


# ---------------------------------------------------------------------------
# read/write_edgelist
# ---------------------------------------------------------------------------


class TestEdgelistIO:
    def test_round_trip(self, triangle):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".edgelist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_edgelist(triangle, path)
            H = fnx.read_edgelist(path)
            assert H.number_of_edges() == 3
        finally:
            os.unlink(path)

    def test_digraph(self, small_digraph):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".edgelist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_edgelist(small_digraph, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# read/write_adjlist
# ---------------------------------------------------------------------------


class TestAdjlistIO:
    def test_round_trip(self, triangle):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".adjlist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_adjlist(triangle, path)
            H = fnx.read_adjlist(path)
            assert H.number_of_nodes() == 3
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# read/write_graphml
# ---------------------------------------------------------------------------


class TestGraphMLIO:
    def test_round_trip(self, triangle):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_graphml(triangle, path)
            H = fnx.read_graphml(path)
            assert H.number_of_nodes() == 3
            assert H.number_of_edges() == 3
        finally:
            os.unlink(path)

    def test_weighted(self, weighted_graph):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_graphml(weighted_graph, path)
            H = fnx.read_graphml(path)
            assert H.number_of_edges() == 2
        finally:
            os.unlink(path)
