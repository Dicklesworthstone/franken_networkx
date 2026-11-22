"""Parity tests for k_edge_augmentation (bead 049)."""
from decimal import Decimal
from fractions import Fraction
import random
from unittest import mock

import franken_networkx as fnx
import networkx as nx
import pytest


class TestKEdgeAugmentation:
    """Verify k_edge_augmentation matches NetworkX behavior."""

    def test_k0_raises_value_error(self):
        # br-r37-c1-keaug-k0: nx raises ValueError("k must be a
        # positive integer, not 0"); fnx previously returned [].
        # Updated to match nx contract.
        import pytest
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3)])
        with pytest.raises(ValueError, match=r"k must be a positive integer, not 0"):
            fnx.k_edge_augmentation(G, 0)

    def test_float_k_matches_nx(self):
        """br-r37-c1-nyh42: nx compares positive float ``k`` values
        directly; fnx previously routed them through integer-only
        native connectivity checks and raised TypeError."""
        G = fnx.path_graph(5)
        nG = nx.path_graph(5)
        for k in (2.0, 2.5, 3.0):
            assert sorted(fnx.k_edge_augmentation(G, k)) == sorted(
                nx.k_edge_augmentation(nG, k)
            )

    def test_nonpositive_float_k_error_message_matches_nx(self):
        G = fnx.path_graph(5)
        with pytest.raises(
            ValueError,
            match=r"k must be a positive integer, not 0\.0",
        ):
            fnx.k_edge_augmentation(G, 0.0)

    def test_avail_endpoint_not_in_graph_raises_keyerror_like_nx(self):
        """NetworkX validates candidate endpoints even when the graph
        already satisfies k=1.  fnx previously returned [] on the
        fast path or leaked NodeNotFound from local connectivity.
        """
        cases = [
            (1, [(0, 3)], False),
            (2, [(0, 3), (1, 2)], False),
            (2, {(0, 3): 1, (1, 2): 2}, True),
        ]
        for k, avail, partial in cases:
            G = fnx.path_graph(3)
            nG = nx.path_graph(3)
            with pytest.raises(KeyError) as fnx_exc:
                fnx.k_edge_augmentation(G, k, avail=avail, partial=partial)
            with pytest.raises(KeyError) as nx_exc:
                list(nx.k_edge_augmentation(nG, k, avail=avail, partial=partial))
            assert fnx_exc.value.args == nx_exc.value.args == (3,)

    def test_k1_already_connected(self):
        G = fnx.complete_graph(4)
        assert fnx.k_edge_augmentation(G, 1) == []

    def test_k1_disconnected_components(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3), (4, 5)])
        aug = fnx.k_edge_augmentation(G, 1)
        assert len(aug) == 2  # need 2 edges to connect 3 components
        H = G.copy()
        for u, v in aug:
            H.add_edge(u, v)
        assert fnx.is_connected(H)

    def test_k2_bridge_graph(self):
        """Graph with a bridge: augmentation should eliminate it."""
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])
        aug = fnx.k_edge_augmentation(G, 2)
        # Both should produce valid augmentations
        H = G.copy()
        for u, v in aug:
            H.add_edge(u, v)
        assert fnx.edge_connectivity(H) >= 2.0

    def test_k2_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])
        nG = nx.Graph(G.edges())
        aug = fnx.k_edge_augmentation(G, 2)
        naug = list(nx.k_edge_augmentation(nG, 2))
        assert sorted(aug) == sorted(naug)

    def test_k3_cycle_graph(self):
        """C6 has edge connectivity 2; augment to 3."""
        G = fnx.cycle_graph(6)
        nG = nx.cycle_graph(6)
        aug = fnx.k_edge_augmentation(G, 3)
        naug = list(nx.k_edge_augmentation(nG, 3))
        # Verify result achieves k=3
        H = G.copy()
        for u, v in aug:
            H.add_edge(u, v)
        assert fnx.edge_connectivity(H) >= 3.0
        # Same edge set as NX
        assert sorted(aug) == sorted(naug)

    def test_weighted_k1_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = [(1, 5, {"weight": 11}), (2, 5, {"weight": 10})]

        aug = fnx.k_edge_augmentation(G, 1, avail=avail, weight="weight")
        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        naug = list(nx.k_edge_augmentation(nG, 1, avail=avail, weight="weight"))

        assert aug == naug

    def test_weighted_k2_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = [(1, 5, 11), (2, 5, 10), (4, 3, 1), (4, 5, 51)]

        aug = fnx.k_edge_augmentation(G, 2, avail=avail)
        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        naug = list(nx.k_edge_augmentation(nG, 2, avail=avail))

        assert sorted(aug) == sorted(naug)

    def test_partial_k2_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = {(1, 5): 11}

        aug = fnx.k_edge_augmentation(G, 2, avail=avail, partial=True)
        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        naug = list(nx.k_edge_augmentation(nG, 2, avail=avail, partial=True))

        assert sorted(aug) == sorted(naug)

    def test_nontrivial_paths_do_not_call_to_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = [(1, 5, 11), (2, 5, 10), (4, 3, 1), (4, 5, 51)]

        with mock.patch(
            "franken_networkx.drawing.layout._to_nx",
            side_effect=AssertionError("_to_nx fallback should not be used"),
        ), mock.patch(
            "networkx.k_edge_augmentation",
            side_effect=AssertionError("networkx fallback should not be used"),
        ):
            aug = fnx.k_edge_augmentation(G, 2, avail=avail)

        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        assert sorted(aug) == sorted(nx.k_edge_augmentation(nG, 2, avail=avail))

    def test_k_already_satisfied(self):
        """K5 has edge connectivity 4; k=3 should return empty."""
        G = fnx.complete_graph(5)
        assert fnx.k_edge_augmentation(G, 3) == []

    def test_augmented_graph_is_k_connected(self):
        """Generic verification: after augmentation, connectivity >= k."""
        G = fnx.path_graph(8)
        for k in [1, 2, 3]:
            aug = fnx.k_edge_augmentation(G, k)
            H = G.copy()
            for u, v in aug:
                H.add_edge(u, v)
            conn = fnx.edge_connectivity(H)
            assert conn >= k, f"k={k}: expected conn>={k}, got {conn}"


