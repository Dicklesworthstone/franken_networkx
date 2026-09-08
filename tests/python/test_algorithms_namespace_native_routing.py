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
        ("is_multigraphical", ([2, 2, 2],), {}),
        ("is_pseudographical", ([2, 2, 2],), {}),
        ("is_valid_degree_sequence_erdos_gallai", ([2, 2, 2],), {}),
        ("is_valid_degree_sequence_havel_hakimi", ([2, 2, 2],), {}),
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
        ("is_multigraphical", ("sequence",)),
        ("is_pseudographical", ("sequence",)),
        ("is_valid_degree_sequence_erdos_gallai", ("deg-sequence",)),
        ("is_valid_degree_sequence_havel_hakimi", ("deg-sequence",)),
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


_FLATTENED_WIENER_NAMES = [
    "wiener_index",
    "schultz_index",
    "gutman_index",
    "hyper_wiener_index",
]


@pytest.mark.parametrize("name", _FLATTENED_WIENER_NAMES)
def test_flattened_wiener_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize("name", _FLATTENED_WIENER_NAMES)
def test_flattened_wiener_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.wiener, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


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


@pytest.mark.parametrize("name", ["is_at_free", "find_asteroidal_triple"])
def test_flattened_asteroidal_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize("name", ["is_at_free", "find_asteroidal_triple"])
def test_flattened_asteroidal_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.asteroidal, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize("name", ["communicability", "communicability_exp"])
def test_flattened_communicability_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(3)
    legacy_graph = legacy.path_graph(3)
    actual_val = actual(graph)
    expected_val = expected(legacy_graph)
    for u in actual_val:
        for v in actual_val[u]:
            assert actual_val[u][v] == pytest.approx(expected_val[u][v])

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize("name", ["communicability", "communicability_exp"])
def test_flattened_communicability_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.communicability_alg, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


def test_flattened_chains_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.chain_decomposition
    expected = legacy.algorithms.chain_decomposition
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    assert list(actual(graph)) == list(expected(legacy_graph))

    with pytest.raises(ImportError):
        list(actual(graph, backend="missing"))
    with pytest.raises(TypeError):
        list(actual(graph, unexpected=True))


def test_flattened_chains_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.chains, "chain_decomposition", sentinel)
    assert fnx_algorithms.chain_decomposition("graph") is marker


@pytest.mark.parametrize("name", ["chromatic_polynomial", "tutte_polynomial"])
def test_flattened_polynomials_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(3)
    legacy_graph = legacy.path_graph(3)
    try:
        expected_val = expected(legacy_graph)
    except ModuleNotFoundError:
        with pytest.raises(ModuleNotFoundError):
            actual(graph)
    else:
        assert actual(graph) == expected_val

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize("name", ["chromatic_polynomial", "tutte_polynomial"])
def test_flattened_polynomials_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.polynomials, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


def test_flattened_richclub_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.rich_club_coefficient
    expected = legacy.algorithms.rich_club_coefficient
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph, normalized=False) == expected(legacy_graph, normalized=False)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


def test_flattened_richclub_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.richclub, "rich_club_coefficient", sentinel)
    assert fnx_algorithms.rich_club_coefficient("graph") is marker


def test_flattened_smetric_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.s_metric
    expected = legacy.algorithms.s_metric
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


def test_flattened_smetric_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.smetric, "s_metric", sentinel)
    assert fnx_algorithms.s_metric("graph") is marker


@pytest.mark.parametrize("name", ["constraint", "local_constraint", "effective_size"])
def test_flattened_structuralholes_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name == "local_constraint":
        assert actual(graph, 0, 1) == pytest.approx(expected(legacy_graph, 0, 1))
        with pytest.raises(ImportError):
            actual(graph, 0, 1, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 0, 1, unexpected=True)
    else:
        actual_val = actual(graph)
        expected_val = expected(legacy_graph)
        for n in actual_val:
            assert actual_val[n] == pytest.approx(expected_val[n])
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)


@pytest.mark.parametrize("name", ["constraint", "local_constraint", "effective_size"])
def test_flattened_structuralholes_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.structuralholes, name, sentinel)
    if name == "local_constraint":
        assert getattr(fnx_algorithms, name)("graph", 0, 1) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


def test_flattened_voronoi_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.voronoi_cells
    expected = legacy.algorithms.voronoi_cells
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph, [0]) == expected(legacy_graph, [0])

    with pytest.raises(ImportError):
        actual(graph, [0], backend="missing")
    with pytest.raises(TypeError):
        actual(graph, [0], unexpected=True)


def test_flattened_voronoi_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph", [0])
        return marker

    monkeypatch.setattr(fnx_algorithms.voronoi, "voronoi_cells", sentinel)
    assert fnx_algorithms.voronoi_cells("graph", [0]) is marker


def test_flattened_vitality_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.closeness_vitality
    expected = legacy.algorithms.closeness_vitality
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph, 0) == expected(legacy_graph, 0)

    with pytest.raises(ImportError):
        actual(graph, 0, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, 0, unexpected=True)


def test_flattened_vitality_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        assert kwargs.get("node") == 0
        return marker

    monkeypatch.setattr(fnx_algorithms.vitality, "closeness_vitality", sentinel)
    assert fnx_algorithms.closeness_vitality("graph", 0) is marker


