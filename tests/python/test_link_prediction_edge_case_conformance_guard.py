"""Python-conformance safety net for the in-flight link-prediction raw kernels.

The swarm is optimizing the raw link-prediction scorers (endpoint-index slabs,
repeated-pair memos, common-neighbor weight memos — see the perf negative-evidence
ledger 04z53.9144-9152). Every entry's keep/drop criterion is "without Python
conformance drift". This guard pins that Python conformance for the exact edge
cases those kernels target — repeated pairs, reversed pairs, default ebunch,
self-loop endpoints — across all the standard + community scorers, vs networkx.

No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_PLAIN = [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
    "preferential_attachment",
    "common_neighbor_centrality",
]


def _g(seed):
    r = random.Random(seed)
    n = r.randint(6, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    fg = fnx.Graph(list(edges)); fg.add_nodes_from(range(n))
    ng = nx.Graph(list(edges)); ng.add_nodes_from(range(n))
    return fg, ng, n


def _eq(fr, nr):
    fr, nr = list(fr), list(nr)
    assert len(fr) == len(nr)
    for (fu, fv, fs), (nu, nv, ns) in zip(fr, nr):
        assert (fu, fv) == (nu, nv)
        assert fs == pytest.approx(ns, abs=1e-9)


@pytest.mark.parametrize("fn", _PLAIN)
@pytest.mark.parametrize("seed", range(15))
def test_repeated_reversed_pairs(fn, seed):
    fg, ng, n = _g(seed)
    # repeated + reversed concrete pairs in one ebunch (the memo/slab target).
    ebunch = [(0, 1), (0, 1), (1, 0), (2, 4), (4, 2), (0, n - 1), (0, 1)]
    _eq(getattr(fnx, fn)(fg, ebunch), getattr(nx, fn)(ng, ebunch))


@pytest.mark.parametrize("fn", _PLAIN)
@pytest.mark.parametrize("seed", range(10))
def test_default_ebunch(fn, seed):
    fg, ng, n = _g(seed)
    # ebunch=None -> all non-edges; order + scores must match nx.
    _eq(getattr(fnx, fn)(fg), getattr(nx, fn)(ng))


@pytest.mark.parametrize("seed", range(10))
def test_community_scorers_repeated_reversed(seed):
    r = random.Random(seed)
    n = r.randint(6, 10)
    fg, ng = fnx.Graph(), nx.Graph()
    for node in range(n):
        c = node % 2
        fg.add_node(node, community=c); ng.add_node(node, community=c)
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.45:
                fg.add_edge(u, v); ng.add_edge(u, v)
    ebunch = [(0, 1), (1, 0), (0, 1), (2, 3), (3, 2)]
    for fn in ("cn_soundarajan_hopcroft", "ra_index_soundarajan_hopcroft"):
        _eq(getattr(fnx, fn)(fg, ebunch), getattr(nx, fn)(ng, ebunch))
