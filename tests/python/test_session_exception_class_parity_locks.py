"""Regression-lock tests for the exception-class / message-text / return-type
parity fixes landed during the May 2026 systematic-probing session.

Each block below pins a specific nx contract that fnx previously diverged
on — the bead ID in the docstring is the original fix.  Re-breaking any
of these regressions an nx drop-in scenario, so the assertions check
exact class, exact (or regex-matched) message, and structural equality
against nx.
"""

from __future__ import annotations

import collections

import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


# ---------------------------------------------------------------------------
# br-r37-c1-4bkzp / br-r37-c1-smmml — gomory_hu_tree edge shapes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    ["no_edge", "selfloop", "selfloop_with_capacity"],
)
def test_gomory_hu_tree_single_node_matches_networkx(kind):
    """1-node graph is trivially empty regardless of selfloop / capacity attr."""
    fg, ng = fnx.Graph(), nx.Graph()
    fg.add_node(0)
    ng.add_node(0)
    if kind != "no_edge":
        fg.add_edge(0, 0)
        ng.add_edge(0, 0)
    if kind == "selfloop_with_capacity":
        fg.add_edge(0, 0, capacity=5)
        ng.add_edge(0, 0, capacity=5)

    fr = fnx.gomory_hu_tree(fg)
    nr = nx.gomory_hu_tree(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes()) == [0]
    assert sorted(fr.edges()) == sorted(nr.edges()) == []


def test_gomory_hu_tree_isolated_nodes_matches_networkx():
    """Multiple isolated nodes (no edges) -> nx returns star tree with 0-weight edges."""
    fg = fnx.Graph()
    fg.add_nodes_from([0, 1, 2])
    ng = nx.Graph()
    ng.add_nodes_from([0, 1, 2])

    fr = fnx.gomory_hu_tree(fg)
    nr = nx.gomory_hu_tree(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes())
    fr_edges = {(min(u, v), max(u, v), d.get("weight")) for u, v, d in fr.edges(data=True)}
    nr_edges = {(min(u, v), max(u, v), d.get("weight")) for u, v, d in nr.edges(data=True)}
    assert fr_edges == nr_edges


def test_gomory_hu_tree_two_selfloops_disconnected_matches_networkx():
    """Two disconnected selfloop-only nodes -> nx returns a 0-weight edge."""
    fg = fnx.Graph()
    fg.add_edge(0, 0)
    fg.add_edge(1, 1)
    ng = nx.Graph()
    ng.add_edge(0, 0)
    ng.add_edge(1, 1)

    fr = fnx.gomory_hu_tree(fg)
    nr = nx.gomory_hu_tree(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes())
    assert {(min(u, v), max(u, v)) for u, v in fr.edges()} == {
        (min(u, v), max(u, v)) for u, v in nr.edges()
    }


def test_gomory_hu_tree_disconnected_with_explicit_capacities_matches_networkx():
    """Disconnected graph with capacities -> cross-component edge weight 0."""
    fg = fnx.Graph()
    fg.add_edge(0, 1, capacity=5)
    fg.add_edge(2, 3, capacity=5)
    ng = nx.Graph()
    ng.add_edge(0, 1, capacity=5)
    ng.add_edge(2, 3, capacity=5)

    fr = fnx.gomory_hu_tree(fg)
    nr = nx.gomory_hu_tree(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes())
    fr_w = {(min(u, v), max(u, v), float(d.get("weight"))) for u, v, d in fr.edges(data=True)}
    nr_w = {(min(u, v), max(u, v), float(d.get("weight"))) for u, v, d in nr.edges(data=True)}
    assert fr_w == nr_w


# ---------------------------------------------------------------------------
# br-r37-c1-738gg — hyper_wiener_index empty / disconnected
# ---------------------------------------------------------------------------


def test_hyper_wiener_index_empty_raises_pointless_concept():
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.hyper_wiener_index(fnx.Graph())