# br-r37-c1-squi9: with avail=None networkx never reads weight - its k=1 and
# k=2 answers are the unconstrained augmentations - but fnx's fast paths were
# gated on weight is None too, so weight= sent it to the greedy search: other
# edges, and at k=2 more of them than networkx's minimum.
def _keaug_shape(lib, shape):
    g = lib.Graph()
    if shape == "ring_component_isolated":
        g.add_weighted_edges_from([(i, (i + 1) % 12, float(i % 5) + 1.5) for i in range(12)])
        g.add_weighted_edges_from([(20, 21, 1.0)])
        g.add_nodes_from([100, 101])
    elif shape == "bridged_triangles":
        g.add_weighted_edges_from([(0, 1, 2), (1, 2, 3), (2, 0, 1), (2, 3, 5), (3, 4, 1), (4, 5, 2), (5, 3, 4)])
    else:  # weighted path
        g.add_weighted_edges_from([(i, i + 1, 0.5 * i + 1) for i in range(7)])
    return g


@pytest.mark.parametrize("shape", ["ring_component_isolated", "bridged_triangles", "path"])
@pytest.mark.parametrize("k", [1, 2, 3])
@pytest.mark.parametrize("weight", [None, "weight", "missing"])
def test_weight_without_avail_matches_networkx(shape, k, weight):
    expected = list(nx.k_edge_augmentation(_keaug_shape(nx, shape), k, weight=weight))
    got = list(fnx.k_edge_augmentation(_keaug_shape(fnx, shape), k, weight=weight))
    assert got == expected


