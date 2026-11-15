import math
from unittest import mock

import numpy as np
import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


def _assert_nested_dicts_close(actual, expected, tol=1e-12):
    assert set(actual) == set(expected)
    for left in expected:
        assert set(actual[left]) == set(expected[left])
        for right in expected[left]:
            assert math.isclose(
                actual[left][right],
                expected[left][right],
                rel_tol=tol,
                abs_tol=tol,
            )


def test_mixing_dict_matches_networkx_without_delegation():
    pairs = [("red", "blue"), ("red", "blue"), ("blue", "green")]
    expected_counts = nx.mixing_dict(pairs, normalized=False)
    expected_normalized = nx.mixing_dict(pairs, normalized=True)

    with mock.patch(
        "networkx.mixing_dict",
        side_effect=AssertionError("NetworkX mixing_dict should not be used"),
    ):
        _assert_nested_dicts_close(
            fnx.mixing_dict(pairs, normalized=False),
            expected_counts,
        )
        _assert_nested_dicts_close(
            fnx.mixing_dict(pairs, normalized=True),
            expected_normalized,
        )
        assert fnx.mixing_dict([], normalized=True) == {}


def test_degree_mixing_dict_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    _assert_nested_dicts_close(
        fnx.degree_mixing_dict(graph),
        nx.degree_mixing_dict(expected),
    )


def test_degree_mixing_matrix_directed_matches_networkx_without_fallback(
    monkeypatch,
):
    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    expected = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])

    wanted = nx.degree_mixing_matrix(expected)

    monkeypatch.setattr(
        nx,
        "degree_mixing_matrix",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("NetworkX degree_mixing_matrix fallback should not be used")
        ),
    )

    np.testing.assert_allclose(
        fnx.degree_mixing_matrix(graph),
        wanted,
    )


def test_degree_mixing_matrix_weighted_mapping_matches_networkx_without_fallback(
    monkeypatch,
):
    graph = fnx.Graph()
    expected = nx.Graph()
    for G in (graph, expected):
        G.add_edge("a", "b", weight=0.5)
        G.add_edge("b", "c", weight=1.0)
        G.add_edge("c", "a", weight=1.0)

    mapping = {0.5: 1, 1.5: 0, "unused": 2}
    wanted = nx.degree_mixing_matrix(
        expected,
        weight="weight",
        normalized=False,
        mapping=mapping,
    )

    monkeypatch.setattr(
        nx,
        "degree_mixing_matrix",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("NetworkX degree_mixing_matrix fallback should not be used")
        ),
    )

    np.testing.assert_allclose(
        fnx.degree_mixing_matrix(
            graph,
            weight="weight",
            normalized=False,
            mapping=mapping,
        ),
        wanted,
    )


def test_attribute_mixing_dict_and_matrix_match_networkx():
    graph = fnx.Graph()
    graph.add_nodes_from(
        [
            (0, {"color": "red"}),
            (1, {"color": "red"}),
            (2, {"color": "blue"}),
            (3, {"color": "blue"}),
        ]
    )
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])

    expected = nx.Graph()
    expected.add_nodes_from(
        [
            (0, {"color": "red"}),
            (1, {"color": "red"}),
            (2, {"color": "blue"}),
            (3, {"color": "blue"}),
        ]
    )
    expected.add_edges_from([(0, 1), (1, 2), (2, 3)])

    _assert_nested_dicts_close(
        fnx.attribute_mixing_dict(graph, "color"),
        nx.attribute_mixing_dict(expected, "color"),
    )
    np.testing.assert_allclose(
        fnx.attribute_mixing_matrix(graph, "color"),
        nx.attribute_mixing_matrix(expected, "color"),
    )