def test_flattened_walks_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.number_of_walks
    expected = legacy.algorithms.number_of_walks
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph, 2) == expected(legacy_graph, 2)

    with pytest.raises(ImportError):
        actual(graph, 2, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, 2, unexpected=True)


def test_flattened_walks_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph", 2)
        return marker

    monkeypatch.setattr(fnx_algorithms.walks, "number_of_walks", sentinel)
    assert fnx_algorithms.number_of_walks("graph", 2) is marker


def test_flattened_moral_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.moral_graph
    expected = legacy.algorithms.moral_graph
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    legacy_dg = legacy.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert sorted(actual(dg).edges()) == sorted(expected(legacy_dg).edges())

    with pytest.raises(ImportError):
        actual(dg, backend="missing")
    with pytest.raises(TypeError):
        actual(dg, unexpected=True)


def test_flattened_moral_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.moral, "moral_graph", sentinel)
    assert fnx_algorithms.moral_graph("graph") is marker


@pytest.mark.parametrize("name", ["all_triads", "is_triad"])
def test_flattened_triads_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1), (1, 2)])
    legacy_dg = legacy.DiGraph([(0, 1), (1, 2)])
    if name == "all_triads":
        actual_edges = [sorted(g.edges()) for g in actual(dg)]
        expected_edges = [sorted(g.edges()) for g in expected(legacy_dg)]
        assert actual_edges == expected_edges
        with pytest.raises(ImportError):
            list(actual(dg, backend="missing"))
        with pytest.raises(TypeError):
            list(actual(dg, unexpected=True))
    else:
        assert actual(dg) == expected(legacy_dg)
        with pytest.raises(ImportError):
            actual(dg, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, unexpected=True)


@pytest.mark.parametrize("name", ["all_triads", "is_triad"])
def test_flattened_triads_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.triads, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    ["complete_to_chordal_graph", "find_induced_nodes", "is_chordal"],
)
def test_flattened_chordal_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name == "find_induced_nodes":
        assert actual(graph, 0, 3) == expected(legacy_graph, 0, 3)
        with pytest.raises(ImportError):
            actual(graph, 0, 3, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 0, 3, unexpected=True)
    elif name == "complete_to_chordal_graph":
        act_g, act_alpha = actual(graph)
        exp_g, exp_alpha = expected(legacy_graph)
        assert sorted(act_g.edges()) == sorted(exp_g.edges())
        assert act_alpha == exp_alpha
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)
    else:
        assert actual(graph) == expected(legacy_graph)
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    ["complete_to_chordal_graph", "find_induced_nodes", "is_chordal"],
)
def test_flattened_chordal_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.chordal, name, sentinel)
    if name == "find_induced_nodes":
        assert fnx_algorithms.find_induced_nodes("graph", 0, 3) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize("name", ["is_kl_connected", "kl_connected_subgraph"])
def test_flattened_hybrid_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name == "is_kl_connected":
        assert actual(graph, 1, 1) == expected(legacy_graph, 1, 1)
        with pytest.raises(ImportError):
            actual(graph, 1, 1, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 1, 1, unexpected=True)
    else:
        assert sorted(actual(graph, 1, 1).edges()) == sorted(
            expected(legacy_graph, 1, 1).edges()
        )
        with pytest.raises(ImportError):
            actual(graph, 1, 1, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 1, 1, unexpected=True)


@pytest.mark.parametrize("name", ["is_kl_connected", "kl_connected_subgraph"])
def test_flattened_hybrid_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.hybrid, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph", 1, 1) is marker


def test_flattened_tournament_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.is_tournament
    expected = legacy.algorithms.is_tournament
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1)])
    legacy_dg = legacy.DiGraph([(0, 1)])
    assert actual(dg) == expected(legacy_dg)

    with pytest.raises(ImportError):
        actual(dg, backend="missing")
    with pytest.raises(TypeError):
        actual(dg, unexpected=True)


def test_flattened_tournament_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("graph",)
        return marker

    monkeypatch.setattr(fnx_algorithms.tournament, "is_tournament", sentinel)
    assert fnx_algorithms.is_tournament("graph") is marker


@pytest.mark.parametrize(
    "name",
    ["lattice_reference", "omega", "random_reference", "sigma"],
)
def test_flattened_smallworld_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    if name in ("lattice_reference", "random_reference"):
        graph = fnx.cycle_graph(6)
        legacy_graph = legacy.cycle_graph(6)
        assert actual(graph, niter=1, seed=42).number_of_nodes() == expected(
            legacy_graph, niter=1, seed=42
        ).number_of_nodes()
        with pytest.raises(ImportError):
            actual(graph, niter=1, seed=42, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, niter=1, seed=42, unexpected=True)
    else:
        graph = fnx.complete_graph(5)
        legacy_graph = legacy.complete_graph(5)
        assert isinstance(actual(graph, niter=1, nrand=2, seed=42), (int, float))
        with pytest.raises(ImportError):
            actual(graph, niter=1, nrand=2, seed=42, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, niter=1, nrand=2, seed=42, unexpected=True)


