"""Edge-case parity for kernel-fast-path wrappers.

Wrappers that return/yield a Rust kernel's result directly can skip the
edge-case handling networkx applies (this is exactly how the xn2ho
disjoint_paths NetworkXNoPath bug arose). This pins the value/exception
contract for several such wrappers on their boundary inputs.

NOTE: current_flow_*/katz_numpy on n<3 graphs are intentionally NOT pinned
here — fnx returns the trivial value while nx crashes with an unhandled
ZeroDivisionError/TypeError; that ambiguous divergence is tracked in bp6wk for
an owner decision rather than locked to either behavior.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _outcome(fn, *args):
    try:
        r = fn(*args)
        if hasattr(r, "__iter__") and not isinstance(r, (str, dict, list, tuple)):
            r = list(r)
        if isinstance(r, float):
            r = round(r, 5)
        return ("ok", r)
    except Exception as exc:  # noqa: BLE001 — exception-type parity is the point
        return ("err", type(exc).__name__)


@pytest.mark.parametrize("builder", [
    lambda L: L.path_graph(2),
    lambda L: L.star_graph(4),
    lambda L: L.path_graph(6),
    lambda L: L.cycle_graph(3),       # not a tree → both raise
    lambda L: L.empty_graph(1),       # single node
])
def test_to_prufer_sequence_edge_cases(builder):
    assert _outcome(fnx.to_prufer_sequence, builder(fnx)) == _outcome(
        nx.to_prufer_sequence, builder(nx)
    )


@pytest.mark.parametrize("edges", [
    [(0, 1), (1, 2)],            # DAG
    [(0, 1), (1, 2), (2, 0)],   # full cycle
    [(0, 1), (1, 0)],           # mutual
    [(0, 0)],                   # self-loop
])
def test_flow_hierarchy_edge_cases(edges):
    assert _outcome(lambda: round(fnx.flow_hierarchy(fnx.DiGraph(edges)), 5)) == (
        _outcome(lambda: round(nx.flow_hierarchy(nx.DiGraph(edges)), 5))
    )


@pytest.mark.parametrize("builder", [
    lambda L: L.path_graph(5),
    lambda L: L.complete_graph(4),
    lambda L: L.cycle_graph(6),
])
def test_hyper_wiener_index_connected(builder):
    assert _outcome(lambda: round(fnx.hyper_wiener_index(builder(fnx)), 5)) == (
        _outcome(lambda: round(nx.hyper_wiener_index(builder(nx)), 5))
    )


def test_hyper_wiener_disconnected_contract():
    fg = fnx.Graph([(0, 1), (2, 3)])
    ng = nx.Graph([(0, 1), (2, 3)])
    assert _outcome(fnx.hyper_wiener_index, fg) == _outcome(nx.hyper_wiener_index, ng)
