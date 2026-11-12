"""Parity for ``__str__`` on view classes and Graph.

Bead br-r37-c1-mpv5x. Several ``__str__`` implementations diverged
from nx:

- View classes (NodeView, EdgeView, DegreeView, NodeDataView,
  EdgeDataView, AtlasView, AdjacencyView) fell back to ``__repr__``
  (e.g. ``'NodeView((0, 1, 2))'``) instead of nx's bare-data form
  (``'[0, 1, 2]'``).
- ``Graph.__str__`` ignored the graph name attribute entirely.
  ``str(fnx.Graph(name='foo'))`` returned
  ``'Graph with 0 nodes and 0 edges'`` while nx returns
  ``"Graph named 'foo' with 0 nodes and 0 edges"``.

Drop-in code that does ``print(G)``, ``print(G.nodes)``, or asserts
on ``str(view)`` got different output.
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
# View __str__ — bare-data form
# ---------------------------------------------------------------------------

@needs_nx
def test_node_view_str_is_bare_list():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G.nodes) == str(GX.nodes) == "[0, 1, 2]"


@needs_nx
def test_edge_view_str_is_bare_list():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G.edges) == str(GX.edges) == "[(0, 1), (1, 2)]"


@needs_nx
def test_degree_view_str_is_bare_list_of_pairs():
    """nx DegreeView.__str__ returns str(list(self)), not str(dict)."""
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G.degree) == str(GX.degree)
    assert str(G.degree).startswith("[")


@needs_nx
def test_node_data_view_str_is_bare_list():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G.nodes(data=True)) == str(GX.nodes(data=True))


@needs_nx
def test_edge_data_view_str_is_bare_list():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G.edges(data=True)) == str(GX.edges(data=True))


@needs_nx
def test_atlas_view_str_is_bare_dict():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G.adj[0]) == str(GX.adj[0]) == "{1: {}}"


@needs_nx
def test_adjacency_view_str_is_bare_dict():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G.adj) == str(GX.adj)


# ---------------------------------------------------------------------------
# Graph.__str__ includes name when set
# ---------------------------------------------------------------------------

@needs_nx
def test_graph_str_no_name_matches_networkx():
    G = fnx.Graph()
    GX = nx.Graph()
    assert str(G) == str(GX) == "Graph with 0 nodes and 0 edges"


@needs_nx
def test_graph_str_with_name_includes_name():
    G = fnx.Graph(name="foo")
    GX = nx.Graph(name="foo")
    assert str(G) == str(GX) == "Graph named 'foo' with 0 nodes and 0 edges"


@needs_nx
def test_graph_str_path_graph():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert str(G) == str(GX)


@needs_nx
def test_digraph_str_matches_networkx():
    DG = fnx.DiGraph([(0, 1)])
    DGX = nx.DiGraph([(0, 1)])
    assert str(DG) == str(DGX) == "DiGraph with 2 nodes and 1 edges"


@needs_nx
def test_multigraph_str_with_name():
    MG = fnx.MultiGraph([(0, 1), (0, 1)])
    MG.graph["name"] = "bar"
    MGX = nx.MultiGraph([(0, 1), (0, 1)])
    MGX.graph["name"] = "bar"
    assert str(MG) == str(MGX)


@needs_nx
def test_multidigraph_str_with_name():
    MDG = fnx.MultiDiGraph(name="my-graph")
    MDGX = nx.MultiDiGraph(name="my-graph")
    assert str(MDG) == str(MDGX)


# ---------------------------------------------------------------------------
# Behavioural sanity
# ---------------------------------------------------------------------------

@needs_nx
def test_print_node_view_matches_networkx_format():
    """Drop-in ``print(G.nodes)`` behaves like nx."""
    import io
    from contextlib import redirect_stdout

    G = fnx.path_graph(3)
    GX = nx.path_graph(3)

    fbuf = io.StringIO()
    with redirect_stdout(fbuf):
        print(G.nodes)
    nbuf = io.StringIO()
    with redirect_stdout(nbuf):
        print(GX.nodes)

    assert fbuf.getvalue() == nbuf.getvalue()


@needs_nx
def test_str_is_distinct_from_repr_on_views():
    """str() must NOT fall through to repr() for these views — nx
    distinguishes them deliberately."""
    G = fnx.path_graph(3)
    assert str(G.nodes) != repr(G.nodes)
    assert str(G.edges) != repr(G.edges)
    assert str(G.degree) != repr(G.degree)