@pytest.mark.parametrize(
    "name",
    ["lattice_reference", "omega", "random_reference", "sigma"],
)
def test_flattened_smallworld_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.smallworld, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize("name", ["is_k_regular", "is_regular", "k_factor"])
def test_flattened_regular_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    if name == "is_k_regular":
        assert actual(graph, 2) == expected(legacy_graph, 2)
        with pytest.raises(ImportError):
            actual(graph, 2, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 2, unexpected=True)
    elif name == "k_factor":
        assert sorted(actual(graph, 1).edges()) == sorted(
            expected(legacy_graph, 1).edges()
        )
        with pytest.raises(ImportError):
            actual(graph, 1, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 1, unexpected=True)
    else:
        assert actual(graph) == expected(legacy_graph)
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)


@pytest.mark.parametrize("name", ["is_k_regular", "is_regular", "k_factor"])
def test_flattened_regular_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.regular, name, sentinel)
    if name in ("is_k_regular", "k_factor"):
        assert getattr(fnx_algorithms, name)("graph", 2) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    ["connected_double_edge_swap", "directed_edge_swap", "double_edge_swap"],
)
def test_flattened_swap_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    if name == "directed_edge_swap":
        dg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])
        res = actual(dg.copy(), nswap=1, seed=42)
        assert isinstance(res, fnx.DiGraph)
        with pytest.raises(ImportError):
            actual(dg.copy(), nswap=1, seed=42, backend="missing")
        with pytest.raises(TypeError):
            actual(dg.copy(), nswap=1, seed=42, unexpected=True)
    else:
        g = fnx.cycle_graph(6)
        res = actual(g.copy(), nswap=1, seed=42)
        assert res is not None
        with pytest.raises(ImportError):
            actual(g.copy(), nswap=1, seed=42, backend="missing")
        with pytest.raises(TypeError):
            actual(g.copy(), nswap=1, seed=42, unexpected=True)


@pytest.mark.parametrize(
    "name",
    ["connected_double_edge_swap", "directed_edge_swap", "double_edge_swap"],
)
def test_flattened_swap_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.swap, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize("name", ["check_planarity", "is_planar"])
def test_flattened_planarity_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name == "check_planarity":
        assert actual(graph)[0] == expected(legacy_graph)[0]
    else:
        assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize("name", ["check_planarity", "is_planar"])
def test_flattened_planarity_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.planarity, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize("name", ["is_edge_cover", "min_edge_cover"])
def test_flattened_covering_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name == "is_edge_cover":
        cover = {(0, 1), (2, 3)}
        assert actual(graph, cover) == expected(legacy_graph, cover)
        with pytest.raises(ImportError):
            actual(graph, cover, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, cover, unexpected=True)
    else:
        act_res = actual(graph)
        exp_res = expected(legacy_graph)
        assert len(act_res) == len(exp_res)
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)


@pytest.mark.parametrize("name", ["is_edge_cover", "min_edge_cover"])
def test_flattened_covering_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.covering, name, sentinel)
    if name == "is_edge_cover":
        assert fnx_algorithms.is_edge_cover("graph", "cover") is marker
    else:
        assert fnx_algorithms.min_edge_cover("graph") is marker


@pytest.mark.parametrize("name", ["dominance_frontiers", "immediate_dominators"])
def test_flattened_dominance_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    legacy_dg = legacy.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert actual(dg, 0) == expected(legacy_dg, 0)

    with pytest.raises(ImportError):
        actual(dg, 0, backend="missing")
    with pytest.raises(TypeError):
        actual(dg, 0, unexpected=True)


@pytest.mark.parametrize("name", ["dominance_frontiers", "immediate_dominators"])
def test_flattened_dominance_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.dominance, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph", 0) is marker


@pytest.mark.parametrize(
    "name",
    ["weisfeiler_lehman_graph_hash", "weisfeiler_lehman_subgraph_hashes"],
)
def test_flattened_graph_hashing_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    ["weisfeiler_lehman_graph_hash", "weisfeiler_lehman_subgraph_hashes"],
)
def test_flattened_graph_hashing_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.graph_hashing, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


def test_flattened_hierarchy_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.flow_hierarchy
    expected = legacy.algorithms.flow_hierarchy
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    legacy_dg = legacy.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert actual(dg) == pytest.approx(expected(legacy_dg))

    with pytest.raises(ImportError):
        actual(dg, backend="missing")
    with pytest.raises(TypeError):
        actual(dg, unexpected=True)


def test_flattened_hierarchy_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.hierarchy, "flow_hierarchy", sentinel)
    assert fnx_algorithms.flow_hierarchy("graph") is marker


def test_flattened_mis_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.maximal_independent_set
    expected = legacy.algorithms.maximal_independent_set
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert set(actual(graph, seed=42)) == set(expected(legacy_graph, seed=42))

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


def test_flattened_mis_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.mis, "maximal_independent_set", sentinel)
    assert fnx_algorithms.maximal_independent_set("graph") is marker


def test_flattened_perfect_graph_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.is_perfect_graph
    expected = legacy.algorithms.is_perfect_graph
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


