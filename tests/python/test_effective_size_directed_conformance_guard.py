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


@pytest.mark.skip(
    reason="br-r37-c1-qbj9u: native effective_size_directed_rust diverged from nx "
    "(~0.2/node, fnx 2.6 vs nx 2.8) — caught by the value tests below. The native "
    "directed route was REVERTED to the nx-correct fallback pending a kernel fix. "
    "Re-enable this route-enforcement test once the directed kernel matches nx "
    "(the value tests are the gate; this one only asserts the routing)."
)
def test_directed_effective_size_uses_native_route(monkeypatch):
    fg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
    ng = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])

    def fail_fallback(*args, **kwargs):
        raise AssertionError("directed unweighted effective_size must use native route")

    monkeypatch.setattr(fnx, "_structural_holes_effective_size_matrix", fail_fallback)
    monkeypatch.setattr(fnx, "_call_networkx_submodule_for_parity", fail_fallback)
    _approx_dict(fnx.effective_size(fg), nx.effective_size(ng))
    _approx_dict(fnx.effective_size(fg, nodes=[0, 2]), nx.effective_size(ng, nodes=[0, 2]))


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
