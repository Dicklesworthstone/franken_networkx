"""Differential + golden parity for ``reconstruct_path``.

``reconstruct_path(source, target, predecessors)`` walks the nested
Floyd-Warshall predecessor table to rebuild a path. It is a pure-Python
table walk, so feeding fnx and nx the *same* predecessor table must yield
identical output.

br-r37-c1-wtcuj
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _predecessor_table(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    ng = nx.DiGraph()
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < 0.4:
                ng.add_edge(u, v, weight=rng.randint(1, 9))
    pred, _ = nx.floyd_warshall_predecessor_and_distance(ng)
    return pred, n


@pytest.mark.parametrize("seed", range(50))
def test_reconstruct_path_matches_networkx_on_same_table(seed):
    pred, n = _predecessor_table(seed)
    for s in range(n):
        for t in range(n):
            # Both libraries walk the identical table -> identical result.
            try:
                expected = nx.reconstruct_path(s, t, pred)
            except KeyError as exc:
                with pytest.raises(KeyError) as fnx_exc:
                    fnx.reconstruct_path(s, t, pred)
                assert fnx_exc.value.args == exc.args
                continue
            assert fnx.reconstruct_path(s, t, pred) == expected


def test_reconstruct_path_goldens():
    # Unique shortest paths on a small chain-with-shortcut DAG.
    g = nx.DiGraph()
    for u, v, w in [(0, 1, 1), (1, 2, 1), (2, 3, 1), (0, 3, 10)]:
        g.add_edge(u, v, weight=w)
    pred, _ = nx.floyd_warshall_predecessor_and_distance(g)
    assert fnx.reconstruct_path(0, 3, pred) == [0, 1, 2, 3]
    assert fnx.reconstruct_path(0, 0, pred) == []  # source == target
    assert fnx.reconstruct_path(1, 3, pred) == [1, 2, 3]


def test_reconstruct_path_rejects_flat_predecessor_maps_like_networkx():
    flat = {"a": [], "b": ["a"], "c": ["b"]}

    for source, target in [("a", "c"), ("a", "missing")]:
        with pytest.raises(TypeError) as fnx_exc:
            fnx.reconstruct_path(source, target, flat)
        with pytest.raises(TypeError) as nx_exc:
            nx.reconstruct_path(source, target, flat)
        assert fnx_exc.value.args == nx_exc.value.args

    with pytest.raises(KeyError) as fnx_exc:
        fnx.reconstruct_path("missing", "c", flat)
    with pytest.raises(KeyError) as nx_exc:
        nx.reconstruct_path("missing", "c", flat)
    assert fnx_exc.value.args == nx_exc.value.args

    assert fnx.reconstruct_path("a", "a", flat) == nx.reconstruct_path("a", "a", flat)


def test_reconstruct_path_missing_source_raises_keyerror():
    g = nx.DiGraph([(0, 1), (1, 2)])
    pred, _ = nx.floyd_warshall_predecessor_and_distance(g)
    with pytest.raises(KeyError):
        fnx.reconstruct_path("missing", 2, pred)
    with pytest.raises(KeyError):
        nx.reconstruct_path("missing", 2, pred)
