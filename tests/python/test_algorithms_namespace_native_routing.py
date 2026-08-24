"""``franken_networkx.algorithms`` flattened names route to fnx natives.

``from networkx.algorithms import *`` flattens networkx's functions into the
``franken_networkx.algorithms`` namespace, so
``from franken_networkx.algorithms import connected_components`` resolved to
nx's implementation wherever fnx has a native ``fnx.connected_components``.
A dynamic routing pass now rebinds every such flattened name to fnx's native
(functions via call-time wrappers, classes via direct alias).

br-r37-c1-nhbni
"""

from __future__ import annotations

import importlib.util
import inspect
import math
import sys
from functools import lru_cache
from pathlib import Path

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms as fnx_algorithms

# Representative sample across domains.
_SAMPLE_FUNCS = [
    "connected_components", "adamic_adar_index", "wiener_index",
    "betweenness_centrality", "pagerank", "find_cliques", "is_chordal",
    "topological_sort", "maximum_flow", "node_connectivity",
    "transitivity", "triangles", "minimum_spanning_edges", "equitable_color",
    "greedy_color",
]
_CLASSES = [
    "ArborescenceIterator", "EdgePartition", "NetworkXTreewidthBoundExceeded",
    "SpanningTreeIterator",
]
_FLATTENED_LINK_PREDICTION_NAMES = [
    "resource_allocation_index",
    "jaccard_coefficient",
    "adamic_adar_index",
    "preferential_attachment",
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "within_inter_cluster",
    "common_neighbor_centrality",
]
_FLATTENED_CUT_NAMES = [
    "boundary_expansion",
    "conductance",
    "cut_size",
    "edge_expansion",
    "mixing_expansion",
    "node_expansion",
    "normalized_cut_size",
    "volume",
]
_FLATTENED_WEIGHTED_SHORTEST_PATH_NAMES = [
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
    "all_pairs_dijkstra",
    "all_pairs_dijkstra_path",
    "all_pairs_dijkstra_path_length",
    "bellman_ford_path",
    "bellman_ford_path_length",
    "bellman_ford_predecessor_and_distance",
    "bidirectional_dijkstra",
    "dijkstra_path",
    "dijkstra_path_length",
    "dijkstra_predecessor_and_distance",
    "find_negative_cycle",
    "goldberg_radzik",
    "johnson",
    "multi_source_dijkstra",
    "multi_source_dijkstra_path",
    "multi_source_dijkstra_path_length",
    "negative_edge_cycle",
    "single_source_bellman_ford",
    "single_source_bellman_ford_path",
    "single_source_bellman_ford_path_length",
    "single_source_dijkstra",
    "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
]
_FLATTENED_DAG_NAMES = [
    "all_topological_sorts",
    "ancestors",
    "antichains",
    "dag_longest_path",
    "dag_longest_path_length",
    "dag_to_branching",
    "descendants",
    "is_aperiodic",
    "is_directed_acyclic_graph",
    "lexicographical_topological_sort",
    "topological_generations",
    "topological_sort",
    "transitive_closure",
    "transitive_closure_dag",
    "transitive_reduction",
]
_FLATTENED_EFFICIENCY_NAMES = [
    "efficiency",
    "global_efficiency",
    "local_efficiency",
]
_FLATTENED_ISOMORPHISM_NAMES = [
    "is_isomorphic",
    "could_be_isomorphic",
    "fast_could_be_isomorphic",
    "faster_could_be_isomorphic",
    "vf2pp_is_isomorphic",
    "vf2pp_isomorphism",
    "vf2pp_all_isomorphisms",
]
_FLATTENED_CLUSTER_NAMES = [
    "triangles",
    "all_triangles",
    "average_clustering",
    "clustering",
    "transitivity",
    "square_clustering",
    "generalized_degree",
]
_FLATTENED_ASSORTATIVITY_NAMES = [
    "attribute_assortativity_coefficient",
    "attribute_mixing_dict",
    "attribute_mixing_matrix",
    "average_degree_connectivity",
    "average_neighbor_degree",
    "degree_assortativity_coefficient",
    "degree_mixing_dict",
    "degree_mixing_matrix",
    "degree_pearson_correlation_coefficient",
    "mixing_dict",
    "node_attribute_xy",
    "node_degree_xy",
    "numeric_assortativity_coefficient",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_algorithms_surface"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_no_flattened_function_still_bound_to_networkx():
    # After routing, no flattened *function* in __all__ should still be nx's
    # while fnx has a native version. (Submodule references like
    # ``community``/``connectivity`` are modules, not functions, and are out of
    # scope for this function-level routing.)
    still = []
    for name in fnx_algorithms.__all__:
        if name.startswith("_"):
            continue
        fa = getattr(fnx_algorithms, name, None)
        fx = getattr(fnx, name, None)
        nxo = getattr(nx, name, None)
        if fa is None or fx is None or nxo is None:
            continue
        if inspect.ismodule(fx):
            continue
        if fa is nxo and fx is not nxo:
            still.append(name)
    assert still == [], f"still nx-bound: {still[:20]}"


@pytest.mark.parametrize("name", _SAMPLE_FUNCS)
def test_sample_function_routed(name):
    assert getattr(fnx_algorithms, name) is not getattr(nx, name)


@pytest.mark.parametrize("name", _CLASSES)
def test_class_routed_to_fnx(name):
    assert getattr(fnx_algorithms, name) is getattr(fnx, name)
    assert getattr(fnx_algorithms, name) is not getattr(nx, name)


def test_routed_function_values_match_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
    ng = nx.Graph(list(g.edges()))
    assert sorted(map(sorted, fnx_algorithms.connected_components(g))) == (
        sorted(map(sorted, nx.connected_components(ng)))
    )
    assert fnx_algorithms.wiener_index(fnx.complete_graph(4)) == (
        nx.wiener_index(nx.complete_graph(4))
    )
    assert fnx_algorithms.transitivity(g) == pytest.approx(nx.transitivity(ng))


@pytest.mark.parametrize("name", _FLATTENED_ISOMORPHISM_NAMES)
def test_flattened_isomorphism_signature_and_results_match_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(3)
    legacy_graph = legacy.path_graph(3)
    actual_value = actual(graph, graph)
    expected_value = expected(legacy_graph, legacy_graph)
    if name == "vf2pp_all_isomorphisms":
        assert list(actual_value) == list(expected_value)
    else:
        assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, graph, backend="missing")


