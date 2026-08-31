"""Conformance guard for effective_size on DIRECTED / weighted / self-loop graphs.

effective_size routes the unweighted-undirected-no-selfloop common case to a
native kernel. br-r37-c1-qbj9u adds the same no-delegation native route for
simple unweighted DiGraphs using NetworkX's directed mutual-neighbor semantics;
weighted / self-loop graphs still keep matrix/parity routing.

No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import builtins
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


def test_directed_nodes_none_matches_networkx_optional_scipy_path():
    """nodes=None must match NetworkX with and without optional SciPy installed."""
    # This graph distinguishes NetworkX's optional SciPy matrix path from its loop
    # fallback.  Which answer is correct depends on whether SciPy imports.
    edges = [(1, 0), (2, 0), (2, 3), (3, 0), (3, 1), (3, 2),
             (4, 0), (4, 2), (4, 5), (5, 0), (5, 2), (5, 3)]
    fg, ng = fnx.DiGraph(edges), nx.DiGraph(edges)
    fg.add_nodes_from(range(6))
    ng.add_nodes_from(range(6))

    loop = nx.effective_size(ng, nodes=list(ng))
    # The live NetworkX call selects its matrix route only when optional SciPy is
    # importable; FNX must make the same choice.
    _approx_dict(fnx.effective_size(fg), nx.effective_size(ng))
    _approx_dict(fnx.effective_size(fg, nodes=list(fg)), loop)


def test_directed_nodes_none_without_scipy_uses_networkx_loop(monkeypatch):
    """NetworkX falls back to its loop when its optional SciPy import fails."""
    edges = [(1, 0), (2, 0), (2, 3), (3, 0), (3, 1), (3, 2),
             (4, 0), (4, 2), (4, 5), (5, 0), (5, 2), (5, 3)]
    fg, ng = fnx.DiGraph(edges), nx.DiGraph(edges)
    fg.add_nodes_from(range(6))
    ng.add_nodes_from(range(6))

    original_import = builtins.__import__

    def without_scipy(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "scipy":
            raise ImportError("simulated optional SciPy absence")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", without_scipy)
    _approx_dict(fnx.effective_size(fg), nx.effective_size(ng, nodes=list(ng)))


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
