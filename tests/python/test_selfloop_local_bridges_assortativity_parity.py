"""Parity for local_bridges and degree_assortativity_coefficient with self-loops.

Bead br-r37-c1-tqcpg (same self-loop edge-case sweep as br-r37-c1-1boe3).

- local_bridges: nx tests ``set(G[u]) & set(G[v])`` without removing the
  endpoints, so a self-loop on an endpoint counts as a shared neighbour and the
  edge is NOT a local bridge. fnx previously discarded the endpoints first, so
  it disagreed once an endpoint carried a self-loop. (Loop-free graphs agree
  either way.)
- degree_assortativity_coefficient: the native Rust fast-path miscomputes the
  degree-mixing statistic with self-loops; self-loop graphs now delegate to nx.
"""

from __future__ import annotations

import math
import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _norm_span(triples):
    out = []
    for t in triples:
        u, v, s = t
        out.append((tuple(sorted((u, v))), "inf" if s == float("inf") else round(s, 6)))
    return sorted(out)


def _norm_pairs(pairs):
    return sorted(tuple(sorted((u, v))) for u, v in pairs)


@needs_nx
def test_witness_local_bridges_selfloops():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (0, 0), (3, 3)]
    f, n = fnx.Graph(), nx.Graph()
    for u, v in edges:
        f.add_edge(u, v)
        n.add_edge(u, v)
    assert _norm_span(list(fnx.local_bridges(f))) == _norm_span(list(nx.local_bridges(n)))


@needs_nx
@pytest.mark.parametrize("with_span", [True, False])
@pytest.mark.parametrize("seed", list(range(35)))
def test_random_local_bridges(with_span, seed):
    rng = random.Random(seed * 29 + (7 if with_span else 2))
    n = rng.randint(2, 10)
    ng = nx.gnp_random_graph(n, rng.choice([0.2, 0.4, 0.6]), seed=seed)
    for u in list(ng.nodes()):
        if rng.random() < 0.35:
            ng.add_edge(u, u)
    fg = fnx.Graph()
    for u in ng.nodes():
        fg.add_node(u)
    for u, v in ng.edges():
        fg.add_edge(u, v)
    fr = list(fnx.local_bridges(fg, with_span=with_span))
    nr = list(nx.local_bridges(ng, with_span=with_span))
    if with_span:
        assert _norm_span(fr) == _norm_span(nr)
    else:
        assert _norm_pairs(fr) == _norm_pairs(nr)


@needs_nx
@pytest.mark.parametrize("seed", list(range(20)))
def test_weighted_span_local_bridges(seed):
    rng = random.Random(seed * 11 + 4)
    n = rng.randint(3, 9)
    ng = nx.gnp_random_graph(n, 0.4, seed=seed)
    for u in list(ng.nodes()):
        if rng.random() < 0.3:
            ng.add_edge(u, u)
    fg = fnx.Graph()
    for u in ng.nodes():
        fg.add_node(u)
    for u, v in ng.edges():
        w = float(rng.choice([1.0, 2.0, 3.0]))
        ng[u][v]["weight"] = w
        fg.add_edge(u, v, weight=w)
    assert _norm_span(list(fnx.local_bridges(fg, weight="weight"))) == _norm_span(
        list(nx.local_bridges(ng, weight="weight"))
    )


def _assort_eq(a, b):
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isnan(a) != math.isnan(b):
        return False
    return abs(a - b) < 1e-7


@needs_nx
def test_witness_assortativity_selfloops():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (0, 0), (3, 3)]
    f, n = fnx.Graph(), nx.Graph()
    for u, v in edges:
        f.add_edge(u, v)
        n.add_edge(u, v)
    assert _assort_eq(
        fnx.degree_assortativity_coefficient(f),
        nx.degree_assortativity_coefficient(n),
    )


@needs_nx
@pytest.mark.parametrize("seed", list(range(35)))
def test_random_assortativity_selfloops(seed):
    rng = random.Random(seed * 31 + 9)
    n = rng.randint(3, 11)
    ng = nx.gnp_random_graph(n, rng.choice([0.3, 0.5]), seed=seed)
    for u in list(ng.nodes()):
        if rng.random() < 0.35:
            ng.add_edge(u, u)
    fg = fnx.Graph()
    for u in ng.nodes():
        fg.add_node(u)
    for u, v in ng.edges():
        fg.add_edge(u, v)
    if ng.number_of_edges() == 0:
        return
    assert _assort_eq(
        fnx.degree_assortativity_coefficient(fg),
        nx.degree_assortativity_coefficient(ng),
    )