@pytest.mark.parametrize("name", _FLATTENED_ISOMORPHISM_NAMES)
def test_flattened_isomorphism_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("left", "right")
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx_algorithms.isomorphism, name, sentinel)
    assert getattr(fnx_algorithms, name)("left", "right", flag=True) is marker


@pytest.mark.parametrize("name", _FLATTENED_CLUSTER_NAMES)
def test_flattened_cluster_signature_and_results_match_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.complete_graph(4)
    legacy_graph = legacy.complete_graph(4)
    actual_value = actual(graph)
    expected_value = expected(legacy_graph)
    if name == "all_triangles":
        assert list(actual_value) == list(expected_value)
    else:
        assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, backend="missing")


@pytest.mark.parametrize("name", _FLATTENED_CLUSTER_NAMES)
def test_flattened_cluster_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx_algorithms.cluster, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph", flag=True) is marker


@pytest.mark.parametrize("name", _FLATTENED_ASSORTATIVITY_NAMES)
def test_flattened_assortativity_signature_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))


@pytest.mark.parametrize("name", _FLATTENED_ASSORTATIVITY_NAMES)
def test_flattened_assortativity_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("payload",)
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx_algorithms.assortativity, name, sentinel)
    assert getattr(fnx_algorithms, name)("payload", flag=True) is marker


def test_flattened_assortativity_values_and_backend_rejection_match_oracle():
    legacy = _legacy_networkx()
    graph = fnx.Graph([(0, 1), (0, 2), (0, 3), (3, 4)])
    legacy_graph = legacy.Graph(list(graph.edges()))
    attributes = {0: "hub", 1: "leaf", 2: "leaf", 3: "middle", 4: "leaf"}
    fnx.set_node_attributes(graph, attributes, "kind")
    legacy.set_node_attributes(legacy_graph, attributes, "kind")

    assert fnx_algorithms.attribute_mixing_dict(graph, "kind") == (
        legacy.algorithms.attribute_mixing_dict(legacy_graph, "kind")
    )
    assert fnx_algorithms.average_neighbor_degree(graph) == pytest.approx(
        legacy.algorithms.average_neighbor_degree(legacy_graph)
    )
    assert list(fnx_algorithms.node_attribute_xy(graph, "kind")) == list(
        legacy.algorithms.node_attribute_xy(legacy_graph, "kind")
    )
    assert fnx_algorithms.mixing_dict([(1, 2), (1, 2), (2, 1)]) == (
        legacy.algorithms.mixing_dict([(1, 2), (1, 2), (2, 1)])
    )

    with pytest.raises(ImportError):
        fnx_algorithms.degree_assortativity_coefficient(graph, backend="missing")


@pytest.mark.parametrize("name", _FLATTENED_LINK_PREDICTION_NAMES)
def test_flattened_link_prediction_signature_matches_legacy_networkx(name):
    legacy = _legacy_networkx()
    assert str(inspect.signature(getattr(fnx_algorithms, name))) == str(
        inspect.signature(getattr(legacy.algorithms, name))
    )


