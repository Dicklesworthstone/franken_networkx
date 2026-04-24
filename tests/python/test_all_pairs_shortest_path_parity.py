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
