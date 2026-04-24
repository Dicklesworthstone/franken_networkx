"""Tests for previously untested algorithm functions.

Covers graph operators, community detection, dominating sets,
planarity, transitive operations, and remaining shortest path variants.
"""

from datetime import datetime, timedelta
import inspect
import math
from pathlib import Path
from runpy import run_path
from unittest import mock

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _repo_root():
    return Path(__file__).resolve().parents[2]


def _load_coverage_matrix_script():
    script_path = _repo_root() / "scripts" / "generate_coverage_matrix.py"
    return run_path(str(script_path))


def test_public_coverage_has_no_networkx_delegated_exports():
    coverage_matrix = _load_coverage_matrix_script()
    exports, _duplicates = coverage_matrix["load_public_exports"]()
    delegated_exports = sorted(
        name
        for name, obj in exports
        if coverage_matrix["classify_export"](obj) == "NX_DELEGATED"
    )

    assert delegated_exports == []


def test_generated_coverage_matrix_document_is_current():
    coverage_matrix = _load_coverage_matrix_script()
    exports, duplicates = coverage_matrix["load_public_exports"]()
    rendered = coverage_matrix["render_markdown"](exports, duplicates)
    coverage_path = _repo_root() / "docs" / "coverage.md"

    assert coverage_path.read_text(encoding="utf-8") == rendered


# ---------------------------------------------------------------------------
# Graph operators
# ---------------------------------------------------------------------------


class TestGraphOperators:
    def test_union(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G2 = fnx.Graph()
        G2.add_edge(2, 3)
        result = fnx.union(G1, G2)
        assert result.number_of_nodes() == 4
        assert result.number_of_edges() == 2

    def test_intersection(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_edge(0, 1)
        G2.add_edge(2, 3)
        result = fnx.intersection(G1, G2)
        assert result.has_edge(0, 1)
        assert not result.has_edge(1, 2)

    def test_compose(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G2 = fnx.Graph()
        G2.add_edge(1, 2)
        result = fnx.compose(G1, G2)
        assert result.number_of_nodes() == 3
        assert result.number_of_edges() == 2

    def test_difference(self):
        # br-diffnodes: nx enforces equal node sets; seed both graphs
        # with the same nodes so edge-set semantics can be exercised.
        G1 = fnx.Graph()
        G1.add_nodes_from([0, 1, 2])
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_nodes_from([0, 1, 2])
        G2.add_edge(0, 1)
        result = fnx.difference(G1, G2)
        assert not result.has_edge(0, 1)
        assert result.has_edge(1, 2)

    def test_symmetric_difference(self):
        # br-diffnodes: nx enforces equal node sets.
        G1 = fnx.Graph()
        G1.add_nodes_from([0, 1, 2, 3])
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_nodes_from([0, 1, 2, 3])
        G2.add_edge(0, 1)
        G2.add_edge(2, 3)
        result = fnx.symmetric_difference(G1, G2)
        assert not result.has_edge(0, 1)
        assert result.has_edge(1, 2)
        assert result.has_edge(2, 3)


# ---------------------------------------------------------------------------
# Community detection
# ---------------------------------------------------------------------------


class TestCommunityDetection:
    def test_louvain_communities(self):
        G = fnx.Graph()
        # Two cliques connected by a bridge
        for i in range(4):
            for j in range(i + 1, 4):
                G.add_edge(i, j)
        for i in range(4, 8):
            for j in range(i + 1, 8):
                G.add_edge(i, j)
        G.add_edge(3, 4)  # bridge
        comms = fnx.louvain_communities(G)
        assert len(comms) >= 2

    def test_label_propagation_communities(self):
        G = fnx.path_graph(10)
        comms = fnx.label_propagation_communities(G)
        assert len(comms) >= 1
        # All nodes should be in some community
        all_nodes = set()
        for c in comms:
            all_nodes.update(c)
        assert len(all_nodes) == 10

    def test_greedy_modularity_communities(self):
        G = fnx.complete_graph(6)
        comms = fnx.greedy_modularity_communities(G)
        assert len(comms) >= 1

    def test_modularity(self):
        G = fnx.complete_graph(4)
        # modularity expects lists of node labels
        comms = [[0, 1], [2, 3]]
        m = fnx.modularity(G, comms)
        assert isinstance(m, float)
        assert -0.5 <= m <= 1.0


# ---------------------------------------------------------------------------
# Dominating sets
# ---------------------------------------------------------------------------


class TestDominatingSets:
    def test_dominating_set(self):
        G = fnx.star_graph(4)
        ds = fnx.dominating_set(G)
        assert isinstance(ds, (list, set))
        assert len(ds) >= 1

    def test_is_dominating_set(self):
        G = fnx.star_graph(4)
        # Center node (0) dominates all
        assert fnx.is_dominating_set(G, [0])
        # A leaf alone doesn't dominate all
        assert not fnx.is_dominating_set(G, [1])


# ---------------------------------------------------------------------------
# Planarity
# ---------------------------------------------------------------------------


class TestPlanarity:
    def test_planar_graph(self):
        # K4 is planar
        G = fnx.complete_graph(4)
        assert fnx.is_planar(G)

    def test_non_planar_graph(self):
        # K5 is not planar (Kuratowski's theorem)
        G = fnx.complete_graph(5)
        assert not fnx.is_planar(G)

    def test_is_planar_accepts_G_kwarg(self):
        """Regression guard for franken_networkx-sl3mn — the parameter
        must be named ``G`` (matching upstream nx) so callers can use
        keyword-argument form."""
        G = fnx.complete_graph(4)
        assert fnx.is_planar(G=G) is True

    def test_is_planar_rejects_invalid_backend_kwargs(self):
        G = fnx.complete_graph(4)
        with pytest.raises(TypeError):
            fnx.is_planar(G, bogus_kwarg="x")

    def test_is_planar_transformed_graphs_match_networkx(self):
        planar_self_loop = fnx.cycle_graph(4)
        expected_planar_self_loop = nx.cycle_graph(4)
        planar_self_loop.add_edge(0, 0)
        expected_planar_self_loop.add_edge(0, 0)

        tuple_mapping = {node: ("cycle-node", node) for node in range(4)}
        tuple_labeled_planar = fnx.relabel_nodes(fnx.cycle_graph(4), tuple_mapping)
        expected_tuple_labeled_planar = nx.relabel_nodes(
            nx.cycle_graph(4),
            tuple_mapping,
        )

        disconnected_planar = fnx.Graph()
        expected_disconnected_planar = nx.Graph()
        disconnected_edges = [
            (0, 1),
            (1, 2),
            (2, 0),
            ("path-a", "path-b"),
            ("path-b", "path-c"),
        ]
        disconnected_planar.add_edges_from(disconnected_edges)
        expected_disconnected_planar.add_edges_from(disconnected_edges)

        nonplanar_self_loop = fnx.complete_graph(5)
        expected_nonplanar_self_loop = nx.complete_graph(5)
        nonplanar_self_loop.add_edge(0, 0)
        expected_nonplanar_self_loop.add_edge(0, 0)

        tuple_mapping = {node: ("k5-node", node) for node in range(5)}
        tuple_labeled_nonplanar = fnx.relabel_nodes(fnx.complete_graph(5), tuple_mapping)
        expected_tuple_labeled_nonplanar = nx.relabel_nodes(
            nx.complete_graph(5),
            tuple_mapping,
        )

        for actual_graph, expected_graph in [
            (planar_self_loop, expected_planar_self_loop),
            (tuple_labeled_planar, expected_tuple_labeled_planar),
            (disconnected_planar, expected_disconnected_planar),
            (nonplanar_self_loop, expected_nonplanar_self_loop),
            (tuple_labeled_nonplanar, expected_tuple_labeled_nonplanar),
        ]:
            assert fnx.is_planar(actual_graph) == nx.is_planar(expected_graph)

    def test_check_planarity_certificate_contract_matches_networkx(self):
        graph = fnx.cycle_graph(4)
        expected_planar, expected_embedding = nx.check_planarity(nx.cycle_graph(4))

        actual_planar, embedding = fnx.check_planarity(graph)

        assert actual_planar == expected_planar
        assert actual_planar
        assert isinstance(embedding, nx.PlanarEmbedding)
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        embedding.check_structure()

    def test_check_planarity_counterexample_contract_matches_networkx(self):
        graph = fnx.complete_graph(5)
        expected_planar, expected_counterexample = nx.check_planarity(
            nx.complete_graph(5),
            counterexample=True,
        )

        actual_planar, certificate = fnx.check_planarity(graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            graph,
            counterexample=True,
        )

        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert not actual_counter_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_recursive_certificate_contract_matches_networkx(self):
        graph = fnx.cycle_graph(4)
        expected_planar, expected_embedding = nx.algorithms.planarity.check_planarity_recursive(
            nx.cycle_graph(4)
        )

        actual_planar, embedding = fnx.check_planarity_recursive(graph)

        assert actual_planar == expected_planar
        assert actual_planar
        assert isinstance(embedding, nx.PlanarEmbedding)
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        embedding.check_structure()

    def test_check_planarity_recursive_counterexample_contract_matches_networkx(self):
        graph = fnx.complete_graph(5)
        expected_planar, expected_counterexample = nx.algorithms.planarity.check_planarity_recursive(
            nx.complete_graph(5),
            counterexample=True,
        )

        actual_planar, certificate = fnx.check_planarity_recursive(graph)
        actual_counter_planar, counterexample = fnx.check_planarity_recursive(
            graph,
            counterexample=True,
        )

        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert not actual_counter_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_signature_matches_networkx(self):
        assert str(inspect.signature(fnx.check_planarity)) == str(
            inspect.signature(nx.check_planarity)
        )
        assert str(inspect.signature(fnx.check_planarity_recursive)) == str(
            inspect.signature(nx.algorithms.planarity.check_planarity_recursive)
        )

    @pytest.mark.parametrize(
        "actual_func",
        [fnx.check_planarity, fnx.check_planarity_recursive],
    )
    def test_check_planarity_backend_keyword_contract(self, actual_func):
        is_planar, certificate = actual_func(fnx.cycle_graph(4), backend="networkx")

        assert is_planar
        assert isinstance(certificate, nx.PlanarEmbedding)
        with pytest.raises(ImportError):
            actual_func(fnx.cycle_graph(4), backend="missing")
        with pytest.raises(TypeError):
            actual_func(fnx.cycle_graph(4), unexpected=True)

    def test_get_counterexample_signature_matches_networkx(self):
        assert str(inspect.signature(fnx.get_counterexample)) == str(
            inspect.signature(nx.algorithms.planarity.get_counterexample)
        )
        assert str(inspect.signature(fnx.get_counterexample_recursive)) == str(
            inspect.signature(nx.algorithms.planarity.get_counterexample_recursive)
        )

    @pytest.mark.parametrize(
        ("actual_func", "expected_func"),
        [
            (fnx.get_counterexample, nx.algorithms.planarity.get_counterexample),
            (
                fnx.get_counterexample_recursive,
                nx.algorithms.planarity.get_counterexample_recursive,
            ),
        ],
    )
    def test_get_counterexample_contract_matches_networkx(
        self,
        actual_func,
        expected_func,
    ):
        actual = actual_func(fnx.complete_graph(5))
        expected = expected_func(nx.complete_graph(5))

        assert set(actual.nodes()) == set(expected.nodes())
        assert {frozenset(edge) for edge in actual.edges()} == {
            frozenset(edge) for edge in expected.edges()
        }

    @pytest.mark.parametrize(
        ("actual_func", "expected_func"),
        [
            (fnx.get_counterexample, nx.algorithms.planarity.get_counterexample),
            (
                fnx.get_counterexample_recursive,
                nx.algorithms.planarity.get_counterexample_recursive,
            ),
        ],
    )
    def test_get_counterexample_planar_error_matches_networkx(
        self,
        actual_func,
        expected_func,
    ):
        expected_graph = nx.cycle_graph(4)
        actual_graph = fnx.cycle_graph(4)

        with pytest.raises(nx.NetworkXException) as expected_error:
            expected_func(expected_graph)
        with pytest.raises(nx.NetworkXException) as actual_error:
            actual_func(actual_graph)

        assert str(actual_error.value) == str(expected_error.value)

    def test_get_counterexample_backend_keyword_contract(self):
        expected = nx.algorithms.planarity.get_counterexample(nx.complete_graph(5))
        actual = fnx.get_counterexample(fnx.complete_graph(5), backend="networkx")

        assert set(actual.nodes()) == set(expected.nodes())
        assert {frozenset(edge) for edge in actual.edges()} == {
            frozenset(edge) for edge in expected.edges()
        }
        with pytest.raises(ImportError):
            fnx.get_counterexample(fnx.complete_graph(5), backend="missing")
        with pytest.raises(TypeError):
            fnx.get_counterexample(fnx.complete_graph(5), unexpected=True)

    @pytest.mark.parametrize(
        ("actual_graph", "expected_graph"),
        [
            (fnx.path_graph(5), nx.path_graph(5)),
            (fnx.cycle_graph(6), nx.cycle_graph(6)),
            (fnx.complete_graph(4), nx.complete_graph(4)),
            (fnx.wheel_graph(6), nx.wheel_graph(6)),
        ],
    )
    def test_check_planarity_planar_family_certificates_match_networkx(
        self,
        actual_graph,
        expected_graph,
    ):
        expected_planar, expected_embedding = nx.check_planarity(expected_graph)

        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert actual_planar == expected_planar
        assert actual_planar
        assert isinstance(embedding, nx.PlanarEmbedding)
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        embedding.check_structure()

    @pytest.mark.parametrize(
        ("actual_graph", "expected_graph"),
        [
            (fnx.complete_graph(5), nx.complete_graph(5)),
            (fnx.complete_bipartite_graph(3, 3), nx.complete_bipartite_graph(3, 3)),
        ],
    )
    def test_check_planarity_nonplanar_family_counterexamples_match_networkx(
        self,
        actual_graph,
        expected_graph,
    ):
        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )

        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert not actual_counter_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_isolated_nodes_preserve_classification(self):
        actual_graph = fnx.cycle_graph(4)
        expected_graph = nx.cycle_graph(4)
        actual_graph.add_nodes_from(["isolated-a", "isolated-b"])
        expected_graph.add_nodes_from(["isolated-a", "isolated-b"])

        base_planar, _base_embedding = fnx.check_planarity(fnx.cycle_graph(4))
        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert base_planar == actual_planar == expected_planar
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        assert set(embedding.nodes()) == set(expected_graph.nodes())
        embedding.check_structure()

    def test_check_planarity_isolated_nodes_preserve_counterexample_shape(self):
        actual_graph = fnx.complete_graph(5)
        expected_graph = nx.complete_graph(5)
        actual_graph.add_nodes_from(["isolated-a", "isolated-b"])
        expected_graph.add_nodes_from(["isolated-a", "isolated-b"])

        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )
        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_relabeling_preserves_planar_certificate_labels(self):
        mapping = {node: f"wheel-node-{node}" for node in range(6)}
        actual_graph = fnx.relabel_nodes(fnx.wheel_graph(6), mapping)
        expected_graph = nx.relabel_nodes(nx.wheel_graph(6), mapping)

        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert actual_planar == expected_planar
        assert actual_planar
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        assert set(embedding.nodes()) == set(mapping.values())
        embedding.check_structure()

    def test_check_planarity_relabeling_preserves_counterexample_shape(self):
        mapping = {node: f"k5-node-{node}" for node in range(5)}
        actual_graph = fnx.relabel_nodes(fnx.complete_graph(5), mapping)
        expected_graph = nx.relabel_nodes(nx.complete_graph(5), mapping)

        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )
        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert set(counterexample.nodes()) == set(mapping.values())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_pendant_leaf_preserves_planar_certificate(self):
        actual_graph = fnx.complete_graph(4)
        expected_graph = nx.complete_graph(4)
        actual_graph.add_edge(0, "pendant-leaf")
        expected_graph.add_edge(0, "pendant-leaf")

        base_planar, _base_embedding = fnx.check_planarity(fnx.complete_graph(4))
        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert base_planar == actual_planar == expected_planar
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        assert set(embedding.nodes()) == set(expected_graph.nodes())
        embedding.check_structure()

    def test_check_planarity_pendant_leaf_preserves_counterexample_shape(self):
        actual_graph = fnx.complete_graph(5)
        expected_graph = nx.complete_graph(5)
        actual_graph.add_edge(0, "pendant-leaf")
        expected_graph.add_edge(0, "pendant-leaf")

        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )
        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_edge_subdivision_preserves_planar_certificate(self):
        actual_graph = fnx.cycle_graph(4)
        expected_graph = nx.cycle_graph(4)
        actual_graph.remove_edge(0, 1)
        expected_graph.remove_edge(0, 1)
        actual_graph.add_edges_from([(0, "subdivision-node"), ("subdivision-node", 1)])
        expected_graph.add_edges_from([(0, "subdivision-node"), ("subdivision-node", 1)])

        base_planar, _base_embedding = fnx.check_planarity(fnx.cycle_graph(4))
        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert base_planar == actual_planar == expected_planar
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        assert set(embedding.nodes()) == set(expected_graph.nodes())
        embedding.check_structure()

    def test_check_planarity_edge_subdivision_preserves_counterexample_shape(self):
        actual_graph = fnx.complete_graph(5)
        expected_graph = nx.complete_graph(5)
        actual_graph.remove_edge(0, 1)
        expected_graph.remove_edge(0, 1)
        actual_graph.add_edges_from([(0, "subdivision-node"), ("subdivision-node", 1)])
        expected_graph.add_edges_from([(0, "subdivision-node"), ("subdivision-node", 1)])

        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )
        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_disconnected_planar_components_share_certificate(self):
        actual_graph = fnx.Graph()
        expected_graph = nx.Graph()
        component_edges = [
            (0, 1),
            (1, 2),
            (2, 0),
            ("path-a", "path-b"),
            ("path-b", "path-c"),
        ]
        actual_graph.add_edges_from(component_edges)
        expected_graph.add_edges_from(component_edges)

        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert actual_planar == expected_planar
        assert actual_planar
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        assert set(embedding.nodes()) == set(expected_graph.nodes())
        embedding.check_structure()

    def test_check_planarity_disconnected_planar_component_keeps_nonplanarity(self):
        actual_graph = fnx.complete_graph(5)
        expected_graph = nx.complete_graph(5)
        component_edges = [
            ("triangle-a", "triangle-b"),
            ("triangle-b", "triangle-c"),
            ("triangle-c", "triangle-a"),
        ]
        actual_graph.add_edges_from(component_edges)
        expected_graph.add_edges_from(component_edges)

        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )
        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_self_loop_preserves_planar_certificate(self):
        actual_graph = fnx.cycle_graph(4)
        expected_graph = nx.cycle_graph(4)
        actual_graph.add_edge(0, 0)
        expected_graph.add_edge(0, 0)

        base_planar, _base_embedding = fnx.check_planarity(fnx.cycle_graph(4))
        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert base_planar == actual_planar == expected_planar
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        assert set(embedding.nodes()) == set(expected_graph.nodes())
        embedding.check_structure()

    def test_check_planarity_self_loop_preserves_counterexample_shape(self):
        actual_graph = fnx.complete_graph(5)
        expected_graph = nx.complete_graph(5)
        actual_graph.add_edge(0, 0)
        expected_graph.add_edge(0, 0)

        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )
        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}

    def test_check_planarity_tuple_labels_preserve_planar_certificate(self):
        mapping = {node: ("cycle-node", node) for node in range(4)}
        actual_graph = fnx.relabel_nodes(fnx.cycle_graph(4), mapping)
        expected_graph = nx.relabel_nodes(nx.cycle_graph(4), mapping)

        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, embedding = fnx.check_planarity(actual_graph)

        assert actual_planar == expected_planar
        assert actual_planar
        assert set(embedding.nodes()) == set(expected_embedding.nodes())
        assert set(embedding.nodes()) == set(mapping.values())
        embedding.check_structure()

    def test_check_planarity_tuple_labels_preserve_counterexample_shape(self):
        mapping = {node: ("k5-node", node) for node in range(5)}
        actual_graph = fnx.relabel_nodes(fnx.complete_graph(5), mapping)
        expected_graph = nx.relabel_nodes(nx.complete_graph(5), mapping)

        expected_planar, expected_counterexample = nx.check_planarity(
            expected_graph,
            counterexample=True,
        )
        actual_planar, certificate = fnx.check_planarity(actual_graph)
        actual_counter_planar, counterexample = fnx.check_planarity(
            actual_graph,
            counterexample=True,
        )

        assert actual_planar == expected_planar
        assert not actual_planar
        assert certificate is None
        assert actual_counter_planar == expected_planar
        assert set(counterexample.nodes()) == set(expected_counterexample.nodes())
        assert set(counterexample.nodes()) == set(mapping.values())
        assert {
            frozenset(edge) for edge in counterexample.edges()
        } == {frozenset(edge) for edge in expected_counterexample.edges()}