@pytest.mark.parametrize("name", _FLATTENED_LINK_PREDICTION_NAMES)
def test_flattened_link_prediction_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("payload",)
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx_algorithms.link_prediction, name, sentinel)
    assert getattr(fnx_algorithms, name)("payload", flag=True) is marker


@pytest.mark.parametrize("name", _FLATTENED_CUT_NAMES)
def test_flattened_cuts_signature_matches_legacy_networkx(name):
    legacy = _legacy_networkx()
    assert str(inspect.signature(getattr(fnx_algorithms, name))) == str(
        inspect.signature(getattr(legacy.algorithms, name))
    )


@pytest.mark.parametrize("name", _FLATTENED_CUT_NAMES)
def test_flattened_cuts_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("payload",)
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx_algorithms.cuts, name, sentinel)
    assert getattr(fnx_algorithms, name)("payload", flag=True) is marker


@pytest.mark.parametrize("name", _FLATTENED_WEIGHTED_SHORTEST_PATH_NAMES)
def test_flattened_weighted_shortest_path_signature_matches_legacy_networkx(name):
    legacy = _legacy_networkx()
    assert str(inspect.signature(getattr(fnx_algorithms, name))) == str(
        inspect.signature(getattr(legacy.algorithms, name))
    )


@pytest.mark.parametrize("name", _FLATTENED_WEIGHTED_SHORTEST_PATH_NAMES)
def test_flattened_weighted_shortest_path_routes_to_fnx(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("payload",)
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx, name, sentinel)
    assert getattr(fnx_algorithms, name)("payload", flag=True) is marker


@pytest.mark.parametrize("name", _FLATTENED_DAG_NAMES)
def test_flattened_dag_signature_matches_legacy_networkx(name):
    legacy = _legacy_networkx()
    assert str(inspect.signature(getattr(fnx_algorithms, name))) == str(
        inspect.signature(getattr(legacy.algorithms, name))
    )


@pytest.mark.parametrize("name", _FLATTENED_DAG_NAMES)
def test_flattened_dag_routes_to_fnx(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("payload",)
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx, name, sentinel)
    assert getattr(fnx_algorithms, name)("payload", flag=True) is marker


@pytest.mark.parametrize("name", ["equitable_color", "greedy_color"])
def test_coloring_namespace_signature_and_backend_contract_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx, name)
    actual_shape = inspect.signature(actual)
    expected_shape = inspect.signature(expected)
    assert str(actual_shape) in {str(expected_shape)}

    graph = fnx.path_graph(2)
    nx_graph = nx.path_graph(2)
    if name == "equitable_color":
        assert actual(graph, 2) == expected(nx_graph, 2)
    else:
        assert actual(graph, strategy="largest_first") == expected(
            nx_graph, strategy="largest_first"
        )

    with pytest.raises(ImportError):
        actual(graph, 2, backend="missing") if name == "equitable_color" else actual(
            graph, backend="missing"
        )


@pytest.mark.parametrize(
    "name",
    [
        "asyn_lpa_communities",
        "fast_label_propagation_communities",
        "is_partition",
        "partition_quality",
    ],
)
def test_community_namespace_dispatch_contract_matches_oracle(name):
    actual = getattr(fnx_algorithms.community, name)
    expected = getattr(nx.algorithms.community, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.path_graph(3)
    nx_graph = nx.path_graph(3)
    partition = [{0, 1, 2}]
    if name in {"asyn_lpa_communities", "fast_label_propagation_communities"}:
        actual_value = {frozenset(group) for group in actual(graph, seed=7)}
        expected_value = {frozenset(group) for group in expected(nx_graph, seed=7)}
    else:
        actual_value = actual(graph, partition, backend="networkx")
        expected_value = expected(nx_graph, partition, backend="networkx")
    assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, backend="missing") if name.endswith("communities") else actual(
            graph, partition, backend="missing"
        )
    with pytest.raises(TypeError):
        actual(graph, unexpected=True) if name.endswith("communities") else actual(
            graph, partition, unexpected=True
        )