@pytest.mark.parametrize(
    "kind",
    ["isolated", "two-components", "selfloops-only"],
)
def test_hyper_wiener_index_disconnected_returns_inf(kind):
    fg = fnx.Graph()
    if kind == "isolated":
        fg.add_nodes_from([0, 1, 2])
    elif kind == "two-components":
        fg.add_edges_from([(0, 1), (2, 3)])
    else:
        fg.add_edge(0, 0)
        fg.add_edge(1, 1)
    assert fnx.hyper_wiener_index(fg) == float("inf")


# ---------------------------------------------------------------------------
# br-r37-c1-mgdq0 — modularity_matrix no-edges produces NaN matrix
# ---------------------------------------------------------------------------


def test_modularity_matrix_isolated_nodes_returns_nan_matrix():
    import math

    fg = fnx.Graph()
    fg.add_nodes_from([0, 1, 2])
    result = fnx.modularity_matrix(fg)
    assert result.shape == (3, 3)
    # Every entry is NaN (m=0 divides through)
    assert all(math.isnan(x) for row in result for x in row)


def test_modularity_matrix_empty_raises():
    with pytest.raises(fnx.NetworkXError, match="Graph has no nodes"):
        fnx.modularity_matrix(fnx.Graph())


# ---------------------------------------------------------------------------
# br-r37-c1-kpaki — capacity_scaling empty DiGraph
# ---------------------------------------------------------------------------


def test_capacity_scaling_empty_digraph_returns_zero_dict():
    result = fnx.capacity_scaling(fnx.DiGraph())
    assert result == (0, {})


def test_capacity_scaling_undirected_raises_not_implemented():
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        fnx.capacity_scaling(fnx.Graph())


# ---------------------------------------------------------------------------
# br-r37-c1-53kq4 — eulerize uses unweighted shortest paths
# ---------------------------------------------------------------------------


def test_eulerize_accepts_negative_weight_edges():
    """Eulerize uses BFS (hop count), not weighted distances — negative
    weights should not raise."""
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1, {"weight": -1}), (1, 2, {"weight": -2})])
    ng = nx.Graph()
    ng.add_edges_from([(0, 1, {"weight": -1}), (1, 2, {"weight": -2})])
    fr = fnx.eulerize(fg)
    nr = nx.eulerize(ng)
    assert sorted(fr.edges()) == sorted(nr.edges())


# ---------------------------------------------------------------------------
# br-r37-c1-a8g4v — second_order_centrality raises NetworkXException
# ---------------------------------------------------------------------------


def test_second_order_centrality_negative_weights_raises_network_x_exception():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1, {"weight": -1})])
    with pytest.raises(fnx.NetworkXException, match="negative edge weights"):
        fnx.second_order_centrality(fg)
    # And the type is exactly NetworkXException, not just a subclass like
    # NetworkXError — drop-in callers using `except NetworkXException
    # as e: type(e) is NetworkXException` rely on this.
    try:
        fnx.second_order_centrality(fg)
    except fnx.NetworkXException as exc:
        assert type(exc) is fnx.NetworkXException


# ---------------------------------------------------------------------------
# br-r37-c1-egxmz — stoer_wagner rejects negative edge weights
# ---------------------------------------------------------------------------


def test_stoer_wagner_negative_weight_raises_network_x_error():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1, {"weight": -1}), (1, 2, {"weight": -2})])
    with pytest.raises(fnx.NetworkXError, match=r"negative-weighted edge"):
        fnx.stoer_wagner(fg)


def test_stoer_wagner_zero_weight_still_runs():
    """Zero weights are valid for Stoer-Wagner; only negative weights raise."""
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1, {"weight": 0}), (1, 2, {"weight": 1})])
    cut_value, partition = fnx.stoer_wagner(fg)
    assert cut_value == 0


# ---------------------------------------------------------------------------
# br-r37-c1-3gqao — triads_by_type returns defaultdict(list)
# ---------------------------------------------------------------------------


