"""Differential parity for ``bfs_layers`` and ``bfs_beam_edges``.

``bfs_layers(G, sources)`` yields the BFS frontier node lists by distance;
``bfs_beam_edges(G, source, value, width)`` is a beam-limited BFS edge
generator. Neither had a dedicated test file. Both are order-deterministic,
so this compares exact output.

br-r37-c1-9cg1l
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.3):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_bfs_layers_single_source_matches_networkx(directed, seed):
    fg, ng, _ = _pair(seed, directed=directed)
    assert [list(layer) for layer in fnx.bfs_layers(fg, 0)] == [
        list(layer) for layer in nx.bfs_layers(ng, 0)
    ]


@pytest.mark.parametrize("seed", range(30))
def test_bfs_layers_multi_source_matches_networkx(seed):
    fg, ng, n = _pair(seed)
    sources = [0, n - 1]
    assert [list(layer) for layer in fnx.bfs_layers(fg, sources)] == [
        list(layer) for layer in nx.bfs_layers(ng, sources)
    ]


@pytest.mark.parametrize("seed", range(30))
def test_bfs_beam_edges_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    cent_f = fnx.degree_centrality(fg)
    cent_n = nx.degree_centrality(ng)
    fr = list(fnx.bfs_beam_edges(fg, 0, lambda v: cent_f[v], width=2))
    nr = list(nx.bfs_beam_edges(ng, 0, lambda v: cent_n[v], width=2))
    assert fr == nr


def test_bfs_layers_goldens():
    # On a path the layers are singletons by increasing distance.
    assert [list(layer) for layer in fnx.bfs_layers(fnx.path_graph(5), 0)] == [
        [0], [1], [2], [3], [4]
    ]
    # On a star, layer 0 is the center, layer 1 is all leaves.
    star_layers = [sorted(layer) for layer in fnx.bfs_layers(fnx.star_graph(4), 0)]
    assert star_layers == [[0], [1, 2, 3, 4]]