@pytest.mark.parametrize(
    "name",
    [
        "contracted_edge",
        "contracted_nodes",
        "identified_nodes",
        "equivalence_classes",
        "quotient_graph",
    ],
)
def test_minors_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx.algorithms, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    relation = lambda left, right: (left - right) % 2 == 0
    if name == "equivalence_classes":
        actual_value = actual([1, 2, 3, 4], relation)
        expected_value = expected([1, 2, 3, 4], relation)
        assert actual_value == expected_value
        with pytest.raises(TypeError):
            actual([1, 2], relation, unexpected=True)
        return

    graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)
    if name == "contracted_edge":
        actual_graph = actual(graph, (1, 2), backend="networkx")
        expected_graph = expected(nx_graph, (1, 2), backend="networkx")
    elif name in {"contracted_nodes", "identified_nodes"}:
        actual_graph = actual(graph, 1, 2, backend="networkx")
        expected_graph = expected(nx_graph, 1, 2, backend="networkx")
    else:
        partition = [{0, 1}, {2, 3}]
        actual_graph = actual(graph, partition, backend="networkx")
        expected_graph = expected(nx_graph, partition, backend="networkx")

    assert set(actual_graph) == set(expected_graph)
    assert {frozenset(edge) for edge in actual_graph.edges} == {
        frozenset(edge) for edge in expected_graph.edges
    }

    with pytest.raises(ImportError):
        if name == "contracted_edge":
            actual(graph, (1, 2), backend="missing")
        elif name in {"contracted_nodes", "identified_nodes"}:
            actual(graph, 1, 2, backend="missing")
        else:
            actual(graph, [{0, 1}, {2, 3}], backend="missing")


def test_isolates_namespace_signature_and_results_match_oracle():
    actual = fnx_algorithms.isolates
    expected = nx.algorithms.isolates
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.Graph([(0, 1)])
    graph.add_nodes_from([2, 3])
    nx_graph = nx.Graph([(0, 1)])
    nx_graph.add_nodes_from([2, 3])
    assert list(actual(graph, backend="networkx")) == list(
        expected(nx_graph, backend="networkx")
    )

    with pytest.raises(ImportError):
        list(actual(graph, backend="missing"))
    with pytest.raises(TypeError):
        list(actual(graph, unexpected=True))


@pytest.mark.parametrize("name", ["triad_type", "triadic_census", "triads_by_type"])
def test_triads_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx.algorithms, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    nx_graph = nx.DiGraph(graph.edges())
    if name == "triad_type":
        actual_value = actual(fnx.DiGraph([(0, 1), (1, 2)]), backend="networkx")
        expected_value = expected(nx.DiGraph([(0, 1), (1, 2)]), backend="networkx")
    elif name == "triadic_census":
        actual_value = actual(graph, nodelist=[0, 1], backend="networkx")
        expected_value = expected(nx_graph, nodelist=[0, 1], backend="networkx")
    else:
        actual_value = {
            kind: [set(triad) for triad in triads]
            for kind, triads in actual(graph, backend="networkx").items()
        }
        expected_value = {
            kind: [set(triad) for triad in triads]
            for kind, triads in expected(nx_graph, backend="networkx").items()
        }
    assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, backend="missing")


@pytest.mark.parametrize("name", ["core_number", "k_truss"])
def test_core_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.core, name)
    expected = getattr(nx.algorithms.core, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.cycle_graph(4)
    nx_graph = nx.cycle_graph(4)
    if name == "core_number":
        actual_value = actual(graph, backend="networkx")
        expected_value = expected(nx_graph, backend="networkx")
    else:
        actual_value = actual(graph, 2, backend="networkx")
        expected_value = expected(nx_graph, 2, backend="networkx")
    if name == "core_number":
        assert actual_value == expected_value
    else:
        assert set(actual_value) == set(expected_value)
        assert {frozenset(edge) for edge in actual_value.edges} == {
            frozenset(edge) for edge in expected_value.edges
        }

    with pytest.raises(ImportError):
        actual(graph, backend="missing") if name == "core_number" else actual(
            graph, 2, backend="missing"
        )


def test_flattened_core_number_signature_matches_oracle():
    actual = fnx_algorithms.core_number
    expected = nx.algorithms.core_number
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}
    assert actual(fnx.cycle_graph(4), backend="networkx") == expected(
        nx.cycle_graph(4), backend="networkx"
    )


@pytest.mark.parametrize(
    "name",
    [
        "is_chordal",
        "find_induced_nodes",
        "chordal_graph_cliques",
        "chordal_graph_treewidth",
    ],
)
def test_chordal_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.chordal, name)
    expected = getattr(nx.algorithms.chordal, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.complete_graph(3)
    nx_graph = nx.complete_graph(3)
    if name == "find_induced_nodes":
        actual_value = actual(graph, 0, 1, backend="networkx")
        expected_value = expected(nx_graph, 0, 1, backend="networkx")
    else:
        actual_value = actual(graph, backend="networkx")
        expected_value = expected(nx_graph, backend="networkx")
    if name == "chordal_graph_cliques":
        assert {frozenset(clique) for clique in actual_value} == {
            frozenset(clique) for clique in expected_value
        }
    else:
        assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, backend="missing") if name != "find_induced_nodes" else actual(
            graph, 0, 1, backend="missing"
        )


