"""Edge-case contracts for the optimized core_number / effective_size paths.

These functions were de-delegated / given native kernels and matrix paths, with
explicit branches for directed (in+out degree, antiparallel arcs counted
twice), multigraph (NotImplemented), self-loops (NotImplemented), and weighted
inputs. Those branches are exactly where an optimization can silently diverge
from networkx, so this pins each one.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(30))
def test_core_number_directed_in_plus_out_degree(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    fd, nd = fnx.DiGraph(edges), nx.DiGraph(edges)
    # Directed core number uses in+out degree (antiparallel counted twice).
    assert fnx.core_number(fd) == nx.core_number(nd)
    # Undirected on the same edge set.
    ug = fnx.Graph([(u, v) for u, v in edges if u < v])
    nug = nx.Graph([(u, v) for u, v in edges if u < v])
    assert fnx.core_number(ug) == nx.core_number(nug)


def test_core_number_multigraph_and_selfloop_raise():
    for builder in (
        lambda L: L.MultiGraph([(0, 1), (0, 1)]),
        lambda L: L.Graph([(0, 0), (0, 1)]),
    ):
        with pytest.raises(nx.NetworkXNotImplemented):
            fnx.core_number(builder(fnx))
        with pytest.raises(nx.NetworkXNotImplemented):
            nx.core_number(builder(nx))


def test_k_core_family_consumes_core_number_consistently():
    # k_core / k_shell / k_crust all build on core_number; check directed parity.
    r = random.Random(7)
    n = 9
    edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.4]
    fd, nd = fnx.DiGraph(edges), nx.DiGraph(edges)
    assert sorted(fnx.k_core(fd).nodes()) == sorted(nx.k_core(nd).nodes())
    assert sorted(fnx.k_shell(fd).nodes()) == sorted(nx.k_shell(nd).nodes())


def test_effective_size_directed_and_weighted_paths():
    # Directed and weighted inputs take the matrix / delegated paths.
    fd = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    nd = nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    assert {k: round(v, 6) for k, v in fnx.effective_size(fd).items()} == (
        {k: round(v, 6) for k, v in nx.effective_size(nd).items()}
    )
    gw = fnx.Graph()
    ngw = nx.Graph()
    for u, v, w in [(0, 1, 2), (1, 2, 3), (0, 2, 1)]:
        gw.add_edge(u, v, weight=w)
        ngw.add_edge(u, v, weight=w)
    assert {k: round(v, 6) for k, v in fnx.effective_size(gw, weight="weight").items()} == (
        {k: round(v, 6) for k, v in nx.effective_size(ngw, weight="weight").items()}
    )
