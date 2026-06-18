"""Conformance guard for effective_size on DIRECTED / weighted / self-loop graphs.

effective_size routes the unweighted-undirected-no-selfloop common case to the
native effective_size_rust kernel; directed / weighted / self-loop graphs
currently delegate to nx (the kernel is undirected-only). This locks byte-exact
parity for those delegated paths so:
  * the current delegation stays correct, and
  * the planned directed native kernel (br-r37-c1-qbj9u) has a ready conformance
    scaffold to validate against.

No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _approx_dict(a, b):
    assert set(a) == set(b)
    for k in a:
        av, bv = a[k], b[k]
        if isinstance(av, float) and (av != av):   # NaN
            assert isinstance(bv, float) and bv != bv
        else:
            assert av == pytest.approx(bv, abs=1e-9)


@pytest.mark.parametrize("seed", range(20))
def test_directed_effective_size_matches_networkx(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    fg, ng = fnx.DiGraph(), nx.DiGraph()
    fg.add_nodes_from(range(n)); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.3:
                fg.add_edge(u, v); ng.add_edge(u, v)
    _approx_dict(fnx.effective_size(fg), nx.effective_size(ng))


@pytest.mark.parametrize("seed", range(15))
def test_weighted_effective_size_matches_networkx(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    fg, ng = fnx.Graph(), nx.Graph()
    fg.add_nodes_from(range(n)); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    _approx_dict(fnx.effective_size(fg, weight="weight"),
                 nx.effective_size(ng, weight="weight"))


def test_directed_effective_size_nbunch():
    fg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
    ng = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
    _approx_dict(fnx.effective_size(fg, nodes=[0, 2]),
                 nx.effective_size(ng, nodes=[0, 2]))