@pytest.mark.parametrize("name", ["chordal_graph_cliques", "chordal_graph_treewidth"])
def test_flattened_chordal_signatures_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx.algorithms, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}
    graph = fnx.complete_graph(3)
    nx_graph = nx.complete_graph(3)
    if name == "chordal_graph_cliques":
        assert {frozenset(clique) for clique in actual(graph, backend="networkx")} == {
            frozenset(clique) for clique in expected(nx_graph, backend="networkx")
        }
    else:
        assert actual(graph, backend="networkx") == expected(
            nx_graph, backend="networkx"
        )


@pytest.mark.parametrize(
    "name",
    [
        "articulation_points",
        "biconnected_component_edges",
        "biconnected_components",
        "connected_components",
        "is_biconnected",
        "is_connected",
        "node_connected_component",
        "number_connected_components",
    ],
)
def test_undirected_components_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.components, name)
    expected = getattr(nx.algorithms.components, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.Graph([(0, 1), (1, 2), (3, 4)])
    nx_graph = nx.Graph([(0, 1), (1, 2), (3, 4)])
    actual_value = (
        actual(graph, 0, backend="networkx")
        if name == "node_connected_component"
        else actual(graph, backend="networkx")
    )
    expected_value = (
        expected(nx_graph, 0, backend="networkx")
        if name == "node_connected_component"
        else expected(nx_graph, backend="networkx")
    )
    if name in {"connected_components", "biconnected_components"}:
        assert {frozenset(component) for component in actual_value} == {
            frozenset(component) for component in expected_value
        }
    elif name == "biconnected_component_edges":
        assert {
            frozenset(frozenset(edge) for edge in component)
            for component in actual_value
        } == {
            frozenset(frozenset(edge) for edge in component)
            for component in expected_value
        }
    elif name == "articulation_points":
        assert list(actual_value) == list(expected_value)
    else:
        assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, 0, backend="missing") if name == "node_connected_component" else actual(
            graph, backend="missing"
        )


@pytest.mark.parametrize(
    "name",
    [
        "attracting_components",
        "is_attracting_component",
        "is_semiconnected",
        "is_strongly_connected",
        "is_weakly_connected",
        "kosaraju_strongly_connected_components",
        "number_attracting_components",
        "number_strongly_connected_components",
        "number_weakly_connected_components",
        "strongly_connected_components",
        "weakly_connected_components",
    ],
)
def test_directed_components_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.components, name)
    expected = getattr(nx.algorithms.components, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.DiGraph([(0, 1), (1, 0), (1, 2), (2, 3), (3, 2)])
    nx_graph = nx.DiGraph(graph.edges())
    actual_value = actual(graph, backend="networkx")
    expected_value = expected(nx_graph, backend="networkx")
    component_listers = {
        "attracting_components",
        "kosaraju_strongly_connected_components",
        "strongly_connected_components",
        "weakly_connected_components",
    }
    if name in component_listers:
        assert {frozenset(component) for component in actual_value} == {
            frozenset(component) for component in expected_value
        }
    else:
        assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, backend="missing")


@pytest.mark.parametrize("name", ["is_arborescence", "is_branching", "is_forest", "is_tree"])
def test_tree_predicate_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.tree, name)
    expected = getattr(nx.algorithms.tree, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    if name in {"is_arborescence", "is_branching"}:
        graph = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
        nx_graph = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    else:
        graph = fnx.path_graph(4)
        nx_graph = nx.path_graph(4)
    assert actual(graph, backend="networkx") == expected(
        nx_graph, backend="networkx"
    )
    with pytest.raises(ImportError):
        actual(graph, backend="missing")


@pytest.mark.parametrize(
    "name",
    ["local_node_connectivity", "local_edge_connectivity", "is_locally_k_edge_connected"],
)
def test_local_connectivity_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.connectivity, name)
    expected = getattr(nx.algorithms.connectivity, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.cycle_graph(4)
    nx_graph = nx.cycle_graph(4)
    if name == "is_locally_k_edge_connected":
        actual_value = actual(graph, 0, 2, 2, backend="networkx")
        expected_value = expected(nx_graph, 0, 2, 2, backend="networkx")
    else:
        actual_value = actual(graph, 0, 2, backend="networkx")
        expected_value = expected(nx_graph, 0, 2, backend="networkx")
    assert actual_value == expected_value

    with pytest.raises(ImportError):
        if name == "is_locally_k_edge_connected":
            actual(graph, 0, 2, 2, backend="missing")
        else:
            actual(graph, 0, 2, backend="missing")


@pytest.mark.parametrize("name", ["maximum_spanning_edges", "minimum_spanning_edges"])
def test_spanning_edges_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.tree, name)
    expected = getattr(nx.algorithms.tree, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.Graph()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 3), (0, 2, 2)])
    nx_graph = nx.Graph()
    nx_graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 3), (0, 2, 2)])
    assert list(actual(graph, backend="networkx")) == list(
        expected(nx_graph, backend="networkx")
    )
    with pytest.raises(ImportError):
        list(actual(graph, backend="missing"))