# ---------------------------------------------------------------------------
# Graph predicates
# ---------------------------------------------------------------------------


class TestGraphPredicates:
    def test_is_empty_true(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        assert fnx.is_empty(G)

    def test_is_empty_false(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        assert not fnx.is_empty(G)

    def test_degree_histogram(self):
        G = fnx.path_graph(5)
        hist = fnx.degree_histogram(G)
        assert isinstance(hist, list)
        # Path: two nodes of degree 1, three of degree 2
        assert hist[1] == 2
        assert hist[2] == 3


# ---------------------------------------------------------------------------
# Shortest path variants
# ---------------------------------------------------------------------------


class TestShortestPathVariants:
    def test_all_pairs_shortest_path(self):
        G = fnx.path_graph(4)
        # Matches upstream: generator of (source, paths-dict) pairs.
        result = dict(fnx.all_pairs_shortest_path(G))
        assert len(result) == 4
        assert result[0][3] == [0, 1, 2, 3]

    def test_all_pairs_shortest_path_length(self):
        G = fnx.path_graph(4)
        # Matches upstream: generator of (source, lengths-dict) pairs.
        result = dict(fnx.all_pairs_shortest_path_length(G))
        assert len(result) == 4
        assert result[0][3] == 3

    def test_single_source_shortest_path(self):
        G = fnx.path_graph(4)
        paths = fnx.single_source_shortest_path(G, 0)
        assert len(paths) == 4
        assert paths[3] == [0, 1, 2, 3]

    def test_single_source_shortest_path_length(self):
        G = fnx.path_graph(4)
        lengths = fnx.single_source_shortest_path_length(G, 0)
        assert lengths[0] == 0
        assert lengths[3] == 3

    def test_shortest_path_argless_returns_generator(self):
        """Regression (br-1uoos): shortest_path(G) with no source/target
        must return a generator of (source, paths_dict) pairs to match
        networkx's all_pairs contract, not a materialized dict-of-dicts.
        """
        import types
        G = fnx.path_graph(4)
        result = fnx.shortest_path(G)
        assert isinstance(result, types.GeneratorType), (
            f"expected generator, got {type(result).__name__}"
        )
        materialized = dict(result)
        assert sorted(materialized) == [0, 1, 2, 3]
        assert materialized[0][3] == [0, 1, 2, 3]
        # Calling next() on it should work like networkx
        result2 = fnx.shortest_path(G)
        first = next(result2)
        assert isinstance(first, tuple) and len(first) == 2

    def test_multi_source_dijkstra(self):
        G = fnx.path_graph(5)
        G.add_edge(0, 1, weight=1.0)
        G.add_edge(1, 2, weight=1.0)
        G.add_edge(2, 3, weight=1.0)
        G.add_edge(3, 4, weight=1.0)
        result = fnx.multi_source_dijkstra(G, [0, 4], weight="weight")
        assert isinstance(result, (dict, tuple, list))

    def test_barycenter(self):
        G = fnx.path_graph(5)
        bc = fnx.barycenter(G)
        # Center of a path is the middle node(s)
        assert 2 in bc

    def test_barycenter_disconnected_raises(self):
        G = fnx.empty_graph(5)
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.barycenter(G)


# ---------------------------------------------------------------------------
# Transitive operations
# ---------------------------------------------------------------------------


class TestTransitiveOperations:
    def test_transitive_closure(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        tc = fnx.transitive_closure(D)
        assert tc.has_edge(0, 2)  # transitively reachable
        assert tc.has_edge(0, 1)

    def test_transitive_closure_default_is_non_reflexive_even_with_existing_self_loop(self):
        D = fnx.DiGraph()
        D.add_edge(1, 1)
        D.add_edge(1, 2)

        tc = fnx.transitive_closure(D)

        assert tc.has_edge(1, 1)
        assert tc.has_edge(1, 2)
        assert not tc.has_edge(2, 2)

    def test_transitive_reduction(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        D.add_edge(0, 2)  # redundant
        tr = fnx.transitive_reduction(D)
        assert tr.has_edge(0, 1)
        assert tr.has_edge(1, 2)
        assert not tr.has_edge(0, 2)  # removed as redundant


# ---------------------------------------------------------------------------
# Directed component counts
# ---------------------------------------------------------------------------


class TestDirectedComponentCounts:
    def test_number_strongly_connected_components(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        D.add_node(2)
        assert fnx.number_strongly_connected_components(D) == 2

    def test_number_weakly_connected_components(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_node(2)
        assert fnx.number_weakly_connected_components(D) == 2

    def test_weakly_connected_components(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_node(2)
        wcc = list(fnx.weakly_connected_components(D))
        assert len(wcc) == 2

    def test_is_strongly_connected_empty_raises(self):
        D = fnx.DiGraph()
        with pytest.raises(fnx.NetworkXPointlessConcept):
            fnx.is_strongly_connected(D)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


class TestGenerators:
    def test_barabasi_albert(self):
        G = fnx.barabasi_albert_graph(20, 2, seed=42)
        assert G.number_of_nodes() == 20

    def test_watts_strogatz(self):
        G = fnx.watts_strogatz_graph(20, 4, 0.3, seed=42)
        assert G.number_of_nodes() == 20
        assert fnx.is_connected(G)

    @needs_nx
    def test_watts_strogatz_accepts_odd_k_like_networkx(self):
        fnx_graph = fnx.watts_strogatz_graph(7, 3, 0.0, seed=42)
        nx_graph = nx.watts_strogatz_graph(7, 3, 0.0, seed=42)
        assert fnx_graph.number_of_nodes() == nx_graph.number_of_nodes()
        assert fnx_graph.number_of_edges() == nx_graph.number_of_edges() == 7
        assert sorted(dict(fnx_graph.degree).values()) == sorted(
            dict(nx_graph.degree()).values()
        )

    @needs_nx
    def test_newman_watts_strogatz_accepts_odd_k_like_networkx(self):
        fnx_graph = fnx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42)
        nx_graph = nx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42)
        assert fnx_graph.number_of_nodes() == nx_graph.number_of_nodes()
        assert fnx_graph.number_of_edges() == nx_graph.number_of_edges() == 7
        assert sorted(dict(fnx_graph.degree).values()) == sorted(
            dict(nx_graph.degree()).values()
        )

    @needs_nx
    def test_connected_watts_strogatz_accepts_tries_keyword(self):
        fnx_graph = fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42)
        nx_graph = nx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42)
        assert fnx_graph.number_of_nodes() == nx_graph.number_of_nodes() == 12
        assert fnx.is_connected(fnx_graph)
        assert nx.is_connected(nx_graph)

    def test_connected_watts_strogatz_zero_tries_raises(self):
        with pytest.raises(ValueError, match="Maximum number of tries exceeded"):
            fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=0, seed=42)

    def test_random_generators_support_create_using_via_networkx_fallback(self):
        balanced = fnx.balanced_tree(2, 2, create_using=fnx.Graph())
        barbell = fnx.barbell_graph(3, 2, create_using=fnx.Graph())
        bull = fnx.bull_graph(create_using=fnx.Graph())
        chordal_cycle = fnx.chordal_cycle_graph(5, create_using=fnx.MultiGraph())
        chvatal = fnx.chvatal_graph(create_using=fnx.Graph())
        circulant = fnx.circulant_graph(6, [1, 2], create_using=fnx.Graph())
        complete = fnx.complete_graph(4, create_using=fnx.Graph())
        cubical = fnx.cubical_graph(create_using=fnx.Graph())
        cycle = fnx.cycle_graph(4, create_using=fnx.Graph())
        desargues = fnx.desargues_graph(create_using=fnx.Graph())
        diamond = fnx.diamond_graph(create_using=fnx.Graph())
        dodecahedral = fnx.dodecahedral_graph(create_using=fnx.Graph())
        empty = fnx.empty_graph(4, create_using=fnx.Graph())
        frucht = fnx.frucht_graph(create_using=fnx.Graph())
        full = fnx.full_rary_tree(2, 7, create_using=fnx.Graph())
        generalized_petersen = fnx.generalized_petersen_graph(5, 2, create_using=fnx.Graph())
        binomial = fnx.binomial_tree(3, create_using=fnx.Graph())
        bipartite = fnx.complete_bipartite_graph(2, 3, create_using=fnx.Graph())
        dense = fnx.dense_gnm_random_graph(5, 4, seed=1, create_using=fnx.Graph())
        dgm = fnx.dorogovtsev_goltsev_mendes_graph(2, create_using=fnx.Graph())
        hakimi = fnx.havel_hakimi_graph([2, 2, 2, 2], create_using=fnx.Graph())
        hkn = fnx.hkn_harary_graph(2, 5, create_using=fnx.Graph())
        hnm = fnx.hnm_harary_graph(5, 5, create_using=fnx.Graph())
        house = fnx.house_graph(create_using=fnx.Graph())
        house_x = fnx.house_x_graph(create_using=fnx.Graph())
        heawood = fnx.heawood_graph(create_using=fnx.Graph())
        icosahedral = fnx.icosahedral_graph(create_using=fnx.Graph())
        circular = fnx.circular_ladder_graph(4, create_using=fnx.Graph())
        krackhardt = fnx.krackhardt_kite_graph(create_using=fnx.Graph())
        ladder = fnx.ladder_graph(4, create_using=fnx.Graph())
        lollipop = fnx.lollipop_graph(4, 3, create_using=fnx.Graph())
        moebius = fnx.moebius_kantor_graph(create_using=fnx.Graph())
        null = fnx.null_graph(create_using=fnx.Graph())
        octahedral = fnx.octahedral_graph(create_using=fnx.Graph())
        paley = fnx.paley_graph(5, create_using=fnx.DiGraph())
        path = fnx.path_graph(4, create_using=fnx.Graph())
        petersen = fnx.petersen_graph(create_using=fnx.Graph())
        random_clustered = fnx.random_clustered_graph(
            [(1, 0), (1, 0)],
            seed=1,
            create_using=fnx.MultiGraph(),
        )
        random_lobster = fnx.random_lobster_graph(8, 0.4, 0.3, seed=1, create_using=fnx.Graph())
        star = fnx.star_graph(3, create_using=fnx.Graph())
        tadpole = fnx.tadpole_graph(4, 3, create_using=fnx.Graph())
        tetrahedral = fnx.tetrahedral_graph(create_using=fnx.Graph())
        trivial = fnx.trivial_graph(create_using=fnx.Graph())
        truncated_cube = fnx.truncated_cube_graph(create_using=fnx.Graph())
        truncated_tetrahedron = fnx.truncated_tetrahedron_graph(create_using=fnx.Graph())
        tutte = fnx.tutte_graph(create_using=fnx.Graph())
        wheel = fnx.wheel_graph(6, create_using=fnx.Graph())
        periodic_grid = fnx.grid_2d_graph(2, 3, periodic=True, create_using=fnx.Graph())
        ws = fnx.watts_strogatz_graph(7, 3, 0.0, seed=42, create_using=fnx.Graph())
        ba = fnx.barabasi_albert_graph(8, 2, seed=42, create_using=fnx.Graph())
        gnp = fnx.gnp_random_graph(7, 0.2, seed=42, create_using=fnx.Graph())
        er = fnx.erdos_renyi_graph(7, 0.2, seed=42, create_using=fnx.Graph())
        fast = fnx.fast_gnp_random_graph(7, 0.2, seed=42, create_using=fnx.Graph())
        graph = fnx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42, create_using=fnx.Graph())
        regular = fnx.random_regular_graph(2, 6, seed=42, create_using=fnx.Graph())
        cluster = fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42, create_using=fnx.Graph())

        assert isinstance(balanced, fnx.Graph)
        assert isinstance(barbell, fnx.Graph)
        assert isinstance(bull, fnx.Graph)
        assert isinstance(chordal_cycle, fnx.MultiGraph)
        assert isinstance(chvatal, fnx.Graph)
        assert isinstance(circulant, fnx.Graph)
        assert isinstance(complete, fnx.Graph)
        assert isinstance(cubical, fnx.Graph)
        assert isinstance(cycle, fnx.Graph)
        assert isinstance(desargues, fnx.Graph)
        assert isinstance(diamond, fnx.Graph)
        assert isinstance(dense, fnx.Graph)
        assert isinstance(dgm, fnx.Graph)
        assert isinstance(dodecahedral, fnx.Graph)
        assert isinstance(empty, fnx.Graph)
        assert isinstance(frucht, fnx.Graph)
        assert isinstance(full, fnx.Graph)
        assert isinstance(generalized_petersen, fnx.Graph)
        assert isinstance(hakimi, fnx.Graph)
        assert isinstance(hkn, fnx.Graph)
        assert isinstance(hnm, fnx.Graph)
        assert isinstance(binomial, fnx.Graph)
        assert isinstance(bipartite, fnx.Graph)
        assert isinstance(house, fnx.Graph)
        assert isinstance(house_x, fnx.Graph)
        assert isinstance(heawood, fnx.Graph)
        assert isinstance(icosahedral, fnx.Graph)
        assert isinstance(circular, fnx.Graph)
        assert isinstance(krackhardt, fnx.Graph)
        assert isinstance(ladder, fnx.Graph)
        assert isinstance(lollipop, fnx.Graph)
        assert isinstance(moebius, fnx.Graph)
        assert isinstance(null, fnx.Graph)
        assert isinstance(octahedral, fnx.Graph)
        assert isinstance(paley, fnx.DiGraph)
        assert isinstance(path, fnx.Graph)
        assert isinstance(petersen, fnx.Graph)
        assert isinstance(random_clustered, fnx.MultiGraph)
        assert isinstance(random_lobster, fnx.Graph)
        assert isinstance(star, fnx.Graph)
        assert isinstance(tadpole, fnx.Graph)
        assert isinstance(tetrahedral, fnx.Graph)
        assert isinstance(trivial, fnx.Graph)
        assert isinstance(truncated_cube, fnx.Graph)
        assert isinstance(truncated_tetrahedron, fnx.Graph)
        assert isinstance(tutte, fnx.Graph)
        assert isinstance(wheel, fnx.Graph)
        assert isinstance(periodic_grid, fnx.Graph)
        assert isinstance(ws, fnx.Graph)
        assert isinstance(ba, fnx.Graph)
        assert isinstance(gnp, fnx.Graph)
        assert isinstance(er, fnx.Graph)
        assert isinstance(fast, fnx.Graph)
        assert isinstance(graph, fnx.Graph)
        assert isinstance(regular, fnx.Graph)
        assert isinstance(cluster, fnx.Graph)

    def test_complete_multipartite_and_windmill_match_networkx_contract(self):
        multipartite = fnx.complete_multipartite_graph(2, 3, 1)
        expected_multipartite = nx.complete_multipartite_graph(2, 3, 1)
        windmill = fnx.windmill_graph(3, 4)
        expected_windmill = nx.windmill_graph(3, 4)

        assert sorted(multipartite.edges()) == sorted(expected_multipartite.edges())
        assert sorted(windmill.edges()) == sorted(expected_windmill.edges())

    def test_empty_graph_respects_default_graph_class(self):
        graph = fnx.empty_graph(3, default=fnx.DiGraph)

        assert isinstance(graph, fnx.DiGraph)
        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 0

    @needs_nx
    def test_serialization_graph_builders_match_networkx_contract(self):
        def normalize_adjacency_payload(payload):
            normalized = dict(payload)
            normalized["nodes"] = sorted(payload["nodes"], key=lambda item: tuple(sorted(item.items())))
            normalized["adjacency"] = [
                sorted(neighbors, key=lambda item: tuple(sorted(item.items())))
                for neighbors in payload["adjacency"]
            ]
            return normalized

        adjacency_payload = {
            "directed": True,
            "multigraph": False,
            "graph": [],
            "nodes": [{"id": 0}, {"id": 1}],
            "adjacency": [[{"id": 1}], []],
        }
        adjacency_graph = fnx.adjacency_graph(adjacency_payload, directed=True, multigraph=False)
        expected_adjacency = nx.adjacency_graph(
            adjacency_payload,
            directed=True,
            multigraph=False,
        )

        node_link_payload = {
            "directed": True,
            "multigraph": False,
            "graph": {},
            "nodes": [{"id": 0}, {"id": 1}],
            "links": [{"source": 0, "target": 1}],
        }
        node_link_graph = fnx.node_link_graph(
            node_link_payload,
            directed=True,
            multigraph=False,
            edges="links",
        )
        expected_node_link = nx.node_link_graph(
            node_link_payload,
            directed=True,
            multigraph=False,
            edges="links",
        )

        tree_payload = {"name": "root", "kids": [{"name": "leaf"}]}
        tree = fnx.tree_graph(tree_payload, ident="name", children="kids")
        expected_tree = nx.tree_graph(tree_payload, ident="name", children="kids")
        tree_export = fnx.tree_data(
            nx.DiGraph([(0, 1)]),
            0,
            ident="name",
            children="kids",
        )
        expected_tree_export = nx.tree_data(
            nx.DiGraph([(0, 1)]),
            0,
            ident="name",
            children="kids",
        )

        adjacency_data = fnx.adjacency_data(
            fnx.path_graph(3),
            attrs={"id": "name", "key": "ekey"},
        )
        expected_adjacency_data = nx.adjacency_data(
            nx.path_graph(3),
            attrs={"id": "name", "key": "ekey"},
        )

        cytoscape_payload = {
            "data": [],
            "directed": False,
            "multigraph": False,
            "elements": {
                "nodes": [
                    {"data": {"value": "a", "label": "A"}},
                    {"data": {"value": "b", "label": "B"}},
                ],
                "edges": [{"data": {"source": "a", "target": "b"}}],
            },
        }
        cytoscape = fnx.cytoscape_graph(cytoscape_payload, name="label", ident="value")
        expected_cytoscape = nx.cytoscape_graph(
            cytoscape_payload,
            name="label",
            ident="value",
        )
        cytoscape_data = fnx.cytoscape_data(
            fnx.path_graph(2),
            name="label",
            ident="value",
        )
        expected_cytoscape_data = nx.cytoscape_data(
            nx.path_graph(2),
            name="label",
            ident="value",
        )
        node_link_export = fnx.node_link_data(
            fnx.path_graph(2),
            edges="links",
            nodes="vertices",
            source="src",
            target="dst",
            name="name",
        )
        expected_node_link_export = nx.node_link_data(
            nx.path_graph(2),
            edges="links",
            nodes="vertices",
            source="src",
            target="dst",
            name="name",
        )

        projected_source = fnx.complete_bipartite_graph(2, 2)
        projected = fnx.projected_graph(projected_source, [0, 1], multigraph=True)
        expected_projected = nx.projected_graph(
            nx.complete_bipartite_graph(2, 2),
            [0, 1],
            multigraph=True,
        )

        multigraph_input = {
            0: {1: {7: {"weight": 3}}},
            1: {0: {7: {"weight": 3}}},
        }
        converted = fnx.to_networkx_graph(multigraph_input, multigraph_input=True)
        expected_converted = nx.to_networkx_graph(multigraph_input, multigraph_input=True)
        converted_multi = fnx.to_networkx_graph(
            multigraph_input,
            create_using=fnx.MultiGraph(),
            multigraph_input=True,
        )
        expected_converted_multi = nx.to_networkx_graph(
            multigraph_input,
            create_using=nx.MultiGraph(),
            multigraph_input=True,
        )

        assert adjacency_graph.is_directed()
        assert sorted(adjacency_graph.edges()) == sorted(expected_adjacency.edges())
        assert node_link_graph.is_directed()
        assert sorted(node_link_graph.edges()) == sorted(expected_node_link.edges())
        assert normalize_adjacency_payload(adjacency_data) == normalize_adjacency_payload(
            expected_adjacency_data
        )
        assert sorted(tree.edges()) == sorted(expected_tree.edges())
        assert sorted(tree.nodes(data=True)) == sorted(expected_tree.nodes(data=True))
        assert tree_export == expected_tree_export
        assert node_link_export == expected_node_link_export
        assert cytoscape_data == expected_cytoscape_data
        assert sorted(cytoscape.edges()) == sorted(expected_cytoscape.edges())
        assert isinstance(projected, fnx.MultiGraph)
        assert sorted(projected.edges(keys=True)) == sorted(expected_projected.edges(keys=True))
        assert isinstance(converted, fnx.Graph)
        assert sorted(converted.edges(data=True)) == sorted(expected_converted.edges(data=True))
        assert isinstance(converted_multi, fnx.MultiGraph)
        assert sorted(converted_multi.edges(keys=True, data=True)) == sorted(
            expected_converted_multi.edges(keys=True, data=True)
        )

    @needs_nx
    def test_graph_transform_helpers_match_networkx_contract(self):
        path = fnx.path_graph(3)
        line = fnx.line_graph(path, create_using=fnx.Graph())
        expected_line = nx.line_graph(nx.path_graph(3), create_using=nx.Graph())

        clique_graph = fnx.make_max_clique_graph(fnx.complete_graph(4), create_using=fnx.Graph())
        expected_clique_graph = nx.make_max_clique_graph(nx.complete_graph(4), create_using=nx.Graph())

        digraph = fnx.DiGraph([(0, 2), (1, 2)])
        stochastic = fnx.stochastic_graph(digraph, copy=True, weight="w")
        expected_stochastic = nx.stochastic_graph(nx.DiGraph([(0, 2), (1, 2)]), copy=True, weight="w")

        expected_moral = nx.moral_graph(nx.DiGraph([(0, 2), (1, 2)]))
        with mock.patch.object(
            nx,
            "moral_graph",
            side_effect=AssertionError("NetworkX moral_graph fallback used"),
        ):
            moral = fnx.moral_graph(digraph)

        expected_chordal_graph, expected_alpha = nx.complete_to_chordal_graph(nx.cycle_graph(4))
        with mock.patch.object(
            nx,
            "complete_to_chordal_graph",
            side_effect=AssertionError("NetworkX complete_to_chordal_graph fallback used"),
        ):
            chordal_graph, alpha = fnx.complete_to_chordal_graph(fnx.cycle_graph(4))

        assert isinstance(line, fnx.Graph)
        assert sorted(line.edges()) == sorted(expected_line.edges())
        assert isinstance(clique_graph, fnx.Graph)
        assert sorted(clique_graph.edges()) == sorted(expected_clique_graph.edges())
        assert isinstance(stochastic, fnx.DiGraph)
        assert sorted(stochastic.edges(data=True)) == sorted(expected_stochastic.edges(data=True))
        assert {frozenset(edge) for edge in moral.edges()} == {
            frozenset(edge) for edge in expected_moral.edges()
        }
        assert sorted(chordal_graph.edges()) == sorted(expected_chordal_graph.edges())
        assert alpha == expected_alpha

    def test_graph_class_constructors_accept_edge_iterables(self):
        graph = fnx.Graph([(0, 1)])
        multigraph = fnx.MultiGraph([(0, 1)])
        digraph = fnx.DiGraph([(0, 2), (1, 2)])
        multidigraph = fnx.MultiDiGraph([(0, 2), (1, 2)])

        assert sorted(graph.edges()) == [(0, 1)]
        assert sorted(multigraph.edges()) == [(0, 1)]
        assert sorted(digraph.edges()) == [(0, 2), (1, 2)]
        assert sorted(multidigraph.edges()) == [(0, 2), (1, 2)]

    @needs_nx
    def test_ego_graph_and_from_dict_of_dicts_match_networkx_contract(self):
        weighted = fnx.Graph()
        weighted.add_edge(0, 1, weight=1)
        weighted.add_edge(1, 2, weight=1)
        weighted.add_edge(2, 3, weight=5)

        expected_ego = nx.ego_graph(
            nx.Graph(
                [
                    (0, 1, {"weight": 1}),
                    (1, 2, {"weight": 1}),
                    (2, 3, {"weight": 5}),
                ]
            ),
            1,
            radius=1,
            distance="weight",
        )
        with mock.patch.object(
            nx,
            "ego_graph",
            side_effect=AssertionError("NetworkX ego_graph fallback used"),
        ):
            ego = fnx.ego_graph(weighted, 1, radius=1, distance="weight")

        multigraph = fnx.from_dict_of_dicts(
            {0: {1: {7: {"w": 1}}}, 1: {0: {7: {"w": 1}}}},
            create_using=fnx.MultiGraph(),
            multigraph_input=True,
        )
        expected_multigraph = nx.from_dict_of_dicts(
            {0: {1: {7: {"w": 1}}}, 1: {0: {7: {"w": 1}}}},
            create_using=nx.MultiGraph(),
            multigraph_input=True,
        )

        assert sorted(ego.edges(data=True)) == sorted(expected_ego.edges(data=True))
        assert isinstance(multigraph, fnx.MultiGraph)
        assert sorted(multigraph.edges(keys=True, data=True)) == sorted(
            expected_multigraph.edges(keys=True, data=True)
        )

    @needs_nx
    def test_tabular_and_matrix_importers_preserve_networkx_contract(self):
        np = pytest.importorskip("numpy")
        pd = pytest.importorskip("pandas")
        scipy_sparse = pytest.importorskip("scipy.sparse")

        frame = pd.DataFrame(
            [
                {"src": "a", "dst": "b", "ek": 7, "weight": 3},
                {"src": "a", "dst": "b", "ek": 8, "weight": 4},
            ]
        )
        pandas_graph = fnx.from_pandas_edgelist(
            frame,
            source="src",
            target="dst",
            edge_attr="weight",
            create_using=fnx.MultiGraph(),
            edge_key="ek",
        )
        expected_pandas_graph = nx.from_pandas_edgelist(
            frame,
            source="src",
            target="dst",
            edge_attr="weight",
            create_using=nx.MultiGraph(),
            edge_key="ek",
        )

        matrix = np.array([[0, 2], [2, 0]], dtype=int)
        numpy_graph = fnx.from_numpy_array(
            matrix,
            parallel_edges=True,
            create_using=fnx.MultiGraph(),
        )
        expected_numpy_graph = nx.from_numpy_array(
            matrix,
            parallel_edges=True,
            create_using=nx.MultiGraph(),
        )

        sparse_graph = fnx.from_scipy_sparse_array(
            scipy_sparse.csr_array(matrix),
            parallel_edges=True,
            create_using=fnx.MultiGraph(),
        )
        expected_sparse_graph = nx.from_scipy_sparse_array(
            scipy_sparse.csr_array(matrix),
            parallel_edges=True,
            create_using=nx.MultiGraph(),
        )

        assert sorted(pandas_graph.edges(keys=True, data=True)) == sorted(
            expected_pandas_graph.edges(keys=True, data=True)
        )
        assert sorted(numpy_graph.edges(keys=True, data=True)) == sorted(
            expected_numpy_graph.edges(keys=True, data=True)
        )
        assert sorted(sparse_graph.edges(keys=True, data=True)) == sorted(
            expected_sparse_graph.edges(keys=True, data=True)
        )

    @needs_nx
    def test_tabular_and_matrix_exporters_preserve_networkx_contract(self):
        np = pytest.importorskip("numpy")
        pytest.importorskip("pandas")

        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7, weight=3)
        graph.add_edge("a", "b", key=8, weight=4)

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7, weight=3)
        expected_graph.add_edge("a", "b", key=8, weight=4)

        expected_frame = nx.to_pandas_edgelist(
            expected_graph,
            source="src",
            target="dst",
            edge_key="ek",
        )
        expected_matrix = nx.to_numpy_array(
            expected_graph,
            nodelist=["a", "b"],
            multigraph_weight=max,
            weight="weight",
        )
        expected_pandas_adjacency = nx.to_pandas_adjacency(
            expected_graph,
            nodelist=["a", "b"],
            multigraph_weight=max,
            nonedge=-1.0,
        )
        expected_sparse = nx.to_scipy_sparse_array(
            expected_graph,
            nodelist=["a", "b"],
            format="csr",
        )

        with (
            mock.patch.object(
                nx,
                "to_pandas_edgelist",
                side_effect=AssertionError("NetworkX to_pandas_edgelist fallback used"),
            ),
            mock.patch.object(
                nx,
                "to_numpy_array",
                side_effect=AssertionError("NetworkX to_numpy_array fallback used"),
            ),
            mock.patch.object(
                nx,
                "to_pandas_adjacency",
                side_effect=AssertionError("NetworkX to_pandas_adjacency fallback used"),
            ),
            mock.patch.object(
                nx,
                "to_scipy_sparse_array",
                side_effect=AssertionError("NetworkX to_scipy_sparse_array fallback used"),
            ),
        ):
            frame = fnx.to_pandas_edgelist(graph, source="src", target="dst", edge_key="ek")
            matrix = fnx.to_numpy_array(
                graph,
                nodelist=["a", "b"],
                multigraph_weight=max,
                weight="weight",
            )
            pandas_adjacency = fnx.to_pandas_adjacency(
                graph,
                nodelist=["a", "b"],
                multigraph_weight=max,
                nonedge=-1.0,
            )
            sparse = fnx.to_scipy_sparse_array(graph, nodelist=["a", "b"], format="csr")

        assert frame.sort_values(["ek"]).reset_index(drop=True).equals(
            expected_frame.sort_values(["ek"]).reset_index(drop=True)
        )
        assert np.array_equal(matrix, expected_matrix)
        assert pandas_adjacency.equals(expected_pandas_adjacency)
        assert np.array_equal(sparse.toarray(), expected_sparse.toarray())

    @needs_nx
    def test_matrix_exporters_match_networkx_without_fallback(self):
        np = pytest.importorskip("numpy")
        pytest.importorskip("scipy.sparse")

        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7, weight=3)
        graph.add_edge("a", "b", key=8, weight=4)

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7, weight=3)
        expected_graph.add_edge("a", "b", key=8, weight=4)
        expected_matrix = nx.to_numpy_array(
            expected_graph,
            nodelist=["a", "b"],
            multigraph_weight=max,
            weight="weight",
        )
        expected_sparse = nx.to_scipy_sparse_array(
            expected_graph,
            nodelist=["a", "b"],
            format="csr",
        )

        with (
            mock.patch.object(
                nx,
                "to_numpy_array",
                side_effect=AssertionError("NetworkX to_numpy_array fallback used"),
            ),
            mock.patch.object(
                nx,
                "to_scipy_sparse_array",
                side_effect=AssertionError("NetworkX to_scipy_sparse_array fallback used"),
            ),
        ):
            matrix = fnx.to_numpy_array(
                graph,
                nodelist=["a", "b"],
                multigraph_weight=max,
                weight="weight",
            )
            sparse = fnx.to_scipy_sparse_array(graph, nodelist=["a", "b"], format="csr")

        assert np.array_equal(matrix, expected_matrix)
        assert np.array_equal(sparse.toarray(), expected_sparse.toarray())

    @needs_nx
    def test_attribute_accessors_preserve_defaults_and_multigraph_keys(self):
        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7, weight=3)
        graph.add_edge("a", "b", key=8)
        graph.add_node("a", color="red")
        graph.add_node("b")

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7, weight=3)
        expected_graph.add_edge("a", "b", key=8)
        expected_graph.add_node("a", color="red")
        expected_graph.add_node("b")

        expected_node_attributes = nx.get_node_attributes(
            expected_graph,
            "color",
            default=None,
        )
        expected_edge_attributes = nx.get_edge_attributes(
            expected_graph,
            "weight",
            default=0,
        )
        with (
            mock.patch.object(
                nx,
                "get_node_attributes",
                side_effect=AssertionError("NetworkX get_node_attributes fallback used"),
            ),
            mock.patch.object(
                nx,
                "get_edge_attributes",
                side_effect=AssertionError("NetworkX get_edge_attributes fallback used"),
            ),
        ):
            node_attributes = fnx.get_node_attributes(graph, "color", default=None)
            edge_attributes = fnx.get_edge_attributes(graph, "weight", default=0)

        assert node_attributes == expected_node_attributes
        assert edge_attributes == expected_edge_attributes

    @needs_nx
    def test_attribute_mutators_preserve_networkx_multigraph_contract(self):
        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7)
        graph.add_edge("a", "b", key=8)
        graph.add_node("a")
        graph.add_node("b")

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7)
        expected_graph.add_edge("a", "b", key=8)
        expected_graph.add_node("a")
        expected_graph.add_node("b")

        nx.set_edge_attributes(expected_graph, {("a", "b", 7): 5}, "weight")
        nx.set_node_attributes(expected_graph, "blue", "color")
        with (
            mock.patch.object(
                nx,
                "set_edge_attributes",
                side_effect=AssertionError("NetworkX set_edge_attributes fallback used"),
            ),
            mock.patch.object(
                nx,
                "set_node_attributes",
                side_effect=AssertionError("NetworkX set_node_attributes fallback used"),
            ),
        ):
            fnx.set_edge_attributes(graph, {("a", "b", 7): 5}, "weight")
            fnx.set_node_attributes(graph, "blue", "color")

        assert sorted(graph.edges(keys=True, data=True)) == sorted(
            expected_graph.edges(keys=True, data=True)
        )
        assert dict(graph.nodes(data=True)) == dict(expected_graph.nodes(data=True))

    @needs_nx
    def test_top_level_nodes_edges_and_degree_match_networkx(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(1, 2, weight=3)
        graph.add_edge(2, 3, weight=4)

        expected_graph = nx.Graph()
        expected_graph.add_edge(0, 1, weight=2)
        expected_graph.add_edge(1, 2, weight=3)
        expected_graph.add_edge(2, 3, weight=4)

        expected_nodes = list(nx.nodes(expected_graph))
        expected_edges = sorted(nx.edges(expected_graph, [1, 2]))
        expected_degree = dict(nx.degree(expected_graph, weight="weight"))
        with (
            mock.patch.object(
                nx,
                "nodes",
                side_effect=AssertionError("NetworkX nodes fallback used"),
            ),
            mock.patch.object(
                nx,
                "edges",
                side_effect=AssertionError("NetworkX edges fallback used"),
            ),
            mock.patch.object(
                nx,
                "degree",
                side_effect=AssertionError("NetworkX degree fallback used"),
            ),
        ):
            actual_nodes = list(fnx.nodes(graph))
            actual_edges = sorted(fnx.edges(graph, [1, 2]))
            actual_degree = dict(fnx.degree(graph, weight="weight"))

        assert actual_nodes == expected_nodes
        assert actual_edges == expected_edges
        assert actual_degree == expected_degree

    @needs_nx
    def test_default_node_link_serialization_matches_networkx(self):
        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7, weight=3)

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7, weight=3)

        expected_payload = nx.node_link_data(expected_graph)
        with (
            mock.patch.object(
                nx,
                "node_link_data",
                side_effect=AssertionError("NetworkX node_link_data fallback used"),
            ),
            mock.patch.object(
                nx,
                "node_link_graph",
                side_effect=AssertionError("NetworkX node_link_graph fallback used"),
            ),
        ):
            payload = fnx.node_link_data(graph)
            roundtrip = fnx.node_link_graph(expected_payload)

        assert payload == expected_payload
        assert isinstance(roundtrip, fnx.MultiGraph)
        assert sorted(roundtrip.edges(keys=True, data=True)) == sorted(
            expected_graph.edges(keys=True, data=True)
        )

    @needs_nx
    def test_attribute_mixing_helpers_match_networkx_on_missing_attributes(self):
        np = pytest.importorskip("numpy")
        graph = fnx.path_graph(4)
        expected_graph = nx.path_graph(4)

        expected_dict = nx.attribute_mixing_dict(
            expected_graph,
            "missing",
            normalized=False,
        )
        expected_matrix = nx.attribute_mixing_matrix(
            expected_graph,
            "missing",
            normalized=True,
        )
        with (
            mock.patch.object(
                nx,
                "attribute_mixing_dict",
                side_effect=AssertionError("NetworkX attribute_mixing_dict fallback used"),
            ),
            mock.patch.object(
                nx,
                "attribute_mixing_matrix",
                side_effect=AssertionError("NetworkX attribute_mixing_matrix fallback used"),
            ),
        ):
            actual_dict = fnx.attribute_mixing_dict(graph, "missing", normalized=False)
            actual_matrix = fnx.attribute_mixing_matrix(graph, "missing", normalized=True)

        assert actual_dict == expected_dict
        assert np.array_equal(
            actual_matrix,
            expected_matrix,
        )

    @needs_nx
    def test_attribute_assortativity_matches_networkx_nan_contract(self):
        graph = fnx.Graph()
        graph.add_edge("a", "b")
        graph.nodes["a"]["color"] = "red"
        graph.nodes["b"]["color"] = "red"

        expected_graph = nx.Graph()
        expected_graph.add_edge("a", "b")
        expected_graph.nodes["a"]["color"] = "red"
        expected_graph.nodes["b"]["color"] = "red"

        expected = nx.attribute_assortativity_coefficient(expected_graph, "color")
        with mock.patch.object(
            nx,
            "attribute_assortativity_coefficient",
            side_effect=AssertionError(
                "NetworkX attribute_assortativity_coefficient fallback used"
            ),
        ):
            actual = fnx.attribute_assortativity_coefficient(graph, "color")

        assert math.isnan(expected)
        assert math.isnan(actual)

    @needs_nx
    def test_numeric_assortativity_missing_attribute_matches_networkx_error(self):
        graph = fnx.path_graph(3)
        expected_graph = nx.path_graph(3)

        with pytest.raises(KeyError):
            nx.numeric_assortativity_coefficient(expected_graph, "missing")
        with mock.patch.object(
            nx,
            "numeric_assortativity_coefficient",
            side_effect=AssertionError(
                "NetworkX numeric_assortativity_coefficient fallback used"
            ),
        ):
            with pytest.raises(KeyError):
                fnx.numeric_assortativity_coefficient(graph, "missing")

    @needs_nx
    def test_all_pairs_node_connectivity_matches_networkx(self):
        graph = fnx.path_graph(4)
        expected_graph = nx.path_graph(4)

        expected = nx.all_pairs_node_connectivity(expected_graph)
        with mock.patch.object(
            nx,
            "all_pairs_node_connectivity",
            side_effect=AssertionError("NetworkX all_pairs_node_connectivity fallback used"),
        ):
            actual = fnx.all_pairs_node_connectivity(graph)

        assert actual == expected

    @needs_nx
    def test_degree_pearson_and_generalized_degree_match_networkx(self):
        math = pytest.importorskip("math")
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1)
        digraph.add_edge(2, 1)
        digraph.add_edge(2, 3)

        expected_digraph = nx.DiGraph()
        expected_digraph.add_edge(0, 1)
        expected_digraph.add_edge(2, 1)
        expected_digraph.add_edge(2, 3)

        graph = fnx.Graph()
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

        expected_graph = nx.Graph()
        expected_graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

        expected_corr = nx.degree_pearson_correlation_coefficient(
            expected_digraph,
            x="in",
            y="out",
        )
        expected_generalized = nx.generalized_degree(expected_graph)
        with (
            mock.patch.object(
                nx,
                "degree_pearson_correlation_coefficient",
                side_effect=AssertionError(
                    "NetworkX degree_pearson_correlation_coefficient fallback used"
                ),
            ),
            mock.patch.object(
                nx,
                "generalized_degree",
                side_effect=AssertionError("NetworkX generalized_degree fallback used"),
            ),
        ):
            actual_corr = fnx.degree_pearson_correlation_coefficient(
                digraph,
                x="in",
                y="out",
            )
            actual_generalized = fnx.generalized_degree(graph)

        if math.isnan(expected_corr):
            assert math.isnan(actual_corr)
        else:
            assert actual_corr == expected_corr
        assert actual_generalized == expected_generalized

    @needs_nx
    def test_load_centrality_matches_networkx_weighted_contract(self):
        graph = fnx.MultiGraph()
        graph.add_edge(0, 1, key=7, weight=2)
        graph.add_edge(2, 1, key=8, weight=3)
        graph.add_edge(2, 3, key=9, weight=4)

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge(0, 1, key=7, weight=2)
        expected_graph.add_edge(2, 1, key=8, weight=3)
        expected_graph.add_edge(2, 3, key=9, weight=4)

        expected = nx.load_centrality(
            expected_graph,
            normalized=False,
            weight="weight",
        )
        with mock.patch.object(
            nx,
            "load_centrality",
            side_effect=AssertionError("NetworkX load_centrality fallback used"),
        ):
            actual = fnx.load_centrality(graph, normalized=False, weight="weight")

        assert actual == expected

    def test_backend_can_run_rejects_incompatible_signatures(self):
        from franken_networkx.backend import BackendInterface

        graph = fnx.path_graph(4)

        assert BackendInterface.can_run("shortest_path", (graph,), {})
        assert not BackendInterface.can_run("shortest_path", (), {})
        assert not BackendInterface.can_run("node_connectivity", (graph, 0, 3, "extra"), {})
        assert (
            not BackendInterface.can_run(
                "average_shortest_path_length",
                (graph,),
                {"method": "dijkstra"},
            )
        )
        assert BackendInterface.should_run("shortest_path", (graph,), {})
        assert not BackendInterface.should_run("shortest_path", (), {})
        assert not BackendInterface.should_run("node_connectivity", (graph, 0, 3, "extra"), {})
        assert (
            not BackendInterface.should_run(
                "average_shortest_path_length",
                (graph,),
                {"method": "dijkstra"},
            )
        )

    @needs_nx
    def test_harary_and_havel_hakimi_wrappers_match_networkx(self):
        hakimi = fnx.havel_hakimi_graph([3, 3, 2, 2, 2], create_using=fnx.Graph())
        expected_hakimi = nx.havel_hakimi_graph([3, 3, 2, 2, 2], create_using=nx.Graph())
        hkn = fnx.hkn_harary_graph(2, 6, create_using=fnx.Graph())
        expected_hkn = nx.hkn_harary_graph(2, 6, create_using=nx.Graph())
        hnm = fnx.hnm_harary_graph(6, 6, create_using=fnx.Graph())
        expected_hnm = nx.hnm_harary_graph(6, 6, create_using=nx.Graph())
        hkn_directed = fnx.hkn_harary_graph(2, 6, create_using=fnx.DiGraph())
        expected_hkn_directed = nx.hkn_harary_graph(2, 6, create_using=nx.DiGraph())
        hnm_multigraph = fnx.hnm_harary_graph(6, 6, create_using=fnx.MultiGraph())
        expected_hnm_multigraph = nx.hnm_harary_graph(6, 6, create_using=nx.MultiGraph())

        assert sorted(hakimi.edges()) == sorted(expected_hakimi.edges())
        assert sorted(hkn.edges()) == sorted(expected_hkn.edges())
        assert sorted(hnm.edges()) == sorted(expected_hnm.edges())
        assert sorted(hkn_directed.edges()) == sorted(expected_hkn_directed.edges())
        assert sorted(hnm_multigraph.edges(keys=True)) == sorted(
            expected_hnm_multigraph.edges(keys=True)
        )

    @needs_nx
    def test_barabasi_albert_supports_initial_graph_fallback(self):
        initial = fnx.path_graph(3)
        expected_initial = nx.path_graph(3)

        graph = fnx.barabasi_albert_graph(6, 1, seed=42, initial_graph=initial)
        expected = nx.barabasi_albert_graph(6, 1, seed=42, initial_graph=expected_initial)

        assert sorted(graph.edges()) == sorted(expected.edges())

    @needs_nx
    def test_grid_2d_graph_supports_periodic_fallback(self):
        graph = fnx.grid_2d_graph(2, 3, periodic=True)
        expected = nx.grid_2d_graph(2, 3, periodic=True)

        assert sorted(graph.edges()) == sorted(expected.edges())

    def test_gnp_random_graph_supports_directed_fallback(self):
        directed = fnx.gnp_random_graph(8, 0.2, seed=42, directed=True)
        er_directed = fnx.erdos_renyi_graph(8, 0.2, seed=42, directed=True)
        fast_directed = fnx.fast_gnp_random_graph(8, 0.2, seed=42, directed=True)

        assert directed.is_directed()
        assert er_directed.is_directed()
        assert fast_directed.is_directed()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class TestMisc:
    def test_non_neighbors(self):
        G = fnx.path_graph(4)
        nn = list(fnx.non_neighbors(G, 0))
        assert 2 in nn
        assert 3 in nn
        assert 1 not in nn  # 1 IS a neighbor

    def test_number_of_cliques(self):
        G = fnx.complete_graph(4)
        nc = fnx.number_of_cliques(G)
        assert isinstance(nc, (dict, int))

    @needs_nx
    def test_maximum_spanning_tree(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1.0)
        G.add_edge(1, 2, weight=3.0)
        G.add_edge(0, 2, weight=2.0)
        mst = fnx.maximum_spanning_tree(G)
        assert mst.number_of_edges() == 2