def _constrained_one_augmentation(graph, route, avail, *, partial=False, weight=None):
    if route == "backend":
        return list(nx.k_edge_augmentation(
            graph, 1, avail=avail, weight=weight, partial=partial,
            backend="franken_networkx",
        ))
    supplied = fnx.Graph(graph) if route == "native" else graph
    return list(fnx.k_edge_augmentation(
        supplied, 1, avail=avail, weight=weight, partial=partial,
    ))


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
def test_constrained_k1_accepts_unordered_node_labels(route):
    # Costs tie across distinct component pairs. The spanning calculation
    # must not compare these labels just to choose a component link.
    labels = [0, "left", ("tuple", 1), frozenset({"right"})]
    graph = nx.Graph()
    graph.add_nodes_from(labels)
    avail = [(labels[i], labels[j], 1) for i in range(4) for j in range(i + 1, 4)]
    expected = list(nx.k_edge_augmentation(graph, 1, avail=avail))
    actual = _constrained_one_augmentation(graph, route, avail)
    assert actual == expected
    graph.add_edges_from(actual)
    assert nx.is_connected(graph)
    assert len(actual) == len(labels) - 1


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("costs", [
    (2**100 + 1, 2**100, 2**100 + 3),
    (Fraction(1, 3) + Fraction(1, 2**100), Fraction(1, 3), Fraction(2, 3)),
    (Decimal("0.1000000000000000000001"), Decimal("0.1"), Decimal("0.2")),
], ids=["wide-int", "fraction", "decimal"])
@pytest.mark.parametrize("encoding", ["tuples", "mapping", "attributes"])
def test_constrained_k1_preserves_exact_candidate_costs(route, costs, encoding):
    graph = nx.Graph([(0, 1), (2, 3)])
    graph.add_node(4)
    high, low, last = costs
    edges = [(0, 2), (1, 3), (3, 4)]
    values = [high, low, last]
    if encoding == "mapping":
        avail = dict(zip(edges, values))
    elif encoding == "attributes":
        avail = [(u, v, {"cost": value}) for (u, v), value in zip(edges, values)]
    else:
        avail = [(u, v, value) for (u, v), value in zip(edges, values)]
    expected = list(nx.k_edge_augmentation(graph, 1, avail=avail, weight="cost"))
    actual = _constrained_one_augmentation(graph, route, avail, weight="cost")
    assert actual == expected == [(1, 3), (3, 4)]
    assert list(graph.edges()) == [(0, 1), (2, 3)]


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
def test_infeasible_partial_k1_omits_expensive_redundant_candidates(route):
    graph = nx.empty_graph(5)
    avail = [(0, 1, 9), (1, 2, 2), (0, 2, 1), (3, 4, 4)]
    expected = list(nx.k_edge_augmentation(graph, 1, avail=avail, partial=True))
    actual = _constrained_one_augmentation(graph, route, avail, partial=True)
    assert actual == expected == [(0, 2), (1, 2), (3, 4)]
    cost = {(u, v): value for u, v, value in avail}
    assert sum(cost[edge] for edge in actual) == 7
    graph.add_edges_from(actual)
    assert list(nx.connected_components(graph)) == [{0, 1, 2}, {3, 4}]


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
def test_constrained_k1_infeasibility_keeps_graph_unchanged(route):
    graph = nx.empty_graph(5)
    avail = [(0, 1, 9), (1, 2, 2), (0, 2, 1), (3, 4, 4)]
    with pytest.raises(nx.NetworkXUnfeasible) as expected:
        list(nx.k_edge_augmentation(graph, 1, avail=avail))
    with pytest.raises(nx.NetworkXUnfeasible) as actual:
        _constrained_one_augmentation(graph, route, avail)
    assert actual.value.args == expected.value.args
    assert graph.number_of_edges() == 0


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("nodes,edges,avail", [
    (list(range(4)), [], [(2, 3, 1), (1, 3, 1), (0, 2, 1), (0, 1, 1), (1, 2, 1), (0, 3, 1)]),
    (list(range(4)), [(0, 1), (2, 3)], [(1, 3, 1), (0, 2, 1), (3, 0, 1)]),
    (list(range(4)), [(0, 1), (2, 3)], [(1, 3, 5), (3, 0, 1), (0, 2, 1)]),
    (list(range(4)), [], [(0, 1, 4), (0, 2, 2), (0, 3, 1), (1, 2, 3), (2, 3, 9)]),
    (list(range(3)), [(0, 1)], [(0, 0, -10), (0, 1, -5), (1, 2, 2), (0, 2, 9)]),
])
def test_constrained_k1_preserves_ties_orientation_and_edge_order(route, nodes, edges, avail):
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    expected = list(nx.k_edge_augmentation(graph, 1, avail=avail))
    assert _constrained_one_augmentation(graph, route, avail) == expected


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("cost", [None, float("nan")])
def test_constrained_k1_rejects_invalid_candidate_costs(route, cost):
    graph = nx.empty_graph(3)
    avail = [(0, 1, cost), (1, 2, 2)]
    with pytest.raises(Exception) as expected:
        list(nx.k_edge_augmentation(graph, 1, avail=avail))
    with pytest.raises(type(expected.value)) as actual:
        _constrained_one_augmentation(graph, route, avail)
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("partial", [False, True])
def test_constrained_k1_random_component_forests_match_networkx(seed, partial):
    rng = random.Random(seed)
    graph = nx.Graph()
    graph.add_nodes_from(rng.sample(range(12), 12))
    graph.add_edges_from((node, node + 1) for node in range(0, 8, 2))
    avail = [(u, v, rng.randrange(1, 8)) for u, v in nx.non_edges(graph) if rng.random() < 0.3]
    rng.shuffle(avail)
    try:
        expected = list(nx.k_edge_augmentation(graph, 1, avail=avail, partial=partial))
    except nx.NetworkXUnfeasible as exc:
        with pytest.raises(nx.NetworkXUnfeasible) as actual:
            _constrained_one_augmentation(graph, "native", avail, partial=partial)
        assert actual.value.args == exc.args
    else:
        assert _constrained_one_augmentation(graph, "native", avail, partial=partial) == expected