@pytest.mark.parametrize(
    "name",
    [
        "maximum_branching",
        "minimum_branching",
        "maximum_spanning_arborescence",
        "minimum_spanning_arborescence",
    ],
)
def test_branching_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.tree, name)
    expected = getattr(nx.algorithms.tree, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    edges = [(0, 1, 2), (0, 2, 1), (1, 2, 3), (2, 1, 1)]
    graph = fnx.DiGraph()
    graph.add_weighted_edges_from(edges)
    nx_graph = nx.DiGraph()
    nx_graph.add_weighted_edges_from(edges)
    actual_value = actual(graph, backend="networkx")
    expected_value = expected(nx_graph, backend="networkx")
    assert set(actual_value) == set(expected_value)
    assert set(actual_value.edges) == set(expected_value.edges)
    with pytest.raises(ImportError):
        actual(graph, backend="missing")


@pytest.mark.parametrize("name", ["to_nested_tuple", "to_prufer_sequence"])
def test_tree_coding_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.tree, name)
    expected = getattr(nx.algorithms.tree, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)
    if name == "to_nested_tuple":
        actual_value = actual(graph, 0, canonical_form=True, backend="networkx")
        expected_value = expected(nx_graph, 0, canonical_form=True, backend="networkx")
        missing_call = lambda: actual(graph, 0, backend="missing")
    else:
        actual_value = actual(graph, backend="networkx")
        expected_value = expected(nx_graph, backend="networkx")
        missing_call = lambda: actual(graph, backend="missing")
    assert actual_value == expected_value
    with pytest.raises(ImportError):
        missing_call()


def test_spanning_tree_count_namespace_signature_and_results_match_oracle():
    actual = fnx_algorithms.tree.number_of_spanning_trees
    expected = nx.algorithms.tree.number_of_spanning_trees
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    # NetworkX computes this through a floating-point determinant. On K4 its
    # own result is 16.000000000000007 rather than the exact count 16, so the
    # only permitted slack is that measured oracle roundoff—not a broad test
    # tolerance. The epsilon bound makes the derivation auditable.
    nx_count = expected(nx.complete_graph(4), backend="networkx")
    oracle_roundoff = abs(nx_count - round(nx_count))
    assert oracle_roundoff <= 8 * math.ulp(float(nx_count))
    assert actual(fnx.complete_graph(4), backend="networkx") == pytest.approx(
        nx_count, abs=oracle_roundoff, rel=0
    )

    # A tree has one spanning tree and neither implementation needs a
    # determinant-roundoff allowance for this integer-exact case.
    assert actual(fnx.path_graph(4), backend="networkx") == expected(
        nx.path_graph(4), backend="networkx"
    ) == 1.0
    with pytest.raises(ImportError):
        actual(fnx.complete_graph(4), backend="missing")


@pytest.mark.parametrize("name", ["bfs_edges", "bfs_predecessors", "bfs_successors", "bfs_tree"])
def test_flattened_bfs_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx.algorithms, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)
    actual_value = actual(graph, 0, backend="networkx")
    expected_value = expected(nx_graph, 0, backend="networkx")
    if name == "bfs_tree":
        assert set(actual_value) == set(expected_value)
        assert set(actual_value.edges) == set(expected_value.edges)
    else:
        assert list(actual_value) == list(expected_value)
    with pytest.raises(ImportError):
        actual(graph, 0, backend="missing")


@pytest.mark.parametrize("name", ["dfs_edges", "dfs_predecessors", "dfs_successors", "dfs_tree"])
def test_flattened_dfs_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx.algorithms, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)
    actual_value = actual(graph, 0, backend="networkx")
    expected_value = expected(nx_graph, 0, backend="networkx")
    if name == "dfs_tree":
        assert set(actual_value) == set(expected_value)
        assert set(actual_value.edges) == set(expected_value.edges)
    else:
        assert list(actual_value) == list(expected_value)
    with pytest.raises(ImportError):
        actual(graph, 0, backend="missing")


