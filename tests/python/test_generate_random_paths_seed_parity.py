"""Seeded ``generate_random_paths`` parity with NetworkX."""

from __future__ import annotations

import franken_networkx as fnx
import networkx as nx
import pytest


def _path_pair():
    return fnx.path_graph(4), nx.path_graph(4)


def test_seeded_generate_random_paths_matches_networkx():
    fnx_graph, nx_graph = _path_pair()

    assert list(fnx.generate_random_paths(fnx_graph, 2, seed=42)) == list(
        nx.generate_random_paths(nx_graph, 2, seed=42)
    )


def test_seeded_generate_random_paths_with_source_matches_networkx():
    fnx_graph, nx_graph = _path_pair()

    assert list(fnx.generate_random_paths(fnx_graph, 3, seed=7, source=1)) == list(
        nx.generate_random_paths(nx_graph, 3, seed=7, source=1)
    )


def test_generate_random_paths_index_map_matches_networkx():
    fnx_graph, nx_graph = _path_pair()
    fnx_index = {}
    nx_index = {}

    fnx_paths = list(fnx.generate_random_paths(fnx_graph, 3, index_map=fnx_index, seed=5))
    nx_paths = list(nx.generate_random_paths(nx_graph, 3, index_map=nx_index, seed=5))

    assert fnx_paths == nx_paths
    assert fnx_index == nx_index


def test_generate_random_paths_missing_source_message_matches_networkx():
    fnx_graph, nx_graph = _path_pair()

    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        list(fnx.generate_random_paths(fnx_graph, 1, seed=1, source=99))
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        list(nx.generate_random_paths(nx_graph, 1, seed=1, source=99))

    assert str(fnx_exc.value) == str(nx_exc.value)
