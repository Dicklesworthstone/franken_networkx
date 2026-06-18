"""Value parity on DISCONNECTED graphs.

Disconnected graphs exercise unreachable / infinite-distance handling, where
a kernel can quietly diverge from networkx (closeness uses the
Wasserman-Faust correction, harmonic sums 1/inf = 0, efficiency skips
unreachable pairs). This pins fnx == networkx on multi-component graphs.

NOTE: g and ng are built with a SINGLE weight draw per edge so both libraries
get identical inputs — separate draws would inject an asymmetric-construction
artifact (a recurring false-positive source) rather than test the algorithm.

No mocks: real fnx and real networkx on forced-disconnected graphs.
"""

from __future__ import annotations

import math
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _norm(x):
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, float):
        return round(x, 5) if math.isfinite(x) else repr(x)
    if isinstance(x, (list, tuple)):
        return type(x)(_norm(v) for v in x)
    return x


def _forced_disconnected(seed):
    """Two-component graph built identically in fnx and nx."""
    r = random.Random(seed)
    n = r.randint(6, 11)
    split = n // 2
    fg = fnx.Graph(); fg.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            same_component = (u < split) == (v < split)
            if same_component and r.random() < 0.5:
                w = r.randint(1, 5)  # single draw → identical in both
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng


_FUNCS = [
    ("closeness", lambda L, G: L.closeness_centrality(G)),
    ("harmonic", lambda L, G: L.harmonic_centrality(G)),
    ("betweenness", lambda L, G: L.betweenness_centrality(G)),
    ("pagerank", lambda L, G: L.pagerank(G)),
    ("constraint", lambda L, G: L.constraint(G)),
    ("clustering", lambda L, G: L.clustering(G)),
    ("load", lambda L, G: L.load_centrality(G)),
    ("katz_numpy", lambda L, G: L.katz_centrality_numpy(G)),
    ("all_pairs_spl", lambda L, G: dict(L.all_pairs_shortest_path_length(G))),
]


@pytest.mark.parametrize("name,call", _FUNCS)
@pytest.mark.parametrize("seed", range(30))
def test_disconnected_value_parity(name, call, seed):
    fg, ng = _forced_disconnected(seed)
    assert _norm(call(fnx, fg)) == _norm(call(nx, ng))


@pytest.mark.parametrize("seed", range(30))
def test_scalar_efficiency_parity(seed):
    fg, ng = _forced_disconnected(seed)
    assert round(fnx.global_efficiency(fg), 5) == round(nx.global_efficiency(ng), 5)
    assert round(fnx.average_clustering(fg), 5) == round(
        nx.average_clustering(ng), 5
    )