@pytest.mark.parametrize("name", ["edge_bfs", "edge_dfs"])
def test_flattened_edge_traversal_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx.algorithms, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)
    assert list(actual(graph, 0, backend="networkx")) == list(
        expected(nx_graph, 0, backend="networkx")
    )
    with pytest.raises(ImportError):
        actual(graph, 0, backend="missing")


@pytest.mark.parametrize(
    "name", ["dfs_preorder_nodes", "dfs_postorder_nodes", "dfs_labeled_edges"]
)
def test_flattened_dfs_ordering_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms, name)
    expected = getattr(nx.algorithms, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)
    assert list(actual(graph, 0, backend="networkx")) == list(
        expected(nx_graph, 0, backend="networkx")
    )
    with pytest.raises(ImportError):
        actual(graph, 0, backend="missing")


@pytest.mark.parametrize("name", _FLATTENED_EFFICIENCY_NAMES)
def test_flattened_efficiency_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(3)
    legacy_graph = legacy.path_graph(3)
    if name == "efficiency":
        actual_value = actual(graph, 0, 2)
        expected_value = expected(legacy_graph, 0, 2)
        missing_call = lambda: actual(graph, 0, 2, backend="missing")
        unexpected_call = lambda: actual(graph, 0, 2, unexpected=True)
    else:
        actual_value = actual(graph)
        expected_value = expected(legacy_graph)
        missing_call = lambda: actual(graph, backend="missing")
        unexpected_call = lambda: actual(graph, unexpected=True)
    assert actual_value == pytest.approx(expected_value)

    with pytest.raises(ImportError):
        missing_call()
    with pytest.raises(TypeError):
        unexpected_call()


@pytest.mark.parametrize("name", _FLATTENED_EFFICIENCY_NAMES)
def test_flattened_efficiency_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert kwargs == {"backend": None}
        return marker

    monkeypatch.setattr(fnx_algorithms.efficiency_measures, name, sentinel)
    if name == "efficiency":
        assert fnx_algorithms.efficiency("graph", "u", "v") is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize("name", ["has_bridges", "local_bridges"])
def test_flattened_bridges_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name == "has_bridges":
        actual_value = actual(graph)
        expected_value = expected(legacy_graph)
        missing_call = lambda: actual(graph, backend="missing")
        unexpected_call = lambda: actual(graph, unexpected=True)
    else:
        actual_value = list(actual(graph, with_span=False))
        expected_value = list(expected(legacy_graph, with_span=False))
        missing_call = lambda: list(actual(graph, backend="missing"))
        unexpected_call = lambda: list(actual(graph, unexpected=True))
    assert actual_value == expected_value

    with pytest.raises(ImportError):
        missing_call()
    with pytest.raises(TypeError):
        unexpected_call()


@pytest.mark.parametrize("name", ["has_bridges", "local_bridges"])
def test_flattened_bridges_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.bridges, name, sentinel)
    if name == "has_bridges":
        assert fnx_algorithms.has_bridges("graph") is marker
    else:
        assert fnx_algorithms.local_bridges("graph") is marker


@pytest.mark.parametrize("name", ["edge_boundary", "node_boundary"])
def test_flattened_boundary_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name == "edge_boundary":
        actual_value = list(actual(graph, [0, 1], data="weight", default=-1))
        expected_value = list(
            expected(legacy_graph, [0, 1], data="weight", default=-1)
        )
        missing_call = lambda: list(actual(graph, [0, 1], backend="missing"))
        unexpected_call = lambda: list(actual(graph, [0, 1], unexpected=True))
    else:
        actual_value = actual(graph, [0, 1])
        expected_value = expected(legacy_graph, [0, 1])
        missing_call = lambda: actual(graph, [0, 1], backend="missing")
        unexpected_call = lambda: actual(graph, [0, 1], unexpected=True)
    assert actual_value == expected_value

    with pytest.raises(ImportError):
        missing_call()
    with pytest.raises(TypeError):
        unexpected_call()