class TestDelegateFixes:
    @needs_nx
    def test_graph_operator_batches_match_networkx_without_fallback(self):
        empty_func_names = [
            "compose_all",
            "union_all",
            "intersection_all",
            "disjoint_union_all",
        ]
        for name in empty_func_names:
            with pytest.raises(ValueError):
                getattr(nx, name)([])

        left = fnx.MultiGraph()
        left.graph["left"] = 1
        left.add_node("a", color="red")
        left.add_edge("a", "b", key=7, weight=2)

        right = fnx.MultiGraph()
        right.graph["right"] = 2
        right.add_node("c", color="blue")
        right.add_edge("c", "d", key=3, cost=4)

        left_nx = nx.MultiGraph()
        left_nx.graph["left"] = 1
        left_nx.add_node("a", color="red")
        left_nx.add_edge("a", "b", key=7, weight=2)

        right_nx = nx.MultiGraph()
        right_nx.graph["right"] = 2
        right_nx.add_node("c", color="blue")
        right_nx.add_edge("c", "d", key=3, cost=4)

        composed_nx = nx.compose_all([left_nx, right_nx])
        unioned_nx = nx.union_all([left_nx, right_nx], rename=("L-", "R-"))
        disjoint_nx = nx.disjoint_union_all([left_nx, right_nx])

        with (
            mock.patch.object(
                nx,
                "compose_all",
                side_effect=AssertionError("fnx.compose_all fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "union_all",
                side_effect=AssertionError("fnx.union_all fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "intersection_all",
                side_effect=AssertionError("fnx.intersection_all fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "disjoint_union_all",
                side_effect=AssertionError(
                    "fnx.disjoint_union_all fell back to networkx"
                ),
            ),
        ):
            for name in empty_func_names:
                with pytest.raises(ValueError):
                    getattr(fnx, name)([])

            composed = fnx.compose_all([left, right])
            unioned = fnx.union_all([left, right], rename=("L-", "R-"))
            disjoint = fnx.disjoint_union_all([left, right])

        assert composed.is_multigraph()
        assert dict(composed.graph) == composed_nx.graph
        assert sorted(composed.edges(keys=True, data=True)) == sorted(
            composed_nx.edges(keys=True, data=True)
        )

        assert unioned.is_multigraph()
        assert dict(unioned.graph) == unioned_nx.graph
        assert sorted(unioned.edges(keys=True, data=True)) == sorted(
            unioned_nx.edges(keys=True, data=True)
        )

        assert disjoint.is_multigraph()
        assert dict(disjoint.graph) == disjoint_nx.graph
        assert sorted(disjoint.edges(keys=True, data=True)) == sorted(
            disjoint_nx.edges(keys=True, data=True)
        )

    @needs_nx
    def test_conversion_helpers_preserve_multigraph_keys_and_graph_attrs(self):
        graph_nx = nx.MultiGraph()
        graph_nx.graph["name"] = "demo"
        graph_nx.add_edge("a", "b", key=9, weight=4)

        converted = fnx.readwrite._from_nx_graph(graph_nx)
        assert dict(converted.graph) == graph_nx.graph
        assert sorted(converted["a"]["b"].keys()) == [9]

        roundtrip = fnx.drawing.layout._to_nx(converted)
        assert roundtrip.graph == graph_nx.graph
        assert sorted(roundtrip["a"]["b"].keys()) == [9]

    @needs_nx
    def test_disjoint_union_and_relabel_helpers_match_networkx_without_fallback(self):
        left = fnx.MultiGraph()
        left.graph["left"] = 1
        left.add_edge("a", "b", key=7, weight=2)

        right = fnx.MultiGraph()
        right.graph["right"] = 2
        right.add_edge("c", "d", key=3, cost=4)

        left_nx = nx.MultiGraph()
        left_nx.graph["left"] = 1
        left_nx.add_edge("a", "b", key=7, weight=2)

        right_nx = nx.MultiGraph()
        right_nx.graph["right"] = 2
        right_nx.add_edge("c", "d", key=3, cost=4)

        disjoint_nx = nx.disjoint_union(left_nx, right_nx)

        graph = fnx.Graph()
        graph.graph["name"] = "base"
        graph.add_edge("a", "b", weight=1)

        expected_graph = nx.Graph()
        expected_graph.graph["name"] = "base"
        expected_graph.add_edge("a", "b", weight=1)
        relabeled_nx = nx.relabel_nodes(expected_graph, {"a": "x"})
        converted_nx = nx.convert_node_labels_to_integers(
            expected_graph,
            label_attribute="old",
        )

        with (
            mock.patch.object(
                nx,
                "disjoint_union",
                side_effect=AssertionError("fnx.disjoint_union fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "relabel_nodes",
                side_effect=AssertionError("fnx.relabel_nodes fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "convert_node_labels_to_integers",
                side_effect=AssertionError(
                    "fnx.convert_node_labels_to_integers fell back to networkx"
                ),
            ),
        ):
            disjoint = fnx.disjoint_union(left, right)
            relabeled = fnx.relabel_nodes(graph, {"a": "x"})
            converted = fnx.convert_node_labels_to_integers(
                graph,
                label_attribute="old",
            )

        assert disjoint.is_multigraph()
        assert dict(disjoint.graph) == disjoint_nx.graph
        assert sorted(disjoint.edges(keys=True, data=True)) == sorted(
            disjoint_nx.edges(keys=True, data=True)
        )

        assert dict(relabeled.graph) == dict(graph.graph)
        assert sorted((frozenset((u, v)), data) for u, v, data in relabeled.edges(data=True)) == sorted(
            (frozenset((u, v)), data) for u, v, data in relabeled_nx.edges(data=True)
        )

        assert dict(converted.graph) == dict(graph.graph)
        assert sorted(converted.edges(data=True)) == sorted(converted_nx.edges(data=True))
        assert sorted(converted.nodes(data=True)) == sorted(converted_nx.nodes(data=True))

    @needs_nx
    def test_line_graph_reverse_and_empty_copy_match_networkx_without_fallback(self):
        graph = fnx.MultiGraph()
        graph.graph["name"] = "multi"
        graph.add_edge("a", "b", key=5, weight=2)

        graph_nx = nx.MultiGraph()
        graph_nx.graph["name"] = "multi"
        graph_nx.add_edge("a", "b", key=5, weight=2)

        line_nx = nx.line_graph(graph_nx)
        empty_nx = nx.create_empty_copy(graph_nx)

        digraph = fnx.MultiDiGraph()
        digraph.graph["kind"] = "digraph"
        digraph.add_edge("u", "v", key=9, capacity=4)

        digraph_nx = nx.MultiDiGraph()
        digraph_nx.graph["kind"] = "digraph"
        digraph_nx.add_edge("u", "v", key=9, capacity=4)

        reversed_nx = nx.reverse(digraph_nx)

        with (
            mock.patch.object(
                nx,
                "line_graph",
                side_effect=AssertionError("fnx.line_graph fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "create_empty_copy",
                side_effect=AssertionError("fnx.create_empty_copy fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "reverse",
                side_effect=AssertionError("fnx.reverse fell back to networkx"),
            ),
        ):
            line = fnx.line_graph(graph)
            empty = fnx.create_empty_copy(graph)
            reversed_graph = fnx.reverse(digraph)

        assert type(line).__name__ == type(line_nx).__name__
        assert sorted(line.nodes(data=True)) == sorted(line_nx.nodes(data=True))
        assert sorted(line.edges(data=True)) == sorted(line_nx.edges(data=True))

        assert dict(empty.graph) == empty_nx.graph
        assert sorted(empty.nodes(data=True)) == sorted(empty_nx.nodes(data=True))
        assert empty.number_of_edges() == empty_nx.number_of_edges()

        assert dict(reversed_graph.graph) == reversed_nx.graph
        assert sorted(reversed_graph.edges(keys=True, data=True)) == sorted(
            reversed_nx.edges(keys=True, data=True)
        )

    @needs_nx
    def test_directed_undirected_conversion_and_freeze_match_networkx_without_fallback(self):
        graph = fnx.MultiGraph()
        graph.graph["name"] = "base"
        graph.add_node("a", color="red")
        graph.add_edge("a", "b", key=4, weight=2)

        graph_nx = nx.MultiGraph()
        graph_nx.graph["name"] = "base"
        graph_nx.add_node("a", color="red")
        graph_nx.add_edge("a", "b", key=4, weight=2)

        directed_nx = nx.to_directed(graph_nx)
        undirected_nx = nx.to_undirected(directed_nx)
        expected_frozen = nx.freeze(nx.Graph())
        expected_is_frozen = nx.is_frozen(expected_frozen)
        graph_to_freeze = fnx.Graph()

        with (
            mock.patch.object(
                nx,
                "to_directed",
                side_effect=AssertionError("fnx.to_directed fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "to_undirected",
                side_effect=AssertionError("fnx.to_undirected fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "freeze",
                side_effect=AssertionError("fnx.freeze fell back to networkx"),
            ),
            mock.patch.object(
                nx,
                "is_frozen",
                side_effect=AssertionError("fnx.is_frozen fell back to networkx"),
            ),
        ):
            directed = fnx.to_directed(graph)
            undirected = fnx.to_undirected(directed)
            frozen = fnx.freeze(graph_to_freeze)
            actual_is_frozen = fnx.is_frozen(frozen)

        assert directed.is_directed()
        assert directed.is_multigraph()
        assert dict(directed.graph) == directed_nx.graph
        assert sorted(directed.nodes(data=True)) == sorted(directed_nx.nodes(data=True))
        assert sorted(directed.edges(keys=True, data=True)) == sorted(
            directed_nx.edges(keys=True, data=True)
        )

        assert not undirected.is_directed()
        assert undirected.is_multigraph()
        assert dict(undirected.graph) == undirected_nx.graph
        assert sorted(undirected.nodes(data=True)) == sorted(undirected_nx.nodes(data=True))
        assert sorted(undirected.edges(keys=True, data=True)) == sorted(
            undirected_nx.edges(keys=True, data=True)
        )

        assert frozen is graph_to_freeze
        assert actual_is_frozen == expected_is_frozen
        assert getattr(frozen, "frozen", False) == getattr(expected_frozen, "frozen", False)
        with pytest.raises(fnx.NetworkXError, match="Frozen graph can't be modified"):
            frozen.add_edge(1, 2)

    @needs_nx
    def test_graph_products_match_networkx_without_fallback_for_multigraph_attrs(self):
        left = fnx.MultiGraph()
        left.add_node(0, a1=True)
        left.add_edge(0, 1, key=7, w=2)

        right = fnx.MultiGraph()
        right.add_node("a", a2="Spam")
        right.add_edge("a", "b", key=3, c=4)

        left_nx = nx.MultiGraph()
        left_nx.add_node(0, a1=True)
        left_nx.add_edge(0, 1, key=7, w=2)

        right_nx = nx.MultiGraph()
        right_nx.add_node("a", a2="Spam")
        right_nx.add_edge("a", "b", key=3, c=4)

        for name in (
            "cartesian_product",
            "tensor_product",
            "strong_product",
            "lexicographic_product",
        ):
            expected = getattr(nx, name)(left_nx, right_nx)

            with mock.patch.object(
                nx,
                name,
                side_effect=AssertionError(f"NetworkX {name} fallback used"),
            ):
                graph = getattr(fnx, name)(left, right)

            assert graph.is_multigraph()
            assert sorted(graph.nodes(data=True)) == sorted(expected.nodes(data=True))
            assert sorted((u, v, data) for u, v, _, data in graph.edges(keys=True, data=True)) == sorted(
                (u, v, data) for u, v, _, data in expected.edges(keys=True, data=True)
            )

    @needs_nx
    def test_corona_rooted_and_modular_products_match_networkx_without_fallback(self):
        def canonical_nodes(graph):
            return sorted(
                ((repr(node), node_data) for node, node_data in graph.nodes(data=True)),
                key=lambda item: item[0],
            )

        def canonical_edges(graph):
            return sorted(
                (
                    tuple(sorted((repr(u), repr(v)))),
                    edge_data,
                )
                for u, v, edge_data in graph.edges(data=True)
            )

        left = fnx.Graph()
        left.add_node(0, color="red")
        left.add_edge(0, 1, weight=2)

        right = fnx.Graph()
        right.add_node("a", label="A")
        right.add_edge("a", "b", cost=3)

        left_nx = nx.Graph()
        left_nx.add_node(0, color="red")
        left_nx.add_edge(0, 1, weight=2)

        right_nx = nx.Graph()
        right_nx.add_node("a", label="A")
        right_nx.add_edge("a", "b", cost=3)

        corona_nx = nx.corona_product(left_nx, right_nx)
        with mock.patch.object(
            nx,
            "corona_product",
            side_effect=AssertionError("NetworkX corona_product fallback used"),
        ):
            corona = fnx.corona_product(left, right)
        assert canonical_nodes(corona) == canonical_nodes(corona_nx)
        assert canonical_edges(corona) == canonical_edges(corona_nx)

        rooted_nx = nx.rooted_product(left_nx, right_nx, "a")
        with mock.patch.object(
            nx,
            "rooted_product",
            side_effect=AssertionError("NetworkX rooted_product fallback used"),
        ):
            rooted = fnx.rooted_product(left, right, "a")
        assert canonical_nodes(rooted) == canonical_nodes(rooted_nx)
        assert canonical_edges(rooted) == canonical_edges(rooted_nx)

        modular_nx = nx.modular_product(left_nx, right_nx)
        with mock.patch.object(
            nx,
            "modular_product",
            side_effect=AssertionError("NetworkX modular_product fallback used"),
        ):
            modular = fnx.modular_product(left, right)
        assert canonical_nodes(modular) == canonical_nodes(modular_nx)
        assert canonical_edges(modular) == canonical_edges(modular_nx)

    @needs_nx
    def test_from_nx_graph_handles_non_integer_multigraph_keys(self):
        graph_nx = nx.MultiGraph()
        graph_nx.add_edge("a", "b", key=("left", "right"), weight=7)

        converted = fnx.readwrite._from_nx_graph(graph_nx)

        assert converted.is_multigraph()
        assert converted.number_of_edges("a", "b") == 1
        assert next(iter(converted["a"]["b"].values()))["weight"] == 7

    @needs_nx
    def test_graph_atlas_helpers_match_networkx(self):
        atlas_nx = nx.graph_atlas(6)
        atlas_all_nx = nx.graph_atlas_g()
        sample_indices = [0, 1, 6, 7, 208, 1252]
        expected_samples = [
            (
                graph.name,
                sorted(graph.nodes()),
                sorted(graph.edges()),
            )
            for graph in (atlas_all_nx[index] for index in sample_indices)
        ]

        with (
            mock.patch.object(
                nx,
                "graph_atlas",
                side_effect=AssertionError("NetworkX graph_atlas fallback used"),
            ),
            mock.patch.object(
                nx,
                "graph_atlas_g",
                side_effect=AssertionError("NetworkX graph_atlas_g fallback used"),
            ),
        ):
            atlas = fnx.graph_atlas(6)
            atlas_all = fnx.graph_atlas_g()

        assert atlas.name == atlas_nx.name
        assert sorted(atlas.nodes()) == sorted(atlas_nx.nodes())
        assert sorted(atlas.edges()) == sorted(atlas_nx.edges())
        assert len(atlas_all) == len(atlas_all_nx)
        assert [
            (
                graph.name,
                sorted(graph.nodes()),
                sorted(graph.edges()),
            )
            for graph in (atlas_all[index] for index in sample_indices)
        ] == expected_samples

        with pytest.raises(ValueError, match="index must be between 0 and 1253"):
            fnx.graph_atlas(-1)
        with pytest.raises(ValueError, match="index must be between 0 and 1253"):
            fnx.graph_atlas(1253)

    @needs_nx
    def test_random_shell_and_clustered_generators_match_networkx_without_fallback(self):
        shell_constructor = [(4, 8, 0.8)]
        shell_nx = nx.random_shell_graph(shell_constructor, seed=1)
        clustered_sequence = [(1, 0), (1, 0), (1, 0), (1, 0)]
        clustered_nx = nx.random_clustered_graph(clustered_sequence, seed=1)

        with (
            mock.patch.object(
                nx,
                "random_shell_graph",
                side_effect=AssertionError("NetworkX random_shell_graph fallback used"),
            ),
            mock.patch.object(
                nx,
                "random_clustered_graph",
                side_effect=AssertionError("NetworkX random_clustered_graph fallback used"),
            ),
        ):
            shell = fnx.random_shell_graph(shell_constructor, seed=1)
            clustered = fnx.random_clustered_graph(clustered_sequence, seed=1)

        assert sorted(shell.edges()) == sorted(shell_nx.edges())
        assert clustered.number_of_nodes() == clustered_nx.number_of_nodes()
        assert clustered.number_of_edges() == clustered_nx.number_of_edges()

    @needs_nx
    def test_spectral_graph_forge_and_edit_distance_match_networkx_without_fallback(self):
        graph = fnx.path_graph(5)
        forged_nx = nx.spectral_graph_forge(nx.path_graph(5), alpha=0.5, seed=1)
        expected_distance = nx.graph_edit_distance(
            nx.path_graph(3), nx.path_graph(4)
        )
        expected_optimal_cost = nx.optimal_edit_paths(
            nx.path_graph(3),
            nx.path_graph(3),
        )[1]
        expected_iter_cost = next(
            nx.optimize_edit_paths(nx.path_graph(3), nx.path_graph(3))
        )[2]

        with (
            mock.patch.object(
                nx,
                "spectral_graph_forge",
                side_effect=AssertionError("NetworkX spectral_graph_forge fallback used"),
            ),
            mock.patch.object(
                nx,
                "graph_edit_distance",
                side_effect=AssertionError("NetworkX graph_edit_distance fallback used"),
            ),
            mock.patch.object(
                nx,
                "optimal_edit_paths",
                side_effect=AssertionError("NetworkX optimal_edit_paths fallback used"),
            ),
            mock.patch.object(
                nx,
                "optimize_edit_paths",
                side_effect=AssertionError("NetworkX optimize_edit_paths fallback used"),
            ),
        ):
            forged = fnx.spectral_graph_forge(graph, alpha=0.5, seed=1)
            actual_distance = fnx.graph_edit_distance(
                fnx.path_graph(3),
                fnx.path_graph(4),
            )
            actual_optimal_cost = fnx.optimal_edit_paths(
                fnx.path_graph(3),
                fnx.path_graph(3),
            )[1]
            actual_iter_cost = next(
                fnx.optimize_edit_paths(fnx.path_graph(3), fnx.path_graph(3))
            )[2]

        assert forged.number_of_nodes() == forged_nx.number_of_nodes()
        assert actual_distance == expected_distance
        assert actual_optimal_cost == expected_optimal_cost
        assert actual_iter_cost == expected_iter_cost

    @needs_nx
    def test_embedding_and_matplotlib_color_helpers_match_networkx_without_fallback(self):
        embedding = nx.PlanarEmbedding()
        embedding.add_half_edge_cw(0, 1, None)
        embedding.add_half_edge_cw(1, 0, None)
        embedding.add_half_edge_cw(1, 2, 0)
        embedding.add_half_edge_cw(2, 1, None)
        embedding.check_structure()
        expected_pos = nx.combinatorial_embedding_to_pos(embedding)

        mpl = pytest.importorskip("matplotlib")
        graph = fnx.path_graph(3)
        expected_graph = nx.path_graph(3)
        for node, value in enumerate([0.0, 0.5, 1.0]):
            graph.nodes[node]["score"] = value
            expected_graph.nodes[node]["score"] = value
        nx.apply_matplotlib_colors(expected_graph, "score", "rgba", mpl.cm.viridis)
        expected_colors = [
            expected_graph.nodes[node]["rgba"] for node in expected_graph.nodes()
        ]

        with (
            mock.patch.object(
                nx,
                "combinatorial_embedding_to_pos",
                side_effect=AssertionError(
                    "NetworkX combinatorial_embedding_to_pos fallback used"
                ),
            ),
            mock.patch.object(
                nx,
                "apply_matplotlib_colors",
                side_effect=AssertionError(
                    "NetworkX apply_matplotlib_colors fallback used"
                ),
            ),
        ):
            pos = fnx.combinatorial_embedding_to_pos(embedding)
            fnx.apply_matplotlib_colors(graph, "score", "rgba", mpl.cm.viridis)

        assert set(pos) == set(expected_pos) == {0, 1, 2}
        assert [graph.nodes[node]["rgba"] for node in graph.nodes()] == expected_colors

    @needs_nx
    def test_combinatorial_embedding_to_pos_matches_networkx_without_fallback(self, monkeypatch):
        _, embedding = nx.check_planarity(nx.complete_graph(4))
        expected = nx.combinatorial_embedding_to_pos(embedding)

        def fail(*args, **kwargs):
            raise AssertionError("networkx combinatorial embedding fallback was used")

        monkeypatch.setattr(nx, "combinatorial_embedding_to_pos", fail)

        assert fnx.combinatorial_embedding_to_pos(embedding) == expected

    @needs_nx
    @pytest.mark.parametrize("fully_triangulate", [False, True])
    def test_combinatorial_embedding_to_pos_relabels_match_networkx_without_fallback(
        self,
        fully_triangulate,
        monkeypatch,
    ):
        labels = [
            ("hub", 0),
            ("rim", 1),
            ("rim", 2),
            ("rim", 3),
            ("rim", 4),
            ("rim", 5),
        ]
        relabeling = dict(enumerate(labels))

        expected_graph = nx.relabel_nodes(nx.wheel_graph(6), relabeling)
        actual_graph = fnx.relabel_nodes(fnx.wheel_graph(6), relabeling)
        expected_planar, expected_embedding = nx.check_planarity(expected_graph)
        actual_planar, actual_embedding = fnx.check_planarity(actual_graph)
        expected = nx.combinatorial_embedding_to_pos(
            expected_embedding,
            fully_triangulate=fully_triangulate,
        )

        def fail(*args, **kwargs):
            raise AssertionError("networkx combinatorial embedding fallback was used")

        monkeypatch.setattr(nx, "combinatorial_embedding_to_pos", fail)

        assert actual_planar == expected_planar
        assert actual_planar
        assert (
            fnx.combinatorial_embedding_to_pos(
                actual_embedding,
                fully_triangulate=fully_triangulate,
            )
            == expected
        )

    @needs_nx
    def test_equitable_coloring_and_goldberg_radzik_match_networkx_without_fallback(self):
        expected_coloring = nx.equitable_color(nx.cycle_graph(4), 3)

        graph = fnx.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, -2), (0, 2, 4)])
        expected_graph = nx.DiGraph()
        expected_graph.add_weighted_edges_from([(0, 1, 1), (1, 2, -2), (0, 2, 4)])
        expected = nx.goldberg_radzik(expected_graph, 0)

        with (
            mock.patch.object(
                nx,
                "equitable_color",
                side_effect=AssertionError("NetworkX equitable_color fallback used"),
            ),
            mock.patch.object(
                nx,
                "goldberg_radzik",
                side_effect=AssertionError("NetworkX goldberg_radzik fallback used"),
            ),
        ):
            coloring = fnx.equitable_color(fnx.cycle_graph(4), 3)
            actual = fnx.goldberg_radzik(graph, 0)

        assert coloring == expected_coloring
        assert actual == expected

    @needs_nx
    def test_random_degree_sequence_and_edit_distance_iter_match_networkx_without_fallback(self):
        sequence = [2, 2, 2, 2]
        expected = nx.random_degree_sequence_graph(sequence, seed=1)
        expected_edit_distances = list(
            nx.optimize_graph_edit_distance(nx.path_graph(3), nx.path_graph(3))
        )

        with (
            mock.patch.object(
                nx,
                "random_degree_sequence_graph",
                side_effect=AssertionError(
                    "NetworkX random_degree_sequence_graph fallback used"
                ),
            ),
            mock.patch.object(
                nx,
                "optimize_graph_edit_distance",
                side_effect=AssertionError(
                    "NetworkX optimize_graph_edit_distance fallback used"
                ),
            ),
        ):
            graph = fnx.random_degree_sequence_graph(sequence, seed=1)
            actual_edit_distances = list(
                fnx.optimize_graph_edit_distance(
                    fnx.path_graph(3),
                    fnx.path_graph(3),
                )
            )

        assert sorted(graph.degree[node] for node in graph.nodes()) == sorted(
            degree for _, degree in expected.degree()
        )
        assert actual_edit_distances == expected_edit_distances

    @needs_nx
    def test_neighbors_and_describe_match_networkx_without_fallback(self, capsys):
        graph = fnx.path_graph(3)
        expected_graph = nx.path_graph(3)

        expected_neighbors = tuple(nx.neighbors(expected_graph, 1))
        nx.describe(expected_graph)
        expected_out = capsys.readouterr().out

        with (
            mock.patch.object(
                nx,
                "neighbors",
                side_effect=AssertionError("NetworkX neighbors fallback used"),
            ),
            mock.patch.object(
                nx,
                "describe",
                side_effect=AssertionError("NetworkX describe fallback used"),
            ),
        ):
            neighbors = fnx.neighbors(graph, 1)
            assert iter(neighbors) is neighbors
            actual_neighbors = tuple(neighbors)
            assert fnx.describe(graph) is None

        out = capsys.readouterr().out
        assert actual_neighbors == expected_neighbors
        assert out == expected_out

    @needs_nx
    def test_mixing_and_resistance_helpers_match_networkx_without_to_nx_fallback(self):
        expected_mixing = nx.mixing_dict(
            [(1, 2), (1, 2), (2, 3)],
            normalized=True,
        )

        graph = fnx.path_graph(4)
        expected_graph = nx.path_graph(4)
        expected_constraint = nx.local_constraint(expected_graph, 1, 0)
        expected_communicability = nx.communicability_exp(expected_graph)
        expected_resistance = nx.effective_graph_resistance(expected_graph)

        with (
            mock.patch.object(
                nx,
                "mixing_dict",
                side_effect=AssertionError("NetworkX mixing_dict fallback used"),
            ),
            mock.patch.object(
                nx,
                "local_constraint",
                side_effect=AssertionError("NetworkX local_constraint fallback used"),
            ),
            mock.patch.object(
                nx,
                "communicability_exp",
                side_effect=AssertionError("NetworkX communicability_exp fallback used"),
            ),
            mock.patch.object(
                nx,
                "effective_graph_resistance",
                side_effect=AssertionError("NetworkX effective_graph_resistance fallback used"),
            ),
            mock.patch(
                "franken_networkx.drawing.layout._to_nx",
                side_effect=AssertionError("_to_nx fallback should not be used"),
            ),
        ):
            actual_mixing = fnx.mixing_dict([(1, 2), (1, 2), (2, 3)], normalized=True)
            actual_constraint = fnx.local_constraint(graph, 1, 0)
            actual_communicability = fnx.communicability_exp(graph)
            actual_resistance = fnx.effective_graph_resistance(graph)

        assert actual_mixing == expected_mixing
        assert actual_constraint == expected_constraint
        assert actual_communicability == expected_communicability
        assert actual_resistance == expected_resistance

    @needs_nx
    def test_cd_index_matches_networkx_without_to_nx_fallback(self):
        graph = fnx.DiGraph()
        expected_graph = nx.DiGraph()

        edges = [(0, 1), (0, 2), (3, 0), (4, 0), (3, 1)]
        graph.add_edges_from(edges)
        expected_graph.add_edges_from(edges)

        node_attrs = {
            0: {"time": datetime(2020, 1, 1)},
            1: {"time": datetime(2019, 1, 1)},
            2: {"time": datetime(2019, 6, 1)},
            3: {"time": datetime(2020, 2, 1), "weight": 2},
            4: {"time": datetime(2020, 3, 1), "weight": 4},
        }
        for node, attrs in node_attrs.items():
            graph.nodes[node].update(attrs)
            expected_graph.nodes[node].update(attrs)

        delta = timedelta(days=400)
        expected = nx.cd_index(expected_graph, 0, delta)
        expected_weighted = nx.cd_index(expected_graph, 0, delta, weight="weight")
        with (
            mock.patch.object(
                nx,
                "cd_index",
                side_effect=AssertionError("NetworkX cd_index fallback used"),
            ),
            mock.patch(
                "franken_networkx.drawing.layout._to_nx",
                side_effect=AssertionError("_to_nx fallback should not be used"),
            ),
        ):
            actual = fnx.cd_index(graph, 0, delta)
            actual_weighted = fnx.cd_index(graph, 0, delta, weight="weight")

        assert actual == expected
        assert actual_weighted == expected_weighted

    @needs_nx
    def test_panther_helpers_match_networkx_without_to_nx_fallback(self):
        graph = fnx.path_graph(4)
        expected_graph = nx.path_graph(4)
        expected_similarity = nx.panther_similarity(expected_graph, 0, k=3, seed=1)
        expected_vector_similarity = nx.panther_vector_similarity(
            expected_graph,
            0,
            D=3,
            k=3,
            seed=1,
        )

        def fail(*args, **kwargs):
            raise AssertionError("NetworkX Panther fallback should not be used")

        with mock.patch(
            "franken_networkx.drawing.layout._to_nx",
            side_effect=AssertionError("_to_nx fallback should not be used"),
        ), mock.patch.object(nx, "panther_similarity", fail), mock.patch.object(
            nx,
            "panther_vector_similarity",
            fail,
        ):
            assert fnx.panther_similarity(graph, 0, k=3, seed=1) == expected_similarity

            with pytest.raises(fnx.NetworkXUnfeasible):
                fnx.panther_vector_similarity(graph, 0, k=5, seed=1)

            assert fnx.panther_vector_similarity(
                graph,
                0,
                D=3,
                k=3,
                seed=1,
            ) == expected_vector_similarity
