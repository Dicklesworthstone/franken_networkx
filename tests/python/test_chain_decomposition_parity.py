"""Differential + golden parity for ``chain_decomposition``.

``chain_decomposition(G[, root])`` yields the chains of a DFS-based
(Gabow) chain decomposition — each chain is a list of directed edges.
fnx replicates networkx's traversal exactly, so chain order AND edge
orientation are compared byte-for-byte. No dedicated test file existed.

br-r37-c1-xsvhs
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(6, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("seed", range(60))
def test_chain_decomposition_exact_match_networkx(seed):
    fg, ng = _pair(seed)
    fc = [list(c) for c in fnx.chain_decomposition(fg)]
    nc = [list(c) for c in nx.chain_decomposition(ng)]
    assert fc == nc


@pytest.mark.parametrize("seed", range(20))
def test_chain_decomposition_root_param_matches_networkx(seed):
    fg, ng = _pair(seed)
    if 0 not in [n for n in ng.nodes()]:
        pytest.skip("node 0 absent")
    fc = [list(c) for c in fnx.chain_decomposition(fg, root=0)]
    nc = [list(c) for c in nx.chain_decomposition(ng, root=0)]
    assert fc == nc


def test_chain_decomposition_goldens():
    # A single cycle decomposes into exactly one chain covering every edge.
    cyc = fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
    ncyc = nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
    fchains = [list(c) for c in fnx.chain_decomposition(cyc)]
    assert len(fchains) == 1
    assert len(fchains[0]) == 4
    assert fchains == [list(c) for c in nx.chain_decomposition(ncyc)]
    # A tree has no chains (no cycles).
    tree = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    assert list(fnx.chain_decomposition(tree)) == []
