"""Differential + golden parity for ``dedensify``.

``dedensify(G, threshold)`` compresses high-degree neighbourhoods by
introducing auto-named "compressor" nodes, returning ``(compressed_graph,
compressor_nodes)``. The compressor names are derived deterministically
from the compressed node set, so fnx reproduces nx's exact output. No
dedicated test file existed.

br-r37-c1-hoylk
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _signature(G):
    return (
        sorted(map(str, G.nodes())),
        sorted((str(u), str(v)) for u, v in G.edges()),
    )


def _pair(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("threshold", [2, 3])
@pytest.mark.parametrize("seed", range(40))
def test_dedensify_matches_networkx(threshold, seed):
    fg, ng = _pair(seed)
    fr, fc = fnx.dedensify(fg, threshold=threshold)
    nr, nc = nx.dedensify(ng, threshold=threshold)
    assert _signature(fr) == _signature(nr)
    assert sorted(map(str, fc)) == sorted(map(str, nc))


def test_dedensify_golden():
    # Three sources each pointing at the same three targets -> one compressor.
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for source in (1, 2, 3):
        for target in ("A", "B", "C"):
            fg.add_edge(source, target)
            ng.add_edge(source, target)
    fr, fc = fnx.dedensify(fg, threshold=2)
    nr, nc = nx.dedensify(ng, threshold=2)
    # Exactly one compressor node is introduced; its auto-generated name is
    # derived from the (hash-ordered) compressed set, so fnx must produce the
    # SAME name as nx but the literal value is not pinned across runs.
    assert len(fc) == len(nc) == 1
    assert sorted(map(str, fc)) == sorted(map(str, nc))
    assert _signature(fr) == _signature(nr)


def test_dedensify_copy_does_not_mutate_input():
    fg = fnx.DiGraph()
    for source in (1, 2, 3):
        for target in ("A", "B", "C"):
            fg.add_edge(source, target)
    before = fg.number_of_edges()
    fnx.dedensify(fg, threshold=2, copy=True)
    assert fg.number_of_edges() == before
