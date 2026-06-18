"""Degenerate-input parity for DIRECTED and MULTI graphs.

Complements the undirected degenerate sweep in
``test_degenerate_input_parity.py`` (2zf90), which only builds ``nx.Graph``
shapes. Directed-specific predicates (strong/weak connectivity, reciprocity,
in/out degree) and multigraph parallel-edge handling have their own edge
cases — directed self-loops, single-direction cycles, parallel edges — that
the undirected sweep cannot reach.

No mocks: real fnx and real networkx on hand-built directed / multi graphs.
"""

from __future__ import annotations

import math

import pytest
import networkx as nx
import franken_networkx as fnx


def _di_shapes(mod):
    s = {}
    s["empty"] = mod.DiGraph()
    g = mod.DiGraph(); g.add_node(0); s["single"] = g
    g = mod.DiGraph(); g.add_edge(0, 0); s["self_loop"] = g
    g = mod.DiGraph(); g.add_edge(0, 1); s["one_arc"] = g
    g = mod.DiGraph(); g.add_edges_from([(0, 1), (1, 0)]); s["two_cycle"] = g
    g = mod.DiGraph(); g.add_edges_from([(0, 1), (1, 2), (2, 0)]); s["three_cycle"] = g
    g = mod.DiGraph(); g.add_edges_from([(0, 1), (1, 2)]); s["path"] = g
    g = mod.DiGraph(); g.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 0)]); s["cycle_loop"] = g
    return s


_DI_ALGOS = {
    "is_strongly_connected": (nx.is_strongly_connected, fnx.is_strongly_connected),
    "is_weakly_connected": (nx.is_weakly_connected, fnx.is_weakly_connected),
    "number_strongly_connected_components": (
        nx.number_strongly_connected_components,
        fnx.number_strongly_connected_components,
    ),
    "number_weakly_connected_components": (
        nx.number_weakly_connected_components,
        fnx.number_weakly_connected_components,
    ),
    "is_aperiodic": (nx.is_aperiodic, fnx.is_aperiodic),
    "is_directed_acyclic_graph": (
        nx.is_directed_acyclic_graph, fnx.is_directed_acyclic_graph,
    ),
    "overall_reciprocity": (nx.overall_reciprocity, fnx.overall_reciprocity),
    "in_degree": (lambda G: dict(G.in_degree()), lambda G: dict(G.in_degree())),
    "out_degree": (lambda G: dict(G.out_degree()), lambda G: dict(G.out_degree())),
    "transitivity": (nx.transitivity, fnx.transitivity),
    "pagerank": (nx.pagerank, fnx.pagerank),
}

_NX_DI = _di_shapes(nx)
_FNX_DI = _di_shapes(fnx)
_DI_NAMES = sorted(_NX_DI)


def _normalize(x):
    if isinstance(x, dict):
        return {k: _normalize(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return type(x)(_normalize(v) for v in x)
    if isinstance(x, float):
        return round(x, 7) if math.isfinite(x) else repr(x)
    return x


def _outcome(fn, g):
    try:
        return ("ok", _normalize(fn(g)))
    except Exception as exc:  # noqa: BLE001 — exception-type parity is the point
        return ("err", type(exc).__name__)


@pytest.mark.parametrize("algo", sorted(_DI_ALGOS))
@pytest.mark.parametrize("shape", _DI_NAMES)
def test_directed_degenerate_matches_networkx(algo, shape):
    nx_fn, fnx_fn = _DI_ALGOS[algo]
    assert _outcome(fnx_fn, _FNX_DI[shape]) == _outcome(nx_fn, _NX_DI[shape])


def test_multigraph_parallel_edges_and_self_loops():
    spec = [(0, 1), (0, 1), (1, 2), (2, 2)]
    m = fnx.MultiGraph(spec)
    nm = nx.MultiGraph(spec)
    assert dict(m.degree()) == dict(nm.degree())
    assert m.number_of_edges() == nm.number_of_edges()
    assert m.number_of_edges(0, 1) == nm.number_of_edges(0, 1) == 2
    assert fnx.number_of_selfloops(m) == nx.number_of_selfloops(nm)


def test_multidigraph_parallel_arcs():
    spec = [(0, 1), (0, 1), (1, 0)]
    m = fnx.MultiDiGraph(spec)
    nm = nx.MultiDiGraph(spec)
    assert dict(m.in_degree()) == dict(nm.in_degree())
    assert dict(m.out_degree()) == dict(nm.out_degree())
    assert m.number_of_edges() == nm.number_of_edges() == 3