def test_attribute_assortativity_coefficient_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)
    for node, color in [(0, "red"), (1, "red"), (2, "blue"), (3, "blue")]:
        graph.nodes[node]["color"] = color
        expected.nodes[node]["color"] = color

    assert math.isclose(
        fnx.attribute_assortativity_coefficient(graph, "color"),
        nx.attribute_assortativity_coefficient(expected, "color"),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_numeric_assortativity_coefficient_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)
    for node, size in [(0, 1), (1, 2), (2, 2), (3, 3)]:
        graph.nodes[node]["size"] = size
        expected.nodes[node]["size"] = size

    assert math.isclose(
        fnx.numeric_assortativity_coefficient(graph, "size"),
        nx.numeric_assortativity_coefficient(expected, "size"),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_degree_pearson_correlation_coefficient_matches_networkx():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    assert math.isclose(
        fnx.degree_pearson_correlation_coefficient(graph),
        nx.degree_pearson_correlation_coefficient(expected),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_attribute_mixing_matrix_respects_mapping():
    graph = fnx.Graph()
    graph.add_nodes_from([(0, {"kind": "a"}), (1, {"kind": "b"})])
    graph.add_edge(0, 1)

    expected = nx.Graph()
    expected.add_nodes_from([(0, {"kind": "a"}), (1, {"kind": "b"})])
    expected.add_edge(0, 1)

    mapping = {"a": 1, "b": 0, "unused": 2}
    np.testing.assert_allclose(
        fnx.attribute_mixing_matrix(graph, "kind", mapping=mapping),
        nx.attribute_mixing_matrix(expected, "kind", mapping=mapping),
    )


_ASSORTATIVITY_CALLS = [
    ("node_attribute_xy", ("kind",), {}),
    ("node_degree_xy", (), {"weight": "cost"}),
    ("attribute_mixing_dict", ("kind",), {}),
    ("attribute_mixing_matrix", ("kind",), {}),
    ("degree_mixing_dict", (), {"weight": "cost"}),
    ("degree_mixing_matrix", (), {"weight": "cost"}),
    ("attribute_assortativity_coefficient", ("kind",), {}),
    ("numeric_assortativity_coefficient", ("score",), {}),
    ("degree_pearson_correlation_coefficient", (), {"weight": "cost"}),
]


def _assortativity_graph(module, class_name):
    graph = getattr(module, class_name)()
    graph.add_nodes_from([
        (1024, {"kind": "c", "score": 5}),
        (0, {"kind": "a", "score": 2}),
        (3, {"kind": "b", "score": 3}),
        (7, {"kind": "a", "score": 2}),
        (2, {"kind": "c", "score": 5}),
        (99, {"kind": "isolated", "score": 11}),
    ])
    graph.add_weighted_edges_from(
        [(1024, 3, 2), (1024, 0, 3), (3, 0, 5), (0, 7, 1), (7, 2, 4), (2, 3, 2)],
        weight="cost",
    )
    if graph.is_multigraph():
        graph.add_edge(1024, 3, cost=7)
        graph.add_edge(3, 3, cost=2)
    return graph


def _assert_assortativity_result(actual, expected):
    if isinstance(expected, np.ndarray):
        np.testing.assert_array_equal(actual, expected)
    elif isinstance(expected, dict):
        assert list(actual) == list(expected)
        for key in expected:
            if isinstance(expected[key], dict):
                assert list(actual[key]) == list(expected[key])
            assert actual[key] == expected[key]
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12, nan_ok=True)
    else:
        assert list(actual) == list(expected)


def _prime_assortativity_cache(graph, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    nx.relabel_nodes(graph, {}, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


@pytest.mark.parametrize("name,args,kwargs", _ASSORTATIVITY_CALLS)
def test_assortativity_backend_advertises_owned_functions(name, args, kwargs):
    import fnx_backend_info
    from franken_networkx.backend import BackendInterface, get_backend_info

    assert name in get_backend_info()["functions"]
    assert name in fnx_backend_info.get_backend_info()["functions"]
    graph = _assortativity_graph(nx, "Graph")
    assert BackendInterface.can_run(name, (graph, *args), kwargs)


@pytest.mark.parametrize("name,args,kwargs", _ASSORTATIVITY_CALLS)
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["networkx", "cached-networkx", "native", "view"])
def test_assortativity_backend_results_keep_public_inputs(
    name, args, kwargs, class_name, input_kind, monkeypatch
):
    graph = _assortativity_graph(fnx if input_kind == "native" else nx, class_name)
    expected_graph = _assortativity_graph(nx, class_name)
    if input_kind == "view":
        graph = nx.subgraph_view(graph, filter_node=lambda node: node != 99)
        expected_graph = nx.subgraph_view(expected_graph, filter_node=lambda node: node != 99)
    if input_kind == "cached-networkx":
        _prime_assortativity_cache(graph, monkeypatch)

    expected = getattr(nx, name)(expected_graph, *args, backend="networkx", **kwargs)
    actual = getattr(nx, name)(graph, *args, backend="franken_networkx", **kwargs)
    _assert_assortativity_result(actual, expected)


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["node_attribute_xy", "node_degree_xy"])
@pytest.mark.parametrize("route", ["direct-networkx", "direct-native", "backend", "cached-backend"])
def test_assortativity_pair_iterators_read_mutations_between_yields(
    class_name, name, route, monkeypatch
):
    graph = _assortativity_graph(fnx if route == "direct-native" else nx, class_name)
    expected_graph = _assortativity_graph(nx, class_name)
    options = {"attribute": "kind"} if name == "node_attribute_xy" else {"weight": "cost"}
    if route == "cached-backend":
        _prime_assortativity_cache(graph, monkeypatch)
    if route in {"backend", "cached-backend"}:
        actual = getattr(nx, name)(graph, backend="franken_networkx", **options)
    else:
        actual = getattr(fnx, name)(graph, **options)
    expected = getattr(nx, name)(expected_graph, backend="networkx", **options)

    # The source is retained before first advancement, including a warm
    # conversion. A second write after a yielded pair must remain visible.
    for value in (13, 17):
        for owner in (graph, expected_graph):
            for node in owner:
                owner.nodes[node]["kind"] = f"{node}:{value}"
            for _, _, attrs in owner.edges(data=True):
                attrs["cost"] = value
        assert next(actual) == next(expected)
    assert list(actual) == list(expected)


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["attribute_mixing_dict", "attribute_mixing_matrix"])
@pytest.mark.parametrize("route", ["direct-networkx", "direct-native", "backend", "cached-backend"])
def test_attribute_mixing_resolves_mutating_node_selector_before_attributes(
    class_name, name, route, monkeypatch
):
    graph = _assortativity_graph(fnx if route == "direct-native" else nx, class_name)
    expected_graph = _assortativity_graph(nx, class_name)
    if route == "cached-backend":
        _prime_assortativity_cache(graph, monkeypatch)

    def selected(owner):
        yield 1024
        owner.nodes[3]["kind"] = "changed-by-selector"
        yield 3
        yield 0

    expected = getattr(nx, name)(expected_graph, "kind", nodes=selected(expected_graph))
    if route in {"backend", "cached-backend"}:
        actual = getattr(nx, name)(
            graph, "kind", nodes=selected(graph), backend="franken_networkx"
        )
    else:
        actual = getattr(fnx, name)(graph, "kind", nodes=selected(graph))
    _assert_assortativity_result(actual, expected)


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["attribute_mixing_matrix", "degree_mixing_matrix"])
@pytest.mark.parametrize("normalized", [False, True])
def test_mixing_matrix_mapping_with_no_observed_values_keeps_normalization(
    class_name, name, normalized
):
    graph = _assortativity_graph(fnx, class_name)
    expected_graph = _assortativity_graph(nx, class_name)
    args = ("kind",) if name == "attribute_mixing_matrix" else ()
    options = {"mapping": {"unobserved": 0}, "normalized": normalized}
    with np.errstate(invalid="ignore"):
        expected = getattr(nx, name)(expected_graph, *args, **options)
        actual = getattr(fnx, name)(graph, *args, **options)
    np.testing.assert_array_equal(actual, expected)
    if normalized:
        assert np.isnan(actual).all()
    else:
        assert not actual.any()


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["degree_mixing_dict", "attribute_mixing_dict"])
@pytest.mark.parametrize("normalized", [False, True])
def test_mixing_dict_order_matches_pair_consumption(class_name, name, normalized):
    graph = _assortativity_graph(fnx, class_name)
    expected_graph = _assortativity_graph(nx, class_name)
    args = ("kind",) if name == "attribute_mixing_dict" else ()
    _assert_assortativity_result(
        getattr(fnx, name)(graph, *args, normalized=normalized),
        getattr(nx, name)(expected_graph, *args, normalized=normalized),
    )


@pytest.mark.parametrize(
    "name", ["node_degree_xy", "degree_mixing_dict", "degree_pearson_correlation_coefficient"]
)
def test_assortativity_keeps_custom_degree_provider_read_order(name):
    def run(function):
        graph = nx.Graph([(0, 1), (0, 2), (1, 2)])
        events = []

        def degree_provider(nodes=None, weight=None):
            selected = list(graph if nodes is None else nodes)
            events.append((selected, weight))
            for node in selected:
                yield node, len(events) * 10 + node

        graph.degree = degree_provider
        result = function(graph, weight="cost")
        if name == "node_degree_xy":
            result = list(result)
        return result, events

    actual, actual_events = run(getattr(fnx, name))
    expected, expected_events = run(getattr(nx, name))
    _assert_assortativity_result(actual, expected)
    assert actual_events == expected_events