def test_flattened_perfect_graph_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.perfect_graph, "is_perfect_graph", sentinel)
    assert fnx_algorithms.is_perfect_graph("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "enumerate_all_cliques",
        "find_cliques",
        "find_cliques_recursive",
        "make_clique_bipartite",
        "max_weight_clique",
        "node_clique_number",
        "number_of_cliques",
    ],
)
def test_flattened_clique_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    if name == "find_cliques":
        assert sorted(map(sorted, actual(graph))) == sorted(
            map(sorted, expected(legacy_graph))
        )
    elif name in ("find_cliques_recursive", "enumerate_all_cliques"):
        assert list(actual(graph)) == list(expected(legacy_graph))
    elif name == "make_clique_bipartite":
        assert sorted(actual(graph).nodes()) == sorted(expected(legacy_graph).nodes())
    elif name == "max_weight_clique":
        assert actual(graph, weight=None) == expected(legacy_graph, weight=None)
    elif name in ("node_clique_number", "number_of_cliques"):
        assert actual(graph) == expected(legacy_graph)

    if name != "number_of_cliques":
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "enumerate_all_cliques",
        "find_cliques",
        "find_cliques_recursive",
        "make_clique_bipartite",
        "max_weight_clique",
        "node_clique_number",
        "number_of_cliques",
    ],
)
def test_flattened_clique_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.clique, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize("name", ["dedensify", "snap_aggregation"])
def test_flattened_summarization_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    if name == "dedensify":
        graph = fnx.cycle_graph(4)
        legacy_graph = legacy.cycle_graph(4)
        res, c = actual(graph, 2)
        exp_res, exp_c = expected(legacy_graph, 2)
        assert sorted(res.edges()) == sorted(exp_res.edges())
        assert c == exp_c
        with pytest.raises(ImportError):
            actual(graph, 2, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 2, unexpected=True)
    else:
        graph = fnx.Graph()
        graph.add_node(0, color="red")
        graph.add_node(1, color="red")
        legacy_graph = legacy.Graph()
        legacy_graph.add_node(0, color="red")
        legacy_graph.add_node(1, color="red")
        assert len(actual(graph, ["color"]).nodes()) == len(
            expected(legacy_graph, ["color"]).nodes()
        )
        with pytest.raises(ImportError):
            actual(graph, ["color"], backend="missing")
        with pytest.raises(TypeError):
            actual(graph, ["color"], unexpected=True)


@pytest.mark.parametrize("name", ["dedensify", "snap_aggregation"])
def test_flattened_summarization_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.summarization, name, sentinel)
    if name == "dedensify":
        assert getattr(fnx_algorithms, name)("graph", 2) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph", ["color"]) is marker


@pytest.mark.parametrize(
    "name",
    [
        "eulerian_circuit",
        "eulerian_path",
        "eulerize",
        "has_eulerian_path",
        "is_eulerian",
        "is_semieulerian",
    ],
)
def test_flattened_euler_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    cycle = fnx.cycle_graph(4)
    legacy_cycle = legacy.cycle_graph(4)
    if name in ("eulerian_circuit", "eulerian_path"):
        assert list(actual(cycle)) == list(expected(legacy_cycle))
    elif name == "eulerize":
        path = fnx.path_graph(4)
        legacy_path = legacy.path_graph(4)
        assert sorted(actual(path).edges()) == sorted(expected(legacy_path).edges())
    else:
        assert actual(cycle) == expected(legacy_cycle)

    with pytest.raises(ImportError):
        actual(cycle, backend="missing")
    with pytest.raises(TypeError):
        actual(cycle, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "eulerian_circuit",
        "eulerian_path",
        "eulerize",
        "has_eulerian_path",
        "is_eulerian",
        "is_semieulerian",
    ],
)
def test_flattened_euler_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.euler, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


def test_flattened_sparsifiers_namespace_matches_legacy_oracle():
    legacy = _legacy_networkx()
    actual = fnx_algorithms.spanner
    expected = legacy.algorithms.spanner
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    assert sorted(actual(graph, 2, seed=42).edges()) == sorted(
        expected(legacy_graph, 2, seed=42).edges()
    )

    with pytest.raises(ImportError):
        actual(graph, 2, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, 2, unexpected=True)


def test_flattened_sparsifiers_namespace_routes_to_leaf_module(monkeypatch):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.sparsifiers, "spanner", sentinel)
    assert fnx_algorithms.spanner("graph", 2) is marker


@pytest.mark.parametrize(
    "name",
    [
        "find_minimal_d_separator",
        "is_d_separator",
        "is_minimal_d_separator",
    ],
)
def test_flattened_d_separation_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1), (1, 2)])
    legacy_dg = legacy.DiGraph([(0, 1), (1, 2)])
    if name == "find_minimal_d_separator":
        assert actual(dg, 0, 2) == expected(legacy_dg, 0, 2)
        with pytest.raises(ImportError):
            actual(dg, 0, 2, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, 0, 2, unexpected=True)
    elif name == "is_d_separator":
        assert actual(dg, {0}, {2}, {1}) == expected(legacy_dg, {0}, {2}, {1})
        with pytest.raises(ImportError):
            actual(dg, {0}, {2}, {1}, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, {0}, {2}, {1}, unexpected=True)
    else:
        assert actual(dg, 0, 2, {1}) == expected(legacy_dg, 0, 2, {1})
        with pytest.raises(ImportError):
            actual(dg, 0, 2, {1}, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, 0, 2, {1}, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "find_minimal_d_separator",
        "is_d_separator",
        "is_minimal_d_separator",
    ],
)
def test_flattened_d_separation_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.d_separation, name, sentinel)
    if name in ("is_d_separator", "is_minimal_d_separator"):
        assert getattr(fnx_algorithms, name)("graph", {0}, {2}, {1}) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph", 0, 2) is marker