def _constrained_two_augmentation(graph, route, avail, *, partial=False, weight=None):
    if route == "backend":
        return list(nx.k_edge_augmentation(
            graph, 2, avail=avail, weight=weight, partial=partial,
            backend="franken_networkx",
        ))
    supplied = fnx.Graph(graph) if route == "native" else graph
    return list(fnx.k_edge_augmentation(
        supplied, 2, avail=avail, weight=weight, partial=partial,
    ))


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("encoding", ["tuples", "mapping", "attributes"])
def test_constrained_k2_omits_redundant_cheaper_links(route, encoding):
    graph = nx.path_graph(5)
    graph[0][1]["weight"] = 17
    choices = [(0, 2, 1), (0, 4, 2)]
    if encoding == "mapping":
        avail = {(u, v): cost for u, v, cost in choices}
    elif encoding == "attributes":
        avail = [(u, v, {"cost": cost}) for u, v, cost in choices]
    else:
        avail = choices
    before = list(graph.edges(data=True))
    expected = list(nx.k_edge_augmentation(graph, 2, avail=avail, weight="cost"))
    actual = _constrained_two_augmentation(graph, route, avail, weight="cost")
    assert actual == expected == [(0, 4)]
    assert list(graph.edges(data=True)) == before
    graph.add_edges_from(actual)
    assert nx.is_k_edge_connected(graph, 2)


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
def test_constrained_k2_accepts_unordered_candidate_labels(route):
    labels = [0, "branch", (2,), frozenset({3}), "tip"]
    graph = nx.path_graph(labels)
    avail = [
        (labels[0], labels[2], 1),
        (labels[1], labels[4], 1),
        (labels[0], labels[4], 2),
    ]
    expected = list(nx.k_edge_augmentation(graph, 2, avail=avail))
    actual = _constrained_two_augmentation(graph, route, avail)
    assert actual == expected
    graph.add_edges_from(actual)
    assert nx.is_k_edge_connected(graph, 2)


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("encoding", ["pairs", "mapping"])
def test_partial_k2_optimizes_feasible_blocks_and_retains_crossing_links(route, encoding):
    graph = nx.path_graph(7)
    graph.add_node(7)
    candidates = {
        (0, 2): 1, (0, 3): 2, (0, 4): 3, (1, 3): 4,
        (1, 4): 2, (2, 4): 1, (0, 7): 5,
    }
    avail = list(candidates) if encoding == "pairs" else candidates
    expected = list(nx.k_edge_augmentation(graph, 2, avail=avail, partial=True))
    actual = _constrained_two_augmentation(graph, route, avail, partial=True)
    assert actual == expected
    assert (0, 7) in actual
    assert len(actual) < len(avail)
    assert list(graph.edges()) == [(node, node + 1) for node in range(6)]
    augmented = graph.copy()
    augmented.add_edges_from(actual)
    assert nx.is_k_edge_connected(augmented.subgraph(range(5)), 2)
    assert set(nx.bridges(augmented)) == {(0, 7), (4, 5), (5, 6)}


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
def test_constrained_k2_infeasibility_preserves_reference_error(route):
    graph = nx.path_graph(5)
    avail = {(0, 2): 1}
    with pytest.raises(nx.NetworkXUnfeasible) as expected:
        list(nx.k_edge_augmentation(graph, 2, avail=avail))
    with pytest.raises(nx.NetworkXUnfeasible) as actual:
        _constrained_two_augmentation(graph, route, avail)
    assert actual.value.args == expected.value.args
    assert list(graph.edges()) == [(node, node + 1) for node in range(4)]


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("count,avail", [(0, {}), (1, {}), (2, {}), (2, {(0, 1): 7})])
def test_partial_k2_small_graphs_respect_available_edges(route, count, avail):
    graph = nx.empty_graph(count)
    expected = list(nx.k_edge_augmentation(graph, 2, avail=avail, partial=True))
    actual = _constrained_two_augmentation(graph, route, avail, partial=True)
    assert actual == expected
    assert all(edge in avail for edge in actual)
    assert graph.number_of_edges() == 0


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("count", [2, 5])
def test_partial_k2_preserves_reference_raw_pair_errors(route, count):
    graph = nx.empty_graph(2) if count == 2 else nx.path_graph(5)
    avail = [(0, 1 if count == 2 else 2, 1)]
    with pytest.raises(ValueError) as expected:
        list(nx.k_edge_augmentation(graph, 2, avail=avail, partial=True))
    with pytest.raises(ValueError) as actual:
        _constrained_two_augmentation(graph, route, avail, partial=True)
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
def test_partial_k2_existing_candidate_iteration_matches_reference(route):
    graph = nx.path_graph(5)
    avail = {(0, 1): 99, (0, 2): 1}
    before = list(graph.edges(data=True))
    expected = list(nx.k_edge_augmentation(graph, 2, avail=avail, partial=True))
    actual = _constrained_two_augmentation(graph, route, avail, partial=True)
    assert actual == expected
    assert list(graph.edges(data=True)) == before


