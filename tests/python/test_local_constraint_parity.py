"""Differential + golden parity for ``local_constraint``.

``local_constraint(G, u, v[, weight])`` is the Burt local constraint of
``u`` with respect to ``v``. ``constraint`` and ``effective_size`` already
have coverage; ``local_constraint`` did not.

br-r37-c1-xc692
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, weighted=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
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
                if weighted:
                    w = round(rng.uniform(1, 4), 2)
                    fg.add_edge(u, v, weight=w)
                    ng.add_edge(u, v, weight=w)
                else:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(15))
def test_local_constraint_matches_networkx(directed, weighted, seed):
    fg, ng, n = _pair(seed, directed=directed, weighted=weighted)
    kwargs = {"weight": "weight"} if weighted else {}
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            fr = fnx.local_constraint(fg, u, v, **kwargs)
            nr = nx.local_constraint(ng, u, v, **kwargs)
            if nr != nr:  # NaN
                assert fr != fr
            else:
                assert fr == pytest.approx(nr, abs=1e-9)


def test_local_constraint_golden():
    # Triangle: the local constraint of 0 w.r.t. 1 is (p01 + p02*p21)^2.
    g = fnx.Graph([(0, 1), (1, 2), (2, 0)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0)])
    assert fnx.local_constraint(g, 0, 1) == pytest.approx(0.5625)
    assert fnx.local_constraint(g, 0, 1) == pytest.approx(nx.local_constraint(ng, 0, 1))


def test_local_constraint_missing_node_raises_like_networkx():
    fg = fnx.Graph([(0, 1)])
    ng = nx.Graph([(0, 1)])
    with pytest.raises(nx.NetworkXError):
        fnx.local_constraint(fg, "x", 1)
    with pytest.raises(nx.NetworkXError):
        nx.local_constraint(ng, "x", 1)