@pytest.mark.parametrize(
    "name",
    [
        "global_parameters",
        "intersection_array",
        "is_distance_regular",
        "is_strongly_regular",
    ],
)
def test_flattened_distance_regular_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    if name == "global_parameters":
        assert list(actual([2, 1], [1, 2])) == list(expected([2, 1], [1, 2]))
        with pytest.raises(TypeError):
            actual([2, 1], [1, 2], unexpected=True)
    else:
        graph = fnx.cycle_graph(5)
        legacy_graph = legacy.cycle_graph(5)
        assert actual(graph) == expected(legacy_graph)
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "global_parameters",
        "intersection_array",
        "is_distance_regular",
        "is_strongly_regular",
    ],
)
def test_flattened_distance_regular_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.distance_regular, name, sentinel)
    if name == "global_parameters":
        assert getattr(fnx_algorithms, name)([2, 1], [1, 2]) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "connected_dominating_set",
        "dominating_set",
        "is_connected_dominating_set",
        "is_dominating_set",
    ],
)
def test_flattened_dominating_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.path_graph(4)
    legacy_graph = legacy.path_graph(4)
    if name in ("connected_dominating_set", "dominating_set"):
        assert set(actual(graph)) == set(expected(legacy_graph))
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)
    else:
        assert actual(graph, [1, 2]) == expected(legacy_graph, [1, 2])
        with pytest.raises(ImportError):
            actual(graph, [1, 2], backend="missing")
        with pytest.raises(TypeError):
            actual(graph, [1, 2], unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "connected_dominating_set",
        "dominating_set",
        "is_connected_dominating_set",
        "is_dominating_set",
    ],
)
def test_flattened_dominating_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.dominating, name, sentinel)
    if name in ("connected_dominating_set", "dominating_set"):
        assert getattr(fnx_algorithms, name)("graph") is marker
    else:
        assert getattr(fnx_algorithms, name)("graph", [0]) is marker


@pytest.mark.parametrize(
    "name",
    [
        "barycenter",
        "center",
        "diameter",
        "eccentricity",
        "effective_graph_resistance",
        "harmonic_diameter",
        "kemeny_constant",
        "periphery",
        "radius",
        "resistance_distance",
    ],
)
def test_flattened_distance_measures_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    if name in ("effective_graph_resistance", "kemeny_constant"):
        assert actual(graph) == pytest.approx(expected(legacy_graph))
    elif name == "resistance_distance":
        assert actual(graph, 0, 2) == pytest.approx(expected(legacy_graph, 0, 2))
    else:
        assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "barycenter",
        "center",
        "diameter",
        "eccentricity",
        "effective_graph_resistance",
        "harmonic_diameter",
        "kemeny_constant",
        "periphery",
        "radius",
        "resistance_distance",
    ],
)
def test_flattened_distance_measures_namespace_routes_to_leaf_module(
    monkeypatch, name
):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.distance_measures, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "k_core",
        "k_corona",
        "k_crust",
        "k_shell",
        "k_truss",
        "onion_layers",
    ],
)
def test_flattened_core_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    if name in ("k_corona", "k_truss"):
        assert sorted(actual(graph, 2).nodes()) == sorted(
            expected(legacy_graph, 2).nodes()
        )
        with pytest.raises(ImportError):
            actual(graph, 2, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 2, unexpected=True)
    elif name == "onion_layers":
        assert actual(graph) == expected(legacy_graph)
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)
    else:
        assert sorted(actual(graph).nodes()) == sorted(expected(legacy_graph).nodes())
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "k_core",
        "k_corona",
        "k_crust",
        "k_shell",
        "k_truss",
        "onion_layers",
    ],
)
def test_flattened_core_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.core, name, sentinel)
    if name in ("k_corona", "k_truss"):
        assert getattr(fnx_algorithms, name)("graph", 2) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "chordless_cycles",
        "cycle_basis",
        "find_cycle",
        "girth",
        "minimum_cycle_basis",
        "recursive_simple_cycles",
        "simple_cycles",
    ],
)
def test_flattened_cycles_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    if name in ("recursive_simple_cycles", "simple_cycles"):
        graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
        legacy_graph = legacy.DiGraph([(0, 1), (1, 2), (2, 0)])
        assert list(actual(graph)) == list(expected(legacy_graph))
    elif name in ("chordless_cycles", "find_cycle"):
        graph = fnx.cycle_graph(4)
        legacy_graph = legacy.cycle_graph(4)
        assert list(actual(graph)) == list(expected(legacy_graph))
    else:
        graph = fnx.cycle_graph(4)
        legacy_graph = legacy.cycle_graph(4)
        assert actual(graph) == expected(legacy_graph)

    with pytest.raises(ImportError):
        actual(graph, backend="missing")
    with pytest.raises(TypeError):
        actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "chordless_cycles",
        "cycle_basis",
        "find_cycle",
        "girth",
        "minimum_cycle_basis",
        "recursive_simple_cycles",
        "simple_cycles",
    ],
)
def test_flattened_cycles_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.cycles, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "all_pairs_lowest_common_ancestor",
        "lowest_common_ancestor",
        "tree_all_pairs_lowest_common_ancestor",
    ],
)
def test_flattened_lowest_common_ancestors_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    tree = fnx.DiGraph([(0, 1), (0, 2), (1, 3)])
    legacy_tree = legacy.DiGraph([(0, 1), (0, 2), (1, 3)])
    if name == "lowest_common_ancestor":
        assert actual(tree, 2, 3) == expected(legacy_tree, 2, 3)
        with pytest.raises(ImportError):
            actual(tree, 2, 3, backend="missing")
        with pytest.raises(TypeError):
            actual(tree, 2, 3, unexpected=True)
    else:
        assert dict(actual(tree)) == dict(expected(legacy_tree))
        with pytest.raises(ImportError):
            dict(actual(tree, backend="missing"))
        with pytest.raises(TypeError):
            dict(actual(tree, unexpected=True))


