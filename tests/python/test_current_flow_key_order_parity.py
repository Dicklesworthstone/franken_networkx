"""Current-flow centrality dicts must be keyed in networkx's order.

br-r37-c1-8n5ni. These kernels permute the graph into reverse Cuthill-McKee
order to make the Laplacian solve cheap. networkx permutes too, but keys its
accumulator off the RELABELED graph (``dict.fromkeys(H)``), whose node order is
``[mapping[v] for v in G]`` — so mapping each key back through ``ordering``
lands in G's node order. fnx built its result with ``for i in range(n)``, i.e.
in RCM rank order, so `list(result)` came out permuted.

Values were never wrong; only the key sequence. That still matters: key order is
observable through iteration, ``list()``, and serialization, and this project
treats it as contract.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

# Chosen so RCM order is NOT the identity — [1, 2, 0, 3] here. On a graph where
# RCM happens to be the identity the bug is invisible.
_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]


def _pair():
    return nx.Graph(_EDGES), fnx.Graph(_EDGES)


def test_fixture_actually_exercises_a_nontrivial_rcm_permutation():
    """Guard the guard: if RCM became the identity this file would prove nothing."""
    _gn, gf = _pair()
    ordering = list(fnx._current_flow_rcm_ordering(gf))
    assert ordering != sorted(ordering), (
        "fixture no longer produces a non-identity RCM ordering, so the tests "
        "below would pass even with the bug reintroduced"
    )


@pytest.mark.parametrize(
    "name", ["current_flow_closeness_centrality", "information_centrality"]
)
def test_current_flow_closeness_key_order_matches_networkx(name):
    gn, gf = _pair()
    expected = getattr(nx, name)(gn)
    actual = getattr(fnx, name)(gf)

    assert list(actual) == list(expected), (
        f"{name} key order diverged from networkx: "
        f"{list(actual)} vs {list(expected)}"
    )
    assert list(actual) == list(gf), f"{name} keys are not in G's node order"
    for node, value in expected.items():
        assert actual[node] == pytest.approx(value)


@pytest.mark.parametrize(
    "name", ["current_flow_closeness_centrality", "information_centrality"]
)
def test_current_flow_closeness_values_are_plain_floats(name):
    """br-r37-c1-cfctype's contract, re-checked through the reordered return."""
    _gn, gf = _pair()
    actual = getattr(fnx, name)(gf)
    assert {type(v) for v in actual.values()} == {float}


def test_current_flow_closeness_key_order_holds_on_relabelled_nodes():
    """String labels, so node order cannot coincide with sorted-integer order."""
    mapping = {0: "delta", 1: "alpha", 2: "charlie", 3: "bravo"}
    gn = nx.relabel_nodes(nx.Graph(_EDGES), mapping, copy=True)
    gf = fnx.relabel_nodes(fnx.Graph(_EDGES), mapping, copy=True)

    expected = nx.current_flow_closeness_centrality(gn)
    actual = fnx.current_flow_closeness_centrality(gf)

    assert list(actual) == list(expected)
    for node, value in expected.items():
        assert actual[node] == pytest.approx(value)


def test_current_flow_betweenness_key_order_still_matches():
    """The sibling that was already correct — it must stay correct."""
    gn, gf = _pair()
    expected = nx.current_flow_betweenness_centrality(gn)
    actual = fnx.current_flow_betweenness_centrality(gf)
    assert list(actual) == list(expected)
    for node, value in expected.items():
        assert actual[node] == pytest.approx(value)


# ``solver="full"`` is the DEFAULT and was the only broken one — it is the
# branch that takes the Rust fast path, while ``lu``/``cg`` fall through to the
# Python implementation and were already correct. Parametrizing over all three
# is what localised the bug, so keep all three.
_SOLVERS = ["full", "lu", "cg"]


@pytest.mark.parametrize("solver", _SOLVERS)
@pytest.mark.parametrize("normalized", [True, False])
def test_edge_current_flow_betweenness_key_order_matches_networkx(solver, normalized):
    gn, gf = _pair()
    expected = nx.edge_current_flow_betweenness_centrality(
        gn, normalized=normalized, solver=solver
    )
    actual = fnx.edge_current_flow_betweenness_centrality(
        gf, normalized=normalized, solver=solver
    )

    assert set(actual) == set(expected), "edge key SET diverged"
    assert list(actual) == list(expected), (
        f"edge key ORDER diverged for solver={solver}: "
        f"{list(actual)} vs {list(expected)}"
    )
    for edge, value in expected.items():
        assert actual[edge] == pytest.approx(value)


@pytest.mark.parametrize(
    "edges",
    [
        pytest.param([(0, 1), (1, 2), (2, 3), (3, 4)], id="path"),
        pytest.param([(0, 1), (0, 2), (0, 3), (0, 4)], id="star"),
        pytest.param([(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)], id="complete"),
        pytest.param(
            [(0, 1), (1, 2), (0, 2), (2, 3), (3, 4), (4, 5), (3, 5)], id="barbell"
        ),
        pytest.param(
            [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("a", "c")], id="strings"
        ),
    ],
)
def test_edge_current_flow_key_order_across_shapes(edges):
    """Different shapes give different RCM orderings — one fixture is not enough."""
    gn = nx.Graph(edges)
    gf = fnx.Graph(edges)
    expected = nx.edge_current_flow_betweenness_centrality(gn)
    actual = fnx.edge_current_flow_betweenness_centrality(gf)
    assert list(actual) == list(expected)
    for edge, value in expected.items():
        assert actual[edge] == pytest.approx(value)
