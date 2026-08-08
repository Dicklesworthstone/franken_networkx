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


# br-r37-c1-p4uxw: the DEGENERATE boundaries. The class this module guards is a
# wrapper handing back a kernel result without networkx's edge-case handling —
# and the inputs where that handling exists at all are the null graph, the
# edgeless graph, and the single node. Those were the cases not covered: every
# fixture above has at least two nodes and at least one edge, except
# empty_graph(1). Each case below was verified to agree with networkx before
# being asserted; the outcomes are recorded in the ids so a future divergence
# shows which contract moved.
@pytest.mark.parametrize(
    "name,builder",
    [
        ("null_graph", lambda L: L.empty_graph(0)),  # NetworkXPointlessConcept
        ("two_isolates", lambda L: L.empty_graph(2)),  # NotATree
        ("single_node", lambda L: L.path_graph(1)),  # NetworkXPointlessConcept
        ("smallest_real_tree", lambda L: L.path_graph(3)),  # -> [1]
        ("forest_two_components", lambda L: L.Graph([(0, 1), (2, 3)])),  # NotATree
    ],
)
def test_to_prufer_sequence_degenerate_boundaries(name, builder):
    assert _outcome(fnx.to_prufer_sequence, builder(fnx)) == _outcome(
        nx.to_prufer_sequence, builder(nx)
    )


@pytest.mark.parametrize(
    "name,build_edges",
    [
        ("empty_digraph", []),  # NetworkXError, not a ZeroDivisionError
        ("self_loop_only", [(0, 0)]),
        ("two_self_loops", [(0, 0), (1, 1)]),
    ],
)
def test_flow_hierarchy_degenerate_boundaries(name, build_edges):
    """An edgeless digraph is the division-by-zero shape for this metric; both
    libraries must raise the same thing rather than one returning a value."""
    assert _outcome(lambda: fnx.flow_hierarchy(fnx.DiGraph(build_edges))) == (
        _outcome(lambda: nx.flow_hierarchy(nx.DiGraph(build_edges)))
    )


def test_flow_hierarchy_single_node_no_edges():
    def build(lib):
        g = lib.DiGraph()
        g.add_node(0)
        return g

    assert _outcome(lambda: fnx.flow_hierarchy(build(fnx))) == (
        _outcome(lambda: nx.flow_hierarchy(build(nx)))
    )


@pytest.mark.parametrize(
    "name,builder",
    [
        ("null_graph", lambda L: L.empty_graph(0)),  # NetworkXPointlessConcept
        ("single_node", lambda L: L.empty_graph(1)),  # 0.0
        ("three_isolates", lambda L: L.empty_graph(3)),  # inf, not an exception
    ],
)
def test_hyper_wiener_degenerate_boundaries(name, builder):
    assert _outcome(fnx.hyper_wiener_index, builder(fnx)) == _outcome(
        nx.hyper_wiener_index, builder(nx)
    )


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path6", lambda L: L.path_graph(6)),
        ("star4", lambda L: L.star_graph(4)),
        ("path3", lambda L: L.path_graph(3)),
        ("balanced_tree", lambda L: L.balanced_tree(2, 2)),
    ],
)
def test_prufer_roundtrip_recovers_the_tree(name, builder):
    """br-r37-c1-p4uxw: the sequence was only ever compared to networkx's. That
    catches a divergence but not a codec that is self-consistently wrong in both
    directions. Decoding is the oracle-free check: from_prufer_sequence must
    rebuild the original tree, and must agree with networkx's decode in edge
    order too.
    """
    g = builder(fnx)
    seq = fnx.to_prufer_sequence(g)
    back = fnx.from_prufer_sequence(seq)
    assert sorted(tuple(sorted(e)) for e in back.edges()) == sorted(
        tuple(sorted(e)) for e in g.edges()
    )
    nback = nx.from_prufer_sequence(nx.to_prufer_sequence(builder(nx)))
    assert list(back.edges()) == list(nback.edges())
