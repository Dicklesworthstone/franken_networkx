"""Tests for bipartite I/O, connectivity auxiliary digraphs, and bridges dispatch parity."""

import io
import tempfile
import networkx as nx
import pytest
import scipy.sparse as sp

import franken_networkx as fnx
from franken_networkx import bipartite as fnx_bipartite
from franken_networkx import connectivity as fnx_conn


def test_bipartite_parse_edgelist_parity():
    lines = [
        "# Initial comment",
        "1 2",
        "1 3 {\"weight\": 4.5, \"color\": \"blue\"}",
        "2 4",
        "# Trailing comment",
    ]
    # Default parse
    g_fnx = fnx_bipartite.parse_edgelist(lines, nodetype=int)
    g_nx = nx.algorithms.bipartite.parse_edgelist(lines, nodetype=int)

    assert isinstance(g_fnx, fnx.Graph)
    assert list(g_fnx.nodes(data=True)) == list(g_nx.nodes(data=True))
    assert list(g_fnx.edges(data=True)) == list(g_nx.edges(data=True))

    # Parse with typed data tuples
    lines_typed = [
        "1 2 4.5",
        "2 3 7.5",
        "3 4 10.0",
    ]
    g_typed_fnx = fnx_bipartite.parse_edgelist(
        lines_typed, nodetype=int, data=[("weight", float)]
    )
    g_typed_nx = nx.algorithms.bipartite.parse_edgelist(
        lines_typed, nodetype=int, data=[("weight", float)]
    )
    assert isinstance(g_typed_fnx, fnx.Graph)
    assert list(g_typed_fnx.nodes(data=True)) == list(g_typed_nx.nodes(data=True))
    assert list(g_typed_fnx.edges(data=True)) == list(g_typed_nx.edges(data=True))

    # Parse with create_using DiGraph
    g_di_fnx = fnx_bipartite.parse_edgelist(lines, nodetype=int, create_using=fnx.DiGraph)
    assert isinstance(g_di_fnx, fnx.DiGraph)
    assert g_di_fnx.is_directed()


def test_bipartite_read_edgelist_parity():
    content = b"""# File comment
nodeA nodeB 1.2
nodeA nodeC 3.4
nodeB nodeD 5.6
"""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(content)
        tf.flush()
        filename = tf.name

    g_fnx = fnx_bipartite.read_edgelist(filename, data=[("weight", float)])
    g_nx = nx.algorithms.bipartite.read_edgelist(filename, data=[("weight", float)])

    assert isinstance(g_fnx, fnx.Graph)
    assert list(g_fnx.nodes(data=True)) == list(g_nx.nodes(data=True))
    assert list(g_fnx.edges(data=True)) == list(g_nx.edges(data=True))


def test_bipartite_from_biadjacency_matrix_parity():
    A = sp.csr_matrix([[1, 0, 2], [0, 3, 4]])
    rows = ["r0", "r1"]
    cols = ["c0", "c1", "c2"]

    for create_using, nx_create_using in [
        (None, None),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        g_fnx = fnx_bipartite.from_biadjacency_matrix(
            A,
            create_using=create_using,
            row_order=rows,
            column_order=cols,
            edge_attribute="cost",
        )
        g_nx = nx.algorithms.bipartite.from_biadjacency_matrix(
            A,
            create_using=nx_create_using,
            row_order=rows,
            column_order=cols,
            edge_attribute="cost",
        )

        assert list(g_fnx.nodes(data=True)) == list(g_nx.nodes(data=True))
        assert list(g_fnx.edges(data=True)) == list(g_nx.edges(data=True))


def test_connectivity_auxiliary_node_connectivity_parity():
    test_graphs = [
        (fnx.Graph([(0, 1), (1, 2), (2, 3), (0, 2)]), nx.Graph([(0, 1), (1, 2), (2, 3), (0, 2)])),
        (fnx.DiGraph([(0, 1), (1, 2), (2, 0)]), nx.DiGraph([(0, 1), (1, 2), (2, 0)])),
        (fnx.MultiGraph([(0, 1), (0, 1), (1, 2)]), nx.MultiGraph([(0, 1), (0, 1), (1, 2)])),
        (fnx.MultiDiGraph([(0, 1), (0, 1), (1, 2)]), nx.MultiDiGraph([(0, 1), (0, 1), (1, 2)])),
        (fnx.Graph([("alpha", "beta")]), nx.Graph([("alpha", "beta")])),
    ]

    for g_fnx, g_nx in test_graphs:
        aux_fnx = fnx_conn.build_auxiliary_node_connectivity(g_fnx)
        aux_nx = nx.algorithms.connectivity.build_auxiliary_node_connectivity(g_nx)

        assert isinstance(aux_fnx, fnx.DiGraph)
        assert list(aux_fnx.nodes(data=True)) == list(aux_nx.nodes(data=True))
        assert list(aux_fnx.edges(data=True)) == list(aux_nx.edges(data=True))
        assert aux_fnx.graph["mapping"] == aux_nx.graph["mapping"]


def test_connectivity_auxiliary_edge_connectivity_parity():
    test_graphs = [
        (fnx.Graph([(0, 1), (1, 2), (2, 3), (0, 2)]), nx.Graph([(0, 1), (1, 2), (2, 3), (0, 2)])),
        (fnx.DiGraph([(0, 1), (1, 2), (2, 0)]), nx.DiGraph([(0, 1), (1, 2), (2, 0)])),
        (fnx.MultiGraph([(0, 1), (0, 1), (1, 2)]), nx.MultiGraph([(0, 1), (0, 1), (1, 2)])),
        (fnx.MultiDiGraph([(0, 1), (0, 1), (1, 2)]), nx.MultiDiGraph([(0, 1), (0, 1), (1, 2)])),
    ]

    for g_fnx, g_nx in test_graphs:
        aux_fnx = fnx_conn.build_auxiliary_edge_connectivity(g_fnx)
        aux_nx = nx.algorithms.connectivity.build_auxiliary_edge_connectivity(g_nx)

        assert isinstance(aux_fnx, fnx.DiGraph)
        assert list(aux_fnx.nodes(data=True)) == list(aux_nx.nodes(data=True))
        assert list(aux_fnx.edges(data=True)) == list(aux_nx.edges(data=True))


def test_bridges_backend_dispatch_and_execution_parity():
    G_fnx = fnx.path_graph(5)
    G_nx = nx.path_graph(5)

    # Calling fnx.bridges directly must not fail with TypeError: bridges() got an unexpected keyword argument 'backend'
    bridges_fnx = list(fnx.bridges(G_fnx))
    bridges_nx = list(nx.bridges(G_nx))
    assert bridges_fnx == bridges_nx

    # Calling fnx.has_bridges
    assert fnx.has_bridges(G_fnx) == nx.has_bridges(G_nx)

    # Calling fnx.local_bridges
    local_fnx = list(fnx.local_bridges(G_fnx))
    local_nx = list(nx.local_bridges(G_nx))
    assert local_fnx == local_nx