@pytest.mark.parametrize("name", ["edge_boundary", "node_boundary"])
def test_flattened_boundary_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph", "left")
        return marker

    monkeypatch.setattr(fnx_algorithms.boundary, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph", "left") is marker


@pytest.mark.parametrize("name", ["tree_broadcast_center", "tree_broadcast_time"])
def test_flattened_broadcasting_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.balanced_tree(2, 2)
    legacy_graph = legacy.balanced_tree(2, 2)
    if name == "tree_broadcast_center":
        actual_value = actual(graph)
        expected_value = expected(legacy_graph)
        missing_call = lambda: actual(graph, backend="missing")
        unexpected_call = lambda: actual(graph, unexpected=True)
    else:
        actual_value = actual(graph, node=0)
        expected_value = expected(legacy_graph, node=0)
        missing_call = lambda: actual(graph, backend="missing")
        unexpected_call = lambda: actual(graph, unexpected=True)
    assert actual_value == expected_value

    with pytest.raises(ImportError):
        missing_call()
    with pytest.raises(TypeError):
        unexpected_call()


@pytest.mark.parametrize("name", ["tree_broadcast_center", "tree_broadcast_time"])
def test_flattened_broadcasting_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.broadcasting, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    ("name", "args", "kwargs"),
    [
        ("is_graphical", ([3, 3, 2, 2, 2],), {"method": "hh"}),
        ("is_graphical", ([3, 3, 3],), {}),
        ("is_digraphical", ([1, 1, 1], [1, 1, 1]), {}),
        ("is_digraphical", ([2, 1], [1, 1]), {}),
    ],
)
def test_flattened_graphical_namespace_matches_legacy_oracle(name, args, kwargs):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))
    assert actual(*args, **kwargs) == expected(*args, **kwargs)

    with pytest.raises(ImportError):
        actual(*args, backend="missing")
    with pytest.raises(TypeError):
        actual(*args, unexpected=True)


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("is_graphical", ("sequence",)),
        ("is_digraphical", ("in-sequence", "out-sequence")),
    ],
)
def test_flattened_graphical_namespace_routes_to_leaf_module(monkeypatch, name, args):
    marker = object()

    def sentinel(*call_args, **kwargs):
        assert call_args == args
        return marker

    monkeypatch.setattr(fnx_algorithms.graphical, name, sentinel)
    assert getattr(fnx_algorithms, name)(*args) is marker


@pytest.mark.parametrize("name", ["is_isolate", "number_of_isolates"])
def test_flattened_isolate_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.Graph()
    graph.add_edge("left", "right")
    graph.add_node("alone")
    legacy_graph = legacy.Graph()
    legacy_graph.add_edge("left", "right")
    legacy_graph.add_node("alone")
    args = (graph, "alone") if name == "is_isolate" else (graph,)
    legacy_args = (legacy_graph, "alone") if name == "is_isolate" else (legacy_graph,)
    assert actual(*args) == expected(*legacy_args)

    with pytest.raises(ImportError):
        actual(*args, backend="missing")
    with pytest.raises(TypeError):
        actual(*args, unexpected=True)


@pytest.mark.parametrize(
    ("name", "args"),
    [("is_isolate", ("graph", "node")), ("number_of_isolates", ("graph",))],
)
def test_flattened_isolate_namespace_routes_to_leaf_module(monkeypatch, name, args):
    marker = object()

    def sentinel(*call_args, **kwargs):
        assert call_args == args
        return marker

    monkeypatch.setattr(fnx_algorithms.isolate, name, sentinel)
    assert getattr(fnx_algorithms, name)(*args) is marker


def test_flattened_bfs_reachability_namespace_signatures_and_results_match_oracle():
    graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    actual_layers = fnx_algorithms.bfs_layers
    expected_layers = nx.algorithms.bfs_layers
    assert str(inspect.signature(actual_layers)) in {str(inspect.signature(expected_layers))}
    assert list(actual_layers(graph, [0], backend="networkx")) == list(
        expected_layers(nx_graph, [0], backend="networkx")
    )
    with pytest.raises(ImportError):
        actual_layers(graph, [0], backend="missing")

    actual_descendants = fnx_algorithms.descendants_at_distance
    expected_descendants = nx.algorithms.descendants_at_distance
    assert str(inspect.signature(actual_descendants)) in {
        str(inspect.signature(expected_descendants))
    }
    assert actual_descendants(graph, 0, 2, backend="networkx") == expected_descendants(
        nx_graph, 0, 2, backend="networkx"
    )
    with pytest.raises(ImportError):
        actual_descendants(graph, 0, 2, backend="missing")


@pytest.mark.parametrize(
    "name",
    ["edge_connectivity", "node_connectivity", "minimum_edge_cut", "minimum_node_cut"],
)
def test_global_connectivity_namespace_signature_and_results_match_oracle(name):
    actual = getattr(fnx_algorithms.connectivity, name)
    expected = getattr(nx.algorithms.connectivity, name)
    assert str(inspect.signature(actual)) in {str(inspect.signature(expected))}

    graph = fnx.cycle_graph(4)
    nx_graph = nx.cycle_graph(4)
    actual_value = actual(graph, 0, 2, backend="networkx")
    expected_value = expected(nx_graph, 0, 2, backend="networkx")
    assert actual_value == expected_value

    with pytest.raises(ImportError):
        actual(graph, 0, 2, backend="missing")
