"""Parity for Graph constructor with numpy.ndarray / pandas.DataFrame.

Bead br-r37-c1-rxigp. ``fnx.Graph(numpy_adj_matrix)`` and
``fnx.Graph(pandas_df)`` returned empty graphs (every edge silently
dropped). nx auto-detects these types via ``to_networkx_graph`` and
dispatches to ``from_numpy_array`` / ``from_pandas_adjacency``. Both
helpers exist on fnx but the constructor wasn't routing to them.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

try:
    import numpy as np
    HAS_NP = True
except ImportError:
    HAS_NP = False

try:
    import pandas as pd
    HAS_PD = True
except ImportError:
    HAS_PD = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
needs_np = pytest.mark.skipif(not HAS_NP, reason="numpy not installed")
needs_pd = pytest.mark.skipif(not HAS_PD, reason="pandas not installed")


# ---------------------------------------------------------------------------
# numpy.ndarray adjacency matrix
# ---------------------------------------------------------------------------

@needs_nx
@needs_np
def test_graph_from_numpy_path_adjacency():
    A = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    f = fnx.Graph(A)
    n = nx.Graph(A)
    assert sorted(f.edges) == sorted(n.edges) == [(0, 1), (1, 2)]


@needs_nx
@needs_np
def test_digraph_from_numpy_directed_adjacency():
    A = np.array([[0, 1, 0], [0, 0, 1], [0, 0, 0]])
    f = fnx.DiGraph(A)
    n = nx.DiGraph(A)
    assert sorted(f.edges) == sorted(n.edges) == [(0, 1), (1, 2)]


@needs_nx
@needs_np
def test_graph_from_numpy_with_weights():
    A = np.array([[0, 2.5, 0], [2.5, 0, 1.0], [0, 1.0, 0]])
    f = fnx.Graph(A)
    n = nx.Graph(A)
    assert dict(f[0]) == dict(n[0])
    assert dict(f[1]) == dict(n[1])


@needs_nx
@needs_np
def test_multigraph_from_numpy_with_parallel_edges():
    """An adjacency value > 1 means parallel edges in nx for MultiGraph."""
    A = np.array([[0, 2, 0], [2, 0, 1], [0, 1, 0]])
    f = fnx.MultiGraph(A)
    n = nx.MultiGraph(A)
    assert f.number_of_edges() == n.number_of_edges()


@needs_nx
@needs_np
def test_empty_numpy_array_yields_empty_graph():
    A = np.zeros((3, 3), dtype=int)
    f = fnx.Graph(A)
    n = nx.Graph(A)
    assert sorted(f.edges) == sorted(n.edges) == []
    assert sorted(f.nodes) == sorted(n.nodes) == [0, 1, 2]


# ---------------------------------------------------------------------------
# pandas.DataFrame adjacency
# ---------------------------------------------------------------------------

@needs_nx
@needs_pd
def test_graph_from_pandas_dataframe_adjacency():
    df = pd.DataFrame([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    f = fnx.Graph(df)
    n = nx.Graph(df)
    assert sorted(f.edges) == sorted(n.edges) == [(0, 1), (1, 2)]


@needs_nx
@needs_pd
def test_digraph_from_pandas_dataframe_adjacency():
    df = pd.DataFrame([[0, 1, 0], [0, 0, 1], [0, 0, 0]])
    f = fnx.DiGraph(df)
    n = nx.DiGraph(df)
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
@needs_pd
def test_pandas_with_string_index_node_labels():
    """Nodes should be the dataframe row/column labels."""
    df = pd.DataFrame(
        [[0, 1, 0], [1, 0, 1], [0, 1, 0]],
        index=["a", "b", "c"],
        columns=["a", "b", "c"],
    )
    f = fnx.Graph(df)
    n = nx.Graph(df)
    assert sorted(f.nodes) == sorted(n.nodes) == ["a", "b", "c"]
    assert sorted(f.edges) == sorted(n.edges)


# ---------------------------------------------------------------------------
# Regression check — list-of-edges constructor still works
# ---------------------------------------------------------------------------

@needs_nx
def test_list_of_edges_constructor_still_works():
    """The numpy/pandas detection must not regress the edge-list path."""
    f = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    n = nx.Graph([(0, 1), (1, 2), (2, 3)])
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
def test_dict_of_dict_constructor_still_works():
    """Earlier br-r37-c1-9m2vs / br-r37-c1-lc3em paths must still work."""
    f = fnx.Graph({0: {1: {"w": 5}}})
    n = nx.Graph({0: {1: {"w": 5}}})
    assert list(f.edges(data=True)) == list(n.edges(data=True))
