"""Differential + golden parity for semi-supervised node classification.

Covers ``harmonic_function`` and ``local_and_global_consistency`` from
``networkx.algorithms.node_classification``. Neither had a dedicated test
file. Both propagate a handful of seed labels across the graph and return
a predicted label per node (in node order).

Locks fnx to upstream networkx across random connected labeled graphs, a
custom ``label_name``, a two-cluster golden, and the no-label
``NetworkXError`` contract.

br-r37-c1-9gol0
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import node_classification as fnx_nc
from networkx.algorithms import node_classification as nx_nc


def _labeled_pair(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    p_cur = p
    for _ in range(60):
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        if nx.is_connected(ng):
            # seed two labels at the extreme nodes.
            for node, label in [(0, "A"), (n - 1, "B")]:
                fg.nodes[node]["label"] = label
                ng.nodes[node]["label"] = label
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


@pytest.mark.parametrize("fn", ["harmonic_function", "local_and_global_consistency"])
@pytest.mark.parametrize("seed", range(40))
def test_node_classification_matches_networkx(fn, seed):
    pair = _labeled_pair(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    assert getattr(fnx_nc, fn)(fg) == getattr(nx_nc, fn)(ng)


@pytest.mark.parametrize("seed", range(20))
def test_harmonic_function_custom_label_name_matches_networkx(seed):
    pair = _labeled_pair(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, n = pair
    # Re-key the seed labels under a custom attribute name.
    for g in (fg, ng):
        for node in (0, n - 1):
            g.nodes[node]["community"] = g.nodes[node].pop("label")
    assert fnx_nc.harmonic_function(fg, label_name="community") == (
        nx_nc.harmonic_function(ng, label_name="community")
    )


def test_two_cluster_golden():
    # Two triangles joined by a bridge; seed one label in each triangle.
    edges = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3)]
    fg = fnx.Graph(edges)
    fg.nodes[0]["label"] = "X"
    fg.nodes[5]["label"] = "Y"
    result = fnx_nc.harmonic_function(fg)
    assert result == ["X", "X", "X", "Y", "Y", "Y"]
    ng = nx.Graph(edges)
    ng.nodes[0]["label"] = "X"
    ng.nodes[5]["label"] = "Y"
    assert result == nx_nc.harmonic_function(ng)


@pytest.mark.parametrize("fn", ["harmonic_function", "local_and_global_consistency"])
def test_no_labels_raises_like_networkx(fn):
    fg = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXError):
        getattr(fnx_nc, fn)(fg)
    with pytest.raises(nx.NetworkXError):
        getattr(nx_nc, fn)(ng)