@pytest.mark.parametrize(
    "name",
    [
        "all_pairs_lowest_common_ancestor",
        "lowest_common_ancestor",
        "tree_all_pairs_lowest_common_ancestor",
    ],
)
def test_flattened_lowest_common_ancestors_namespace_routes_to_leaf_module(
    monkeypatch, name
):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.lowest_common_ancestors, name, sentinel)
    if name == "lowest_common_ancestor":
        assert getattr(fnx_algorithms, name)("graph", 0, 1) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "is_matching",
        "is_maximal_matching",
        "is_perfect_matching",
        "max_weight_matching",
        "maximal_matching",
        "min_weight_matching",
    ],
)
def test_flattened_matching_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    matching = {(0, 1), (2, 3)}
    if name in ("is_matching", "is_maximal_matching", "is_perfect_matching"):
        assert actual(graph, matching) == expected(legacy_graph, matching)
        with pytest.raises(ImportError):
            actual(graph, matching, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, matching, unexpected=True)
    else:
        assert actual(graph) == expected(legacy_graph)
        with pytest.raises(ImportError):
            actual(graph, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "is_matching",
        "is_maximal_matching",
        "is_perfect_matching",
        "max_weight_matching",
        "maximal_matching",
        "min_weight_matching",
    ],
)
def test_flattened_matching_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.matching, name, sentinel)
    if name in ("is_matching", "is_maximal_matching", "is_perfect_matching"):
        assert getattr(fnx_algorithms, name)("graph", [(0, 1)]) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "reciprocity",
        "overall_reciprocity",
    ],
)
def test_flattened_reciprocity_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1), (1, 0), (2, 3)])
    legacy_dg = legacy.DiGraph([(0, 1), (1, 0), (2, 3)])
    assert actual(dg) == expected(legacy_dg)

    with pytest.raises(ImportError):
        actual(dg, backend="missing")
    with pytest.raises(TypeError):
        actual(dg, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "reciprocity",
        "overall_reciprocity",
    ],
)
def test_flattened_reciprocity_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms._fnx_reciprocity, name, sentinel)
    assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "all_simple_edge_paths",
        "all_simple_paths",
        "is_simple_path",
        "shortest_simple_paths",
    ],
)
def test_flattened_simple_paths_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    graph = fnx.cycle_graph(4)
    legacy_graph = legacy.cycle_graph(4)
    if name in ("all_simple_edge_paths", "all_simple_paths", "shortest_simple_paths"):
        assert list(actual(graph, 0, 2)) == list(expected(legacy_graph, 0, 2))
        with pytest.raises(ImportError):
            actual(graph, 0, 2, backend="missing")
        with pytest.raises(TypeError):
            actual(graph, 0, 2, unexpected=True)
    else:
        assert actual(graph, [0, 1, 2]) == expected(legacy_graph, [0, 1, 2])
        with pytest.raises(ImportError):
            actual(graph, [0, 1, 2], backend="missing")
        with pytest.raises(TypeError):
            actual(graph, [0, 1, 2], unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "all_simple_edge_paths",
        "all_simple_paths",
        "is_simple_path",
        "shortest_simple_paths",
    ],
)
def test_flattened_simple_paths_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.simple_paths, name, sentinel)
    if name == "is_simple_path":
        assert getattr(fnx_algorithms, name)("graph", [0, 1]) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph", 0, 1) is marker


