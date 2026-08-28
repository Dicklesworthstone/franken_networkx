"""Conformance guard for effective_size on DIRECTED / weighted / self-loop graphs.

effective_size routes the unweighted-undirected-no-selfloop common case to a
native kernel. br-r37-c1-qbj9u adds the same no-delegation native route for
simple unweighted DiGraphs using NetworkX's directed mutual-neighbor semantics;
weighted / self-loop graphs still keep matrix/parity routing.

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


def test_directed_subset_effective_size_uses_native_route(monkeypatch):
    """nodes=<iterable> on a simple unweighted DiGraph must NOT delegate.

    br-r37-c1-qbj9u. networkx serves effective_size two ways and they DISAGREE on
    directed graphs: nodes=None takes a scipy matrix path, nodes=<iterable> takes the
    redundancy loop (50 of 60 random digraphs differ, 31 of them nan-vs-value; 0 of 60
    undirected differ). The native kernel reproduces the LOOP, so it is correct for this
    branch and only this branch.
    """
    fg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
    ng = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])

    def fail_fallback(*args, **kwargs):
        raise AssertionError("directed unweighted effective_size(nodes=...) must use the native route")

    monkeypatch.setattr(fnx, "_structural_holes_effective_size_matrix", fail_fallback)
    monkeypatch.setattr(fnx, "_call_networkx_submodule_for_parity", fail_fallback)
    _approx_dict(fnx.effective_size(fg, nodes=[0, 2]), nx.effective_size(ng, nodes=[0, 2]))
    _approx_dict(fnx.effective_size(fg, nodes=list(fg)), nx.effective_size(ng, nodes=list(ng)))


def test_directed_nodes_none_must_keep_the_matrix_path():
    """And nodes=None must NOT use that kernel, because networkx does not.

    This is the half of the original route-enforcement test that was wrong. Routing
    nodes=None to the native kernel would reproduce networkx's redundancy loop, which is
    not what networkx returns for that call - on this very graph nx gives 2.0 and 2.4 for
    nodes 2 and 3 via its matrix path, and 1.8 and 2.2 via its loop.
    """
    # A graph where networkx's two paths demonstrably disagree. The 5-edge graph used
    # above is NOT one - they agree there - which is why this uses its own fixture.
    edges = [(1, 0), (2, 0), (2, 3), (3, 0), (3, 1), (3, 2),
             (4, 0), (4, 2), (4, 5), (5, 0), (5, 2), (5, 3)]
    fg, ng = fnx.DiGraph(edges), nx.DiGraph(edges)
    fg.add_nodes_from(range(6))
    ng.add_nodes_from(range(6))

    default = nx.effective_size(ng)
    loop = nx.effective_size(ng, nodes=list(ng))
    assert abs(default[2] - loop[2]) > 1e-9, (
        "networkx's two paths agree here now; re-derive which kernel this branch needs"
    )
    # fnx must follow the DEFAULT (matrix) answer for nodes=None ...
    _approx_dict(fnx.effective_size(fg), default)
    # ... and the LOOP answer once nodes is given, on the same graph.
    _approx_dict(fnx.effective_size(fg, nodes=list(fg)), loop)


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
