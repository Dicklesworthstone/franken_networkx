"""Parity for bellman_ford negative-cycle error message.

Bead br-r37-c1-wtjho. fnx's bellman_ford_path raised
``NetworkXUnbounded('Negative cost cycle detected.')`` (with 'cost').
nx uses ``'Negative cycle detected.'`` (without 'cost'). Drop-in code
that matches on the exact error message text fails on fnx.

Other bellman_ford paths in fnx already used the correct nx wording;
the Rust _raw_bellman_ford_path and one Python path were the
remaining offenders.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_negative_cycle_graph(lib):
    return lib.DiGraph([(0, 1, {"w": -1}), (1, 0, {"w": -1})])


@needs_nx
def test_bellman_ford_path_negative_cycle_message_matches_networkx():
    G = _make_negative_cycle_graph(fnx)
    GX = _make_negative_cycle_graph(nx)
    with pytest.raises(fnx.NetworkXUnbounded) as fnx_exc:
        fnx.bellman_ford_path(G, 0, 1, weight="w")
    with pytest.raises(nx.NetworkXUnbounded) as nx_exc:
        nx.bellman_ford_path(GX, 0, 1, weight="w")
    assert str(fnx_exc.value) == str(nx_exc.value) == "Negative cycle detected."


@needs_nx
def test_bellman_ford_predecessor_message_matches_networkx():
    G = _make_negative_cycle_graph(fnx)
    GX = _make_negative_cycle_graph(nx)
    with pytest.raises(fnx.NetworkXUnbounded) as fnx_exc:
        fnx.bellman_ford_predecessor_and_distance(G, 0, weight="w")
    with pytest.raises(nx.NetworkXUnbounded) as nx_exc:
        nx.bellman_ford_predecessor_and_distance(GX, 0, weight="w")
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_single_source_bellman_ford_message_matches_networkx():
    G = _make_negative_cycle_graph(fnx)
    GX = _make_negative_cycle_graph(nx)
    with pytest.raises(fnx.NetworkXUnbounded) as fnx_exc:
        list(fnx.single_source_bellman_ford_path(G, 0, weight="w").items())
    with pytest.raises(nx.NetworkXUnbounded) as nx_exc:
        list(nx.single_source_bellman_ford_path(GX, 0, weight="w").items())
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_all_pairs_bellman_ford_message_matches_networkx():
    G = _make_negative_cycle_graph(fnx)
    GX = _make_negative_cycle_graph(nx)
    with pytest.raises(fnx.NetworkXUnbounded) as fnx_exc:
        list(fnx.all_pairs_bellman_ford_path(G, weight="w"))
    with pytest.raises(nx.NetworkXUnbounded) as nx_exc:
        list(nx.all_pairs_bellman_ford_path(GX, weight="w"))
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_bellman_ford_does_not_say_cost_cycle():
    """The exact wording 'Negative cost cycle' must NOT appear."""
    G = _make_negative_cycle_graph(fnx)
    with pytest.raises(fnx.NetworkXUnbounded) as exc:
        fnx.bellman_ford_path(G, 0, 1, weight="w")
    assert "cost cycle" not in str(exc.value)


@needs_nx
def test_bellman_ford_happy_path_unchanged():
    """The fix must not regress the happy path."""
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    assert fnx.bellman_ford_path(G, 0, 4) == nx.bellman_ford_path(GX, 0, 4) == [0, 1, 2, 3, 4]


@needs_nx
def test_bellman_ford_no_negative_cycle_raises_no_path():
    """No path between disconnected components should still raise
    NetworkXNoPath, not Unbounded."""
    G = fnx.DiGraph([(0, 1)])
    G.add_node(2)
    with pytest.raises(fnx.NetworkXNoPath):
        fnx.bellman_ford_path(G, 0, 2)
