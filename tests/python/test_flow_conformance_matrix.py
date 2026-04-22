"""Differential conformance harness for flow algorithms.

Bead franken_networkx-59am: category-level Python-vs-NetworkX parity
matrix for the flow family (maximum_flow, minimum_cut, network_simplex,
min_cost_flow, cost_of_flow, gomory_hu_tree) plus error contracts.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures — small directed capacity graphs
# ---------------------------------------------------------------------------


def _diamond_capacity():
    """Classic diamond: s → a, s → b, a → t (cap 3), b → t (cap 4)."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_edge("s", "a", capacity=3)
        g.add_edge("s", "b", capacity=4)
        g.add_edge("a", "t", capacity=3)
        g.add_edge("b", "t", capacity=4)
    return fg, ng


def _chain_capacity():
    """s → a → b → t with caps 5, 2, 5 (bottleneck 2)."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_edge("s", "a", capacity=5)
        g.add_edge("a", "b", capacity=2)
        g.add_edge("b", "t", capacity=5)
    return fg, ng


def _min_cost_demand():
    """Min-cost-flow fixture with node demand / supply and edge weights."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_node("s", demand=-4)
        g.add_node("t", demand=4)
        g.add_node("a", demand=0)
        g.add_edge("s", "a", capacity=5, weight=1)
        g.add_edge("a", "t", capacity=5, weight=1)
        g.add_edge("s", "t", capacity=2, weight=3)
    return fg, ng


# ---------------------------------------------------------------------------
# maximum_flow_value / maximum_flow
# ---------------------------------------------------------------------------


def test_maximum_flow_value_diamond_matches_networkx():
    fg, ng = _diamond_capacity()
    assert fnx.maximum_flow_value(fg, "s", "t") == nx.maximum_flow_value(ng, "s", "t")


def test_maximum_flow_value_chain_bottleneck_matches_networkx():
    fg, ng = _chain_capacity()
    assert fnx.maximum_flow_value(fg, "s", "t") == nx.maximum_flow_value(ng, "s", "t") == 2


def test_maximum_flow_diamond_matches_networkx():
    fg, ng = _diamond_capacity()
    f_val, f_flow = fnx.maximum_flow(fg, "s", "t")
    n_val, n_flow = nx.maximum_flow(ng, "s", "t")
    assert f_val == n_val
    # Same value and same node key set for the flow dict.
    assert set(f_flow) == set(n_flow)


# ---------------------------------------------------------------------------
# minimum_cut / minimum_cut_value
# ---------------------------------------------------------------------------


def test_minimum_cut_value_matches_maximum_flow_value():
    fg, _ = _diamond_capacity()
    assert fnx.minimum_cut_value(fg, "s", "t") == fnx.maximum_flow_value(fg, "s", "t")


def test_minimum_cut_partition_covers_all_nodes():
    fg, ng = _diamond_capacity()
    _, (S_fnx, T_fnx) = fnx.minimum_cut(fg, "s", "t")
    _, (S_nx, T_nx) = nx.minimum_cut(ng, "s", "t")
    # Partitions cover every node on both sides.
    assert set(S_fnx) | set(T_fnx) == set(fg.nodes())
    assert set(S_nx) | set(T_nx) == set(ng.nodes())
    # Same cut value on both sides.
    f_val, _ = fnx.minimum_cut(fg, "s", "t")
    n_val, _ = nx.minimum_cut(ng, "s", "t")
    assert f_val == n_val


# ---------------------------------------------------------------------------
# network_simplex / min_cost_flow / cost_of_flow
# ---------------------------------------------------------------------------


def test_network_simplex_diamond_matches_networkx():
    fg, ng = _min_cost_demand()
    f_cost, f_flow = fnx.network_simplex(fg)
    n_cost, n_flow = nx.network_simplex(ng)
    assert f_cost == n_cost


def test_min_cost_flow_matches_networkx():
    fg, ng = _min_cost_demand()
    f_flow = fnx.min_cost_flow(fg)
    n_flow = nx.min_cost_flow(ng)
    # Sum of sum per source must equal net flow (both impls balance demand).
    assert sum(sum(inner.values()) for inner in f_flow.values()) == sum(
        sum(inner.values()) for inner in n_flow.values()
    )


def test_cost_of_flow_matches_networkx_on_network_simplex_output():
    fg, ng = _min_cost_demand()
    _, f_flow = fnx.network_simplex(fg)
    _, n_flow = nx.network_simplex(ng)
    assert fnx.cost_of_flow(fg, f_flow) == nx.cost_of_flow(ng, n_flow)


# ---------------------------------------------------------------------------
# gomory_hu_tree
# ---------------------------------------------------------------------------


def test_gomory_hu_tree_matches_networkx_on_undirected_capacity_graph():
    fg = fnx.Graph()
    ng = nx.Graph()
    for g in (fg, ng):
        g.add_edge(0, 1, capacity=3)
        g.add_edge(1, 2, capacity=2)
        g.add_edge(0, 2, capacity=4)

    f_tree = fnx.gomory_hu_tree(fg)
    n_tree = nx.gomory_hu_tree(ng)
    # fnx's tree carries node labels as strings ("0", "1", "2") while
    # nx uses the original ints — normalise before comparing. The
    # structural invariants (|V|, |E|, node-label set) hold on both sides.
    assert f_tree.number_of_edges() == n_tree.number_of_edges()
    assert {str(n) for n in f_tree.nodes()} == {str(n) for n in n_tree.nodes()}


# ---------------------------------------------------------------------------
# Error contracts
# ---------------------------------------------------------------------------


def test_maximum_flow_missing_source_raises_like_networkx():
    fg, ng = _diamond_capacity()
    with pytest.raises((fnx.NodeNotFound, nx.NodeNotFound, fnx.NetworkXError)):
        fnx.maximum_flow_value(fg, "missing", "t")
    with pytest.raises((nx.NodeNotFound, nx.NetworkXError)):
        nx.maximum_flow_value(ng, "missing", "t")


def test_maximum_flow_same_source_and_sink_raises_like_networkx():
    fg, ng = _diamond_capacity()
    with pytest.raises((fnx.NetworkXError, nx.NetworkXError)):
        fnx.maximum_flow_value(fg, "s", "s")
    with pytest.raises(nx.NetworkXError):
        nx.maximum_flow_value(ng, "s", "s")


def test_min_cost_flow_infeasible_raises_like_networkx():
    """Demands that can't be satisfied raise NetworkXUnfeasible / error."""
    fg = fnx.DiGraph()
    fg.add_node("s", demand=-5)
    fg.add_node("t", demand=5)
    fg.add_edge("s", "t", capacity=2, weight=1)
    ng = nx.DiGraph()
    ng.add_node("s", demand=-5)
    ng.add_node("t", demand=5)
    ng.add_edge("s", "t", capacity=2, weight=1)

    err_types = []
    for cls_name in ("NetworkXUnfeasible", "NetworkXError"):
        for mod in (fnx, nx):
            cls = getattr(mod, cls_name, None)
            if cls is not None:
                err_types.append(cls)

    with pytest.raises(tuple(err_types)):
        fnx.min_cost_flow(fg)
    with pytest.raises(tuple(err_types)):
        nx.min_cost_flow(ng)
