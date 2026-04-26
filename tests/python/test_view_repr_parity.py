"""Parity for ``__repr__`` of view classes.

Bead br-r37-c1-k147g. Several view-class repr implementations diverged
from nx:

- NodeView/DegreeView reprs stringified node IDs: integers became
  ``'0', '1', ...``. The actual stored values were integers — only
  the repr lied.
- EdgeView repr showed ``EdgeView(2 edges)`` instead of nx's
  ``EdgeView([(0, 1), (1, 2)])``.
- AtlasView/AdjacencyView reprs fell through to default
  ``<franken_networkx.AtlasView object at 0x...>`` instead of nx's
  ``AtlasView({1: {}})``.
- DiGraph/MultiGraph/MultiDiGraph edge views need different class
  prefixes (OutEdgeView, MultiEdgeView, OutMultiEdgeView).

Drop-in debugging output, repr-snapshot tests, and any tooling
comparing __repr__ output broke.
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


# ---------------------------------------------------------------------------
# NodeView
# ---------------------------------------------------------------------------

@needs_nx
def test_node_view_repr_preserves_int_node_ids():
    """The actual node IDs are integers; repr must NOT stringify them."""
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert repr(G.nodes) == repr(GX.nodes) == "NodeView((0, 1, 2))"


@needs_nx
def test_node_view_repr_preserves_string_node_ids():
    G = fnx.Graph()
    G.add_nodes_from(["a", "b", "c"])
    GX = nx.Graph()
    GX.add_nodes_from(["a", "b", "c"])
    assert repr(G.nodes) == repr(GX.nodes)


@needs_nx
def test_node_view_repr_empty():
    G = fnx.Graph()
    GX = nx.Graph()
    assert repr(G.nodes) == repr(GX.nodes) == "NodeView(())"


# ---------------------------------------------------------------------------
# EdgeView class-name prefixes
# ---------------------------------------------------------------------------

@needs_nx
def test_graph_edge_view_repr():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert repr(G.edges) == repr(GX.edges)


@needs_nx
def test_digraph_edge_view_uses_out_edge_view_prefix():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    f = repr(DG.edges)
    n = repr(DGX.edges)
    assert f == n
    assert f.startswith("OutEdgeView(")


@needs_nx
def test_multigraph_edge_view_uses_multi_edge_view_prefix():
    MG = fnx.MultiGraph([(0, 1), (0, 1)])
    MGX = nx.MultiGraph([(0, 1), (0, 1)])
    assert repr(MG.edges) == repr(MGX.edges)
    assert repr(MG.edges).startswith("MultiEdgeView(")


@needs_nx
def test_multidigraph_edge_view_uses_out_multi_edge_view_prefix():
    MDG = fnx.MultiDiGraph([(0, 1), (0, 1)])
    MDGX = nx.MultiDiGraph([(0, 1), (0, 1)])
    assert repr(MDG.edges) == repr(MDGX.edges)
    assert repr(MDG.edges).startswith("OutMultiEdgeView(")


# ---------------------------------------------------------------------------
# DegreeView
# ---------------------------------------------------------------------------

@needs_nx
def test_degree_view_repr_preserves_int_node_ids():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert repr(G.degree) == repr(GX.degree) == "DegreeView({0: 1, 1: 2, 2: 1})"


@needs_nx
def test_degree_view_repr_preserves_string_node_ids():
    G = fnx.Graph()
    G.add_edges_from([("a", "b"), ("b", "c")])
    GX = nx.Graph()
    GX.add_edges_from([("a", "b"), ("b", "c")])
    assert repr(G.degree) == repr(GX.degree)


# ---------------------------------------------------------------------------
# AtlasView / AdjacencyView
# ---------------------------------------------------------------------------

@needs_nx
def test_atlas_view_repr_shows_dict_content():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    f = repr(G.adj[0])
    n = repr(GX.adj[0])
    assert f == n
    assert f.startswith("AtlasView(")


@needs_nx
def test_adjacency_view_repr_shows_full_mapping():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert repr(G.adj) == repr(GX.adj)


@needs_nx
def test_multi_adjacency_view_repr():
    MG = fnx.MultiGraph([(0, 1), (1, 2)])
    f = repr(MG.adj)
    assert "MultiAdjacencyView" in f or "AdjacencyView" in f
    # Must show the actual mapping, not a memory address.
    assert "0x" not in f
    assert "object at" not in f


# ---------------------------------------------------------------------------
# Behavioural sanity
# ---------------------------------------------------------------------------

@needs_nx
def test_node_view_repr_after_mutation_is_live():
    G = fnx.path_graph(3)
    initial = repr(G.nodes)
    G.add_node(99)
    after = repr(G.nodes)
    assert after != initial
    assert "99" in after
