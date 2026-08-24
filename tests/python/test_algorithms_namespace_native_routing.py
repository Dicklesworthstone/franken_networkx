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

import inspect

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