@pytest.mark.parametrize("route", ["native", "networkx", "backend"])
@pytest.mark.parametrize("high,low", [
    (2**100 + 1, 2**100),
    (Fraction(1, 3) + Fraction(1, 2**100), Fraction(1, 3)),
    (Decimal("0.1000000000000000000001"), Decimal("0.1")),
], ids=["wide-int", "fraction", "decimal"])
def test_constrained_k2_preserves_exact_component_link_costs(route, high, low):
    graph = nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])
    avail = [(0, 4, high), (1, 5, low)]
    expected = list(nx.k_edge_augmentation(graph, 2, avail=avail))
    actual = _constrained_two_augmentation(graph, route, avail)
    assert actual == expected == [(1, 5)]


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("partial", [False, True])
def test_constrained_k2_random_weighted_forests_match_networkx(seed, partial):
    rng = random.Random(seed)
    graph = nx.Graph()
    graph.add_nodes_from(rng.sample(range(7), 7))
    graph.add_edges_from((node, node + 1) for node in range(6) if rng.random() < 0.7)
    avail = {
        (u, v): rng.randrange(1, 10)
        for u, v in nx.non_edges(graph)
        if rng.random() < 0.65
    }
    before = list(graph.edges())
    try:
        expected = list(nx.k_edge_augmentation(graph, 2, avail=avail, partial=partial))
    except nx.NetworkXUnfeasible as exc:
        with pytest.raises(nx.NetworkXUnfeasible) as actual:
            _constrained_two_augmentation(graph, "native", avail, partial=partial)
        assert actual.value.args == exc.args
    else:
        actual = _constrained_two_augmentation(graph, "native", avail, partial=partial)
        assert actual == expected
        augmented = graph.copy()
        augmented.add_edges_from(actual)
        if not partial:
            assert nx.is_k_edge_connected(augmented, 2)
    assert list(graph.edges()) == before