def test_triads_by_type_is_defaultdict_list():
    g = fnx.DiGraph()
    g.add_edges_from([(0, 1), (1, 2), (2, 0)])
    result = fnx.triads_by_type(g)
    assert isinstance(result, collections.defaultdict)
    assert result.default_factory is list
    # Unknown triad type yields [] (the defining defaultdict behaviour)
    assert result["nonexistent"] == []


# ---------------------------------------------------------------------------
# br-r37-c1-0oasd — connected_double_edge_swap checks connectivity first
# ---------------------------------------------------------------------------


def test_connected_double_edge_swap_isolated_nodes_raises_not_connected():
    """3 isolated nodes -> nx checks is_connected before len(G)<4,
    so the message is 'Graph not connected' rather than the
    fewer-than-four-nodes wording."""
    g = fnx.Graph()
    g.add_nodes_from([0, 1, 2])
    with pytest.raises(fnx.NetworkXError, match="not connected"):
        fnx.connected_double_edge_swap(g)


def test_connected_double_edge_swap_three_path_raises_fewer_than_four():
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NetworkXError, match="fewer than four"):
        fnx.connected_double_edge_swap(g)


# ---------------------------------------------------------------------------
# br-r37-c1-mnziq — per-function multigraph/directed decorator order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func_name",
    [
        # multigraph-first family
        "rich_club_coefficient",
        "is_strongly_regular",
        "modularity_matrix",
        "minimum_cycle_basis",
        "subgraph_centrality",
        "lattice_reference",
        "min_edge_cover",
        "gutman_index",
        "schultz_index",
        "to_graph6_bytes",
    ],
)
def test_multigraph_first_decorator_order_on_multidigraph(func_name):
    """MultiDiGraph triggers BOTH @not_implemented_for guards; for these
    functions nx's decorator stack puts multigraph outermost so the
    'multigraph' message wins."""
    mdg = fnx.MultiDiGraph()
    mdg.add_edges_from([(0, 1), (1, 2)])
    fxo = getattr(fnx, func_name)
    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        fxo(mdg)


@pytest.mark.parametrize(
    "func_name",
    [
        # directed-first family
        "maximal_matching",
        "min_weight_matching",
        "max_weight_matching",
        "local_bridges",
        "generalized_degree",
        "triangles",
    ],
)
def test_directed_first_decorator_order_on_multidigraph(func_name):
    """For these functions nx applies the directed decorator outermost so
    the 'directed' message wins on a MultiDiGraph."""
    mdg = fnx.MultiDiGraph()
    mdg.add_edges_from([(0, 1), (1, 2)])
    fxo = getattr(fnx, func_name)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fxo(mdg)


# ---------------------------------------------------------------------------
# br-r37-c1-of11w — maximal_independent_set nx-shaped selfloop message
# ---------------------------------------------------------------------------


def test_maximal_independent_set_selfloop_message_matches_networkx():
    g = fnx.Graph()
    g.add_edge(0, 0)
    with pytest.raises(fnx.NetworkXUnfeasible, match=r"\{0\} is not an independent set"):
        fnx.maximal_independent_set(g)


# ---------------------------------------------------------------------------
# br-r37-c1-ms5et — generators accept random.Random as seed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func_call",
    [
        lambda s: fnx.newman_watts_strogatz_graph(10, 4, 0.3, seed=s),
        lambda s: fnx.connected_watts_strogatz_graph(10, 4, 0.3, seed=s),
        lambda s: fnx.watts_strogatz_graph(10, 4, 0.3, seed=s),
        lambda s: fnx.gnp_random_graph(10, 0.3, seed=s),
        lambda s: fnx.erdos_renyi_graph(10, 0.3, seed=s),
        lambda s: fnx.barabasi_albert_graph(10, 2, seed=s),
        lambda s: fnx.maximal_independent_set(fnx.path_graph(6), seed=s),
    ],
)
def test_seeded_generators_accept_random_random_instance(func_call):
    """nx accepts seed=random.Random(...) via @py_random_state; fnx must
    not raise on the same call.  Each func is run with a fresh Random."""
    import random

    func_call(random.Random(42))  # must not raise
