"""Parity coverage for all_pairs_shortest_path(_length) iterator contract.

Bead franken_networkx-pnrd: both wrappers must return generators of
(source, mapping) pairs, matching upstream NetworkX's public surface,
rather than plain dicts.
"""

import types

import networkx as nx
import pytest

import franken_networkx as fnx


def test_all_pairs_shortest_path_returns_generator_of_pairs():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)

    f_res = fnx.all_pairs_shortest_path(fg)
    n_res = nx.all_pairs_shortest_path(ng)

    assert isinstance(f_res, types.GeneratorType)
    assert isinstance(n_res, types.GeneratorType)

    # Source-insertion order matches upstream.
    f_pairs = list(f_res)
    n_pairs = list(n_res)
    assert [s for s, _ in f_pairs] == [s for s, _ in n_pairs]
    # Every per-source dict matches upstream.
    f_dict = dict(f_pairs)
    n_dict = dict(n_pairs)
    for src in n_dict:
        assert f_dict[src] == n_dict[src]


def test_all_pairs_shortest_path_length_returns_generator_of_pairs():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)

    f_res = fnx.all_pairs_shortest_path_length(fg)
    n_res = nx.all_pairs_shortest_path_length(ng)

    assert isinstance(f_res, types.GeneratorType)
    assert isinstance(n_res, types.GeneratorType)

    f_pairs = list(f_res)
    n_pairs = list(n_res)
    assert [s for s, _ in f_pairs] == [s for s, _ in n_pairs]
    f_dict = dict(f_pairs)
    n_dict = dict(n_pairs)
    for src in n_dict:
        assert f_dict[src] == n_dict[src]


def test_all_pairs_shortest_path_cutoff_preserved():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    f = dict(fnx.all_pairs_shortest_path(fg, cutoff=2))
    n = dict(nx.all_pairs_shortest_path(ng, cutoff=2))
    for src in n:
        # Every path within cutoff must match upstream.
        assert f[src] == n[src]


def test_all_pairs_shortest_path_directed_matches_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for graph in (fg, ng):
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (4, 0)])

    assert list(fnx.all_pairs_shortest_path(fg)) == list(nx.all_pairs_shortest_path(ng))
    assert list(fnx.all_pairs_shortest_path_length(fg)) == list(
        nx.all_pairs_shortest_path_length(ng)
    )
    assert list(fnx.all_pairs_shortest_path(fg, cutoff=1)) == list(
        nx.all_pairs_shortest_path(ng, cutoff=1)
    )


def test_all_pairs_shortest_path_rejects_unknown_backend():
    fg = fnx.path_graph(3)
    with pytest.raises(ImportError):
        list(fnx.all_pairs_shortest_path(fg, backend="nonexistent"))
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        list(fnx.all_pairs_shortest_path(fg, foo="bar"))


def test_all_pairs_shortest_path_length_rejects_unknown_backend():
    fg = fnx.path_graph(3)
    with pytest.raises(ImportError):
        list(fnx.all_pairs_shortest_path_length(fg, backend="nonexistent"))
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        list(fnx.all_pairs_shortest_path_length(fg, foo="bar"))


def _networkx_distance_matrix(graph, sources, nodelist, cutoff=None):
    np = pytest.importorskip("numpy")
    matrix = np.full((len(sources), len(nodelist)), -1, dtype=np.int32)
    positions = {node: index for index, node in enumerate(nodelist)}
    for row, source in enumerate(sources):
        for target, distance in nx.single_source_shortest_path_length(
            graph, source, cutoff=cutoff
        ).items():
            matrix[row, positions[target]] = distance
    return matrix


@pytest.mark.parametrize(
    ("fnx_type", "nx_type", "edges"),
    [
        (fnx.Graph, nx.Graph, [(0, 1), (1, 2), (3, 4)]),
        (fnx.DiGraph, nx.DiGraph, [(0, 1), (1, 2), (3, 4)]),
        (fnx.MultiGraph, nx.MultiGraph, [(0, 1), (0, 1), (1, 2), (3, 4)]),
        (fnx.MultiDiGraph, nx.MultiDiGraph, [(0, 1), (0, 1), (1, 2), (3, 4)]),
    ],
)
@pytest.mark.parametrize("cutoff", [None, 0, 1, 3])
def test_shortest_path_length_matrix_matches_networkx(
    fnx_type, nx_type, edges, cutoff
):
    np = pytest.importorskip("numpy")
    fg = fnx_type()
    ng = nx_type()
    for graph in (fg, ng):
        graph.add_nodes_from(range(6))
        graph.add_edges_from(edges)
    sources = [2, 3, 2, 5]
    actual = fnx.shortest_path_length_matrix(fg, sources, cutoff=cutoff)
    expected = _networkx_distance_matrix(ng, sources, list(ng), cutoff=cutoff)

    assert actual.dtype == np.int32
    assert actual.shape == (len(sources), len(ng))
    assert not actual.flags.writeable
    np.testing.assert_array_equal(actual, expected)


def test_shortest_path_length_matrix_defaults_views_and_edge_cases():
    np = pytest.importorskip("numpy")
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)

    full = fnx.shortest_path_length_matrix(fg)
    expected = _networkx_distance_matrix(ng, list(ng), list(ng))
    np.testing.assert_array_equal(full, expected)

    view = fg.subgraph([1, 2, 3, 4])
    nx_view = ng.subgraph([1, 2, 3, 4])
    view_matrix = fnx.shortest_path_length_matrix(view, [4, 1], cutoff=2)
    view_expected = _networkx_distance_matrix(
        nx_view, [4, 1], list(nx_view), cutoff=2
    )
    np.testing.assert_array_equal(view_matrix, view_expected)

    negative = fnx.shortest_path_length_matrix(fg, [2], cutoff=-1)
    np.testing.assert_array_equal(negative, np.array([[-1, -1, 0, -1, -1, -1]]))
    assert fnx.shortest_path_length_matrix(fg, []).shape == (0, len(fg))
    assert fnx.shortest_path_length_matrix(fnx.Graph()).shape == (0, 0)

    with pytest.raises(fnx.NodeNotFound, match="Source 99 is not in G"):
        fnx.shortest_path_length_matrix(fg, [99])