@pytest.mark.parametrize(
    "name",
    [
        "cartesian_product",
        "corona_product",
        "lexicographic_product",
        "modular_product",
        "power",
        "rooted_product",
        "strong_product",
        "tensor_product",
        "compose",
        "difference",
        "disjoint_union",
        "full_join",
        "intersection",
        "symmetric_difference",
        "union",
        "compose_all",
        "disjoint_union_all",
        "intersection_all",
        "union_all",
        "complement",
        "reverse",
    ],
)
def test_flattened_operators_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    g1 = fnx.path_graph(3)
    lg1 = legacy.path_graph(3)
    if name in ("union", "union_all", "full_join"):
        g2 = fnx.path_graph([3, 4, 5])
        lg2 = legacy.path_graph([3, 4, 5])
    else:
        g2 = fnx.path_graph(3)
        lg2 = legacy.path_graph(3)

    if name in ("compose_all", "disjoint_union_all", "intersection_all", "union_all"):
        assert sorted(str(e) for e in actual([g1, g2]).edges()) == sorted(
            str(e) for e in expected([lg1, lg2]).edges()
        )
        with pytest.raises(ImportError):
            actual([g1, g2], backend="missing")
        with pytest.raises(TypeError):
            actual([g1, g2], unexpected=True)
    elif name == "power":
        assert sorted(str(e) for e in actual(g1, 2).edges()) == sorted(
            str(e) for e in expected(lg1, 2).edges()
        )
        with pytest.raises(ImportError):
            actual(g1, 2, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, 2, unexpected=True)
    elif name == "rooted_product":
        assert sorted(str(e) for e in actual(g1, g2, 0).edges()) == sorted(
            str(e) for e in expected(lg1, lg2, 0).edges()
        )
        with pytest.raises(ImportError):
            actual(g1, g2, 0, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, g2, 0, unexpected=True)
    elif name == "corona_product":
        assert sorted(str(e) for e in actual(g1, g2).edges()) == sorted(
            str(e) for e in expected(lg1, lg2).edges()
        )
        with pytest.raises(ImportError):
            actual(g1, g2, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, g2, unexpected=True)
    elif name == "complement":
        assert sorted(str(e) for e in actual(g1).edges()) == sorted(
            str(e) for e in expected(lg1).edges()
        )
        with pytest.raises(ImportError):
            actual(g1, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, unexpected=True)
    elif name == "reverse":
        dg = fnx.DiGraph([(0, 1)])
        ldg = legacy.DiGraph([(0, 1)])
        assert sorted(str(e) for e in actual(dg).edges()) == sorted(
            str(e) for e in expected(ldg).edges()
        )
        with pytest.raises(ImportError):
            actual(dg, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, unexpected=True)
    else:
        assert sorted(str(e) for e in actual(g1, g2).edges()) == sorted(
            str(e) for e in expected(lg1, lg2).edges()
        )
        with pytest.raises(ImportError):
            actual(g1, g2, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, g2, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "cartesian_product",
        "corona_product",
        "lexicographic_product",
        "modular_product",
        "power",
        "rooted_product",
        "strong_product",
        "tensor_product",
        "compose",
        "difference",
        "disjoint_union",
        "full_join",
        "intersection",
        "symmetric_difference",
        "union",
        "compose_all",
        "disjoint_union_all",
        "intersection_all",
        "union_all",
        "complement",
        "reverse",
    ],
)
def test_flattened_operators_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.operators, name, sentinel)
    if name in ("compose_all", "disjoint_union_all", "intersection_all", "union_all"):
        assert getattr(fnx_algorithms, name)(["g1", "g2"]) is marker
    elif name == "power":
        assert getattr(fnx_algorithms, name)("g1", 2) is marker
    elif name == "rooted_product":
        assert getattr(fnx_algorithms, name)("g1", "g2", 0) is marker
    elif name in ("complement", "reverse"):
        assert getattr(fnx_algorithms, name)("g1") is marker
    else:
        assert getattr(fnx_algorithms, name)("g1", "g2") is marker


@pytest.mark.parametrize(
    "name",
    [
        "condensation",
        "is_strongly_connected",
        "kosaraju_strongly_connected_components",
        "number_strongly_connected_components",
        "strongly_connected_components",
        "articulation_points",
        "biconnected_component_edges",
        "biconnected_components",
        "is_biconnected",
        "connected_components",
        "is_connected",
        "node_connected_component",
        "number_connected_components",
        "attracting_components",
        "is_attracting_component",
        "number_attracting_components",
        "is_weakly_connected",
        "number_weakly_connected_components",
        "weakly_connected_components",
        "is_semiconnected",
    ],
)
def test_flattened_components_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    dg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    ldg = legacy.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    ug = fnx.path_graph(3)
    lug = legacy.path_graph(3)

    if name in (
        "is_strongly_connected",
        "is_weakly_connected",
        "number_strongly_connected_components",
        "number_weakly_connected_components",
        "number_attracting_components",
        "is_attracting_component",
        "is_semiconnected",
    ):
        assert actual(dg) == expected(ldg)
        with pytest.raises(ImportError):
            actual(dg, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, unexpected=True)
    elif name in (
        "strongly_connected_components",
        "weakly_connected_components",
        "attracting_components",
        "kosaraju_strongly_connected_components",
    ):
        assert {frozenset(c) for c in actual(dg)} == {
            frozenset(c) for c in expected(ldg)
        }
        with pytest.raises(ImportError):
            actual(dg, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, unexpected=True)
    elif name == "condensation":
        assert sorted(actual(dg).nodes()) == sorted(expected(ldg).nodes())
        with pytest.raises(ImportError):
            actual(dg, backend="missing")
        with pytest.raises(TypeError):
            actual(dg, unexpected=True)
    elif name == "node_connected_component":
        assert actual(ug, 0) == expected(lug, 0)
        with pytest.raises(ImportError):
            actual(ug, 0, backend="missing")
        with pytest.raises(TypeError):
            actual(ug, 0, unexpected=True)
    elif name in ("connected_components", "biconnected_components"):
        assert {frozenset(c) for c in actual(ug)} == {
            frozenset(c) for c in expected(lug)
        }
        with pytest.raises(ImportError):
            actual(ug, backend="missing")
        with pytest.raises(TypeError):
            actual(ug, unexpected=True)
    elif name == "biconnected_component_edges":
        assert {
            frozenset(frozenset(e) for e in c) for c in actual(ug)
        } == {
            frozenset(frozenset(e) for e in c) for c in expected(lug)
        }
        with pytest.raises(ImportError):
            actual(ug, backend="missing")
        with pytest.raises(TypeError):
            actual(ug, unexpected=True)
    elif name == "articulation_points":
        assert list(actual(ug)) == list(expected(lug))
        with pytest.raises(ImportError):
            actual(ug, backend="missing")
        with pytest.raises(TypeError):
            actual(ug, unexpected=True)
    else:
        assert actual(ug) == expected(lug)
        with pytest.raises(ImportError):
            actual(ug, backend="missing")
        with pytest.raises(TypeError):
            actual(ug, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "condensation",
        "is_strongly_connected",
        "kosaraju_strongly_connected_components",
        "number_strongly_connected_components",
        "strongly_connected_components",
        "articulation_points",
        "biconnected_component_edges",
        "biconnected_components",
        "is_biconnected",
        "connected_components",
        "is_connected",
        "node_connected_component",
        "number_connected_components",
        "attracting_components",
        "is_attracting_component",
        "number_attracting_components",
        "is_weakly_connected",
        "number_weakly_connected_components",
        "weakly_connected_components",
        "is_semiconnected",
    ],
)
def test_flattened_components_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.components, name, sentinel)
    if name == "node_connected_component":
        assert getattr(fnx_algorithms, name)("graph", 0) is marker
    else:
        assert getattr(fnx_algorithms, name)("graph") is marker


