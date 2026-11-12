"""Minimum-cut family: size parity + cut-validity invariant + nx contract.

The minimum node/edge cut has a well-defined SIZE (multiple cuts of that size
may exist, so the node set itself can tie-break differently) and must actually
DISCONNECT the graph when removed. Stoer-Wagner's global min-cut value is
order-invariant. Complete graphs have no node cut — both libraries raise. This
checks the size against networkx, verifies the cut is valid, and pins the
exception contract.

No mocks: real fnx and real networkx on structured edge-case graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _structured(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    kind = r.choice(["complete", "disconnected", "random", "star", "cycle"])
    if kind == "complete":
        edges = [(u, v) for u in range(n) for v in range(u + 1, n)]
    elif kind == "disconnected":
        edges = [
            (u, v) for u in range(n) for v in range(u + 1, n)
            if (u < n // 2) == (v < n // 2) and r.random() < 0.6
        ]
    elif kind == "star":
        edges = [(0, i) for i in range(1, n)]
    elif kind == "cycle":
        edges = [(i, (i + 1) % n) for i in range(n)]
    else:
        edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, kind


@pytest.mark.parametrize("seed", range(50))
def test_min_cut_size_parity_and_validity(seed):
    fg, ng, n, kind = _structured(seed)

    # minimum_node_cut: complete graphs have none (both raise NetworkXError).
    try:
        f_cut = fnx.minimum_node_cut(fg)
        f_err = None
    except Exception as exc:  # noqa: BLE001
        f_cut, f_err = None, type(exc).__name__
    try:
        n_cut = nx.minimum_node_cut(ng)
        n_err = None
    except Exception as exc:  # noqa: BLE001
        n_cut, n_err = None, type(exc).__name__

    assert (f_err is None) == (n_err is None)
    if f_err is None:
        # Same cut SIZE (the node set may tie-break differently).
        assert len(f_cut) == len(n_cut)
        # The cut is valid: removing it disconnects the graph (or empties it).
        h = fg.copy()
        h.remove_nodes_from(f_cut)
        assert h.number_of_nodes() <= 1 or not fnx.is_connected(h)


@pytest.mark.parametrize("seed", range(50))
def test_min_edge_cut_and_stoer_wagner(seed):
    fg, ng, n, kind = _structured(seed)
    if fg.number_of_edges() == 0 or not fnx.is_connected(fg):
        pytest.skip("trivial / disconnected")

    f_ec = fnx.minimum_edge_cut(fg)
    n_ec = nx.minimum_edge_cut(ng)
    assert len(f_ec) == len(n_ec)
    # Removing the edge cut disconnects the graph.
    h = fg.copy()
    h.remove_edges_from(f_ec)
    assert not fnx.is_connected(h)

    # Stoer-Wagner global min-cut value matches networkx.
    assert fnx.stoer_wagner(fg)[0] == nx.stoer_wagner(ng)[0]
    # And equals the edge-connectivity (min cut value = lambda).
    assert fnx.stoer_wagner(fg)[0] == len(f_ec)


@pytest.mark.parametrize("seed", range(50))
def test_stoer_wagner_partition_is_valid(seed):
    """stoer_wagner returns (value, partition) and the file reads only [0].

    The partition is half the answer: it is the witness that the value is
    achievable. Nothing checked it covered the graph, that the two sides were
    disjoint and non-empty, or that the edges crossing it actually number the
    reported value.
    """
    fg, _, _, _ = _structured(seed)
    if fg.number_of_edges() == 0 or not fnx.is_connected(fg):
        pytest.skip("trivial / disconnected")

    value, (left, right) = fnx.stoer_wagner(fg)
    left_side, right_side = set(left), set(right)

    assert left_side | right_side == set(fg.nodes())      # covers the graph
    assert not (left_side & right_side)                   # ...disjointly
    assert left_side and right_side                       # a cut needs two sides
    # The reported value IS the number of edges crossing the partition.
    crossing = sum(1 for u, v in fg.edges() if (u in left_side) != (v in left_side))
    assert crossing == value


@pytest.mark.parametrize("seed", range(50))
def test_cuts_are_made_of_graph_elements(seed):
    """A cut that disconnects the graph could still name things not in it.

    Removing nodes or edges that G does not have is a no-op, so a cut padded
    with foreign elements still disconnects and still has the right size.
    """
    fg, _, _, _ = _structured(seed)

    try:
        node_cut = fnx.minimum_node_cut(fg)
    except Exception:  # noqa: BLE001 - complete/disconnected graphs have none
        node_cut = None
    if node_cut is not None:
        assert set(node_cut) <= set(fg.nodes())

    if fg.number_of_edges() and fnx.is_connected(fg):
        for u, v in fnx.minimum_edge_cut(fg):
            assert fg.has_edge(u, v)