@pytest.mark.parametrize(
    "name",
    [
        "generate_random_paths",
        "graph_edit_distance",
        "optimal_edit_paths",
        "optimize_edit_paths",
        "optimize_graph_edit_distance",
        "panther_similarity",
        "panther_vector_similarity",
        "simrank_similarity",
    ],
)
def test_flattened_similarity_namespace_matches_legacy_oracle(name):
    legacy = _legacy_networkx()
    actual = getattr(fnx_algorithms, name)
    expected = getattr(legacy.algorithms, name)
    assert str(inspect.signature(actual)) == str(inspect.signature(expected))

    if name in ("panther_similarity", "panther_vector_similarity"):
        g1 = fnx.path_graph(12)
        lg1 = legacy.path_graph(12)
        assert actual(g1, 0, seed=42) == expected(lg1, 0, seed=42)
        with pytest.raises(ImportError):
            actual(g1, 0, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, 0, unexpected=True)
    elif name == "generate_random_paths":
        g1 = fnx.path_graph(6)
        lg1 = legacy.path_graph(6)
        assert len(list(actual(g1, 5, seed=42))) == len(
            list(expected(lg1, 5, seed=42))
        )
        with pytest.raises(ImportError):
            list(actual(g1, 5, backend="missing"))
        with pytest.raises(TypeError):
            actual(g1, 5, unexpected=True)
    elif name == "graph_edit_distance":
        g1 = fnx.path_graph(3)
        lg1 = legacy.path_graph(3)
        g2 = fnx.path_graph(3)
        lg2 = legacy.path_graph(3)
        assert actual(g1, g2) == expected(lg1, lg2)
        with pytest.raises(ImportError):
            actual(g1, g2, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, g2, unexpected=True)
    elif name in (
        "optimal_edit_paths",
        "optimize_edit_paths",
        "optimize_graph_edit_distance",
    ):
        g1 = fnx.path_graph(3)
        lg1 = legacy.path_graph(3)
        g2 = fnx.path_graph(3)
        lg2 = legacy.path_graph(3)
        act_res = list(actual(g1, g2))
        exp_res = list(expected(lg1, lg2))
        assert len(act_res) == len(exp_res)
        with pytest.raises(ImportError):
            actual(g1, g2, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, g2, unexpected=True)
    elif name == "simrank_similarity":
        g1 = fnx.path_graph(3)
        lg1 = legacy.path_graph(3)
        assert actual(g1, 0, 1) == pytest.approx(expected(lg1, 0, 1))
        with pytest.raises(ImportError):
            actual(g1, 0, 1, backend="missing")
        with pytest.raises(TypeError):
            actual(g1, 0, 1, unexpected=True)


@pytest.mark.parametrize(
    "name",
    [
        "generate_random_paths",
        "graph_edit_distance",
        "optimal_edit_paths",
        "optimize_edit_paths",
        "optimize_graph_edit_distance",
        "panther_similarity",
        "panther_vector_similarity",
        "simrank_similarity",
    ],
)
def test_flattened_similarity_namespace_routes_to_leaf_module(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        return marker

    monkeypatch.setattr(fnx_algorithms.similarity, name, sentinel)
    if name == "generate_random_paths":
        assert getattr(fnx_algorithms, name)("g", 10) is marker
    elif name in ("graph_edit_distance", "optimal_edit_paths", "optimize_edit_paths", "optimize_graph_edit_distance"):
        assert getattr(fnx_algorithms, name)("g1", "g2") is marker
    elif name in ("panther_similarity", "panther_vector_similarity"):
        assert getattr(fnx_algorithms, name)("g", 0) is marker
    else:
        assert getattr(fnx_algorithms, name)("g") is marker
