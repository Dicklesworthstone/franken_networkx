"""Parity coverage for the ``franken_networkx.hybrid`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest

PUBLIC_FUNCTIONS = ("is_kl_connected", "kl_connected_subgraph")


def _canonical_edges(graph):
    return sorted(tuple(sorted(edge)) for edge in graph.edges())


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _assert_same_graph(actual, expected):
    assert isinstance(actual, fnx.Graph)
    assert not actual.is_directed()
    assert not actual.is_multigraph()
    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert _canonical_edges(actual) == _canonical_edges(expected)


def test_direct_hybrid_module_import_exposes_public_surface():
    module = importlib.import_module("franken_networkx.hybrid")
    expected = importlib.import_module("networkx.algorithms.hybrid")

    assert set(module.__all__) == set(expected.__all__)
    for name in set(expected.__all__) | set(PUBLIC_FUNCTIONS):
        assert callable(getattr(module, name))


def test_algorithms_hybrid_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.hybrid")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.hybrid")

    assert via_algorithms is direct
    assert fnx.algorithms.hybrid is direct


def test_hybrid_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.hybrid")
    expected = importlib.import_module("networkx.algorithms.hybrid")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: {actual_repr} != {expected_repr}"
            )


def test_hybrid_module_routes_through_fnx_top_level(monkeypatch):
    module = importlib.import_module("franken_networkx.hybrid")
    graph = fnx.cycle_graph(4)
    connected_sentinel = object()
    subgraph_sentinel = object()

    def fake_is_kl_connected(
        actual_graph,
        k,
        l,
        low_memory=False,
        *,
        backend=None,
        **kwargs,
    ):
        _expect(actual_graph is graph, "is_kl_connected must forward the graph")
        _expect((k, l) == (2, 2), "is_kl_connected must forward k/l")
        _expect(low_memory, "is_kl_connected must forward low_memory")
        _expect(backend == "sentinel", "is_kl_connected must forward backend")
        _expect(kwargs == {"strict": True}, "is_kl_connected must forward backend kwargs")
        return connected_sentinel

    def fake_kl_connected_subgraph(
        actual_graph,
        k,
        l,
        low_memory=False,
        same_as_graph=False,
        *,
        backend=None,
        **kwargs,
    ):
        _expect(actual_graph is graph, "kl_connected_subgraph must forward the graph")
        _expect((k, l) == (2, 2), "kl_connected_subgraph must forward k/l")
        _expect(low_memory, "kl_connected_subgraph must forward low_memory")
        _expect(same_as_graph, "kl_connected_subgraph must forward same_as_graph")
        _expect(backend == "sentinel", "kl_connected_subgraph must forward backend")
        _expect(
            kwargs == {"strict": True},
            "kl_connected_subgraph must forward backend kwargs",
        )
        return subgraph_sentinel

    monkeypatch.setattr(fnx, "is_kl_connected", fake_is_kl_connected)
    monkeypatch.setattr(fnx, "kl_connected_subgraph", fake_kl_connected_subgraph)

    _expect(
        module.is_kl_connected(
            graph,
            2,
            2,
            low_memory=True,
            backend="sentinel",
            strict=True,
        )
        is connected_sentinel,
        "hybrid.is_kl_connected must route through fnx",
    )
    _expect(
        module.kl_connected_subgraph(
            graph,
            2,
            2,
            low_memory=True,
            same_as_graph=True,
            backend="sentinel",
            strict=True,
        )
        is subgraph_sentinel,
        "hybrid.kl_connected_subgraph must route through fnx",
    )


@pytest.mark.parametrize(
    ("fnx_graph", "nx_graph", "expected_connected"),
    [
        (fnx.cycle_graph(5), nx.cycle_graph(5), True),
        (fnx.path_graph(5), nx.path_graph(5), False),
        (fnx.complete_graph(4), nx.complete_graph(4), True),
        (fnx.barbell_graph(3, 1), nx.barbell_graph(3, 1), False),
    ],
)
@pytest.mark.parametrize("low_memory", [False, True])
def test_hybrid_kl_connected_family_matches_networkx(
    fnx_graph, nx_graph, expected_connected, low_memory
):
    module = importlib.import_module("franken_networkx.hybrid")

    actual_connected = module.is_kl_connected(
        fnx_graph, 2, 2, low_memory=low_memory
    )
    try:
        expected = nx.is_kl_connected(nx_graph, 2, 2, low_memory=low_memory)
    except nx.NetworkXError as exc:
        if not low_memory or "Frozen graph can't be modified" not in str(exc):
            raise
        expected = expected_connected
    assert actual_connected == expected == expected_connected

    actual_subgraph = module.kl_connected_subgraph(
        fnx_graph, 2, 2, low_memory=low_memory
    )
    try:
        expected_subgraph = nx.kl_connected_subgraph(
            nx_graph, 2, 2, low_memory=low_memory
        )
    except nx.NetworkXError as exc:
        if not low_memory or "Frozen graph can't be modified" not in str(exc):
            raise
        expected_subgraph = nx.kl_connected_subgraph(nx_graph, 2, 2)
    _assert_same_graph(actual_subgraph, expected_subgraph)


def test_kl_connected_subgraph_preserves_cluster_edges_and_drops_bridge():
    module = importlib.import_module("franken_networkx.hybrid")

    actual = module.kl_connected_subgraph(fnx.barbell_graph(3, 1), 2, 2)

    assert set(_canonical_edges(actual)) == {
        (0, 1),
        (0, 2),
        (1, 2),
        (4, 5),
        (4, 6),
        (5, 6),
    }


@pytest.mark.parametrize(
    "graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
)
@pytest.mark.parametrize("low_memory", [False, True])
@pytest.mark.parametrize("same_as_graph", [False, True])
@pytest.mark.parametrize("min_paths", [1, 2])
def test_kl_connected_subgraph_deep_copies_shared_attributes(
    graph_type, low_memory, same_as_graph, min_paths
):
    nodes = [(0, "a"), (1, "b"), (2, "c"), (3, "leaf")]
    edges = [
        (nodes[0], nodes[1]),
        (nodes[1], nodes[2]),
        (nodes[2], nodes[0]),
        (nodes[2], nodes[3]),
    ]

    def build(library):
        graph = getattr(library, graph_type)()
        graph.add_edges_from(edges)
        if graph.is_directed():
            graph.add_edges_from((v, u) for u, v in edges)
        if graph.is_multigraph():
            graph.add_edge(nodes[0], nodes[1], key=("parallel", 0))
        shared = {"values": []}
        graph.graph["payload"] = shared
        for node in graph:
            graph.nodes[node]["payload"] = shared
        for _, _, data in graph.edges(data=True):
            data["payload"] = shared
        return graph

    source = build(fnx)
    oracle_source = build(nx)
    actual = fnx.kl_connected_subgraph(
        source, 2, min_paths, low_memory=low_memory, same_as_graph=same_as_graph
    )
    expected = nx.kl_connected_subgraph(
        oracle_source, 2, min_paths, low_memory=low_memory, same_as_graph=same_as_graph
    )
    if same_as_graph:
        actual, actual_unchanged = actual
        expected, expected_unchanged = expected
        assert actual_unchanged == expected_unchanged == (min_paths == 1)

    assert type(actual) is getattr(fnx, graph_type)
    assert set(actual) == set(expected)
    if source.is_multigraph():
        assert list(actual.edges(keys=True)) == list(expected.edges(keys=True))
        assert list(source.edges(keys=True)) == list(oracle_source.edges(keys=True))
    else:
        assert list(actual.edges()) == list(expected.edges())
        assert list(source.edges()) == list(oracle_source.edges())

    for original, copied in [(source, actual), (oracle_source, expected)]:
        payload = copied.graph["payload"]
        assert payload is not original.graph["payload"]
        assert all(copied.nodes[node]["payload"] is payload for node in copied)
        assert all(data["payload"] is payload for _, _, data in copied.edges(data=True))
        payload["values"].append("result")
        assert original.graph["payload"]["values"] == []
        original.graph["payload"]["values"].append("input")
        assert payload["values"] == ["result"]


def test_hybrid_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.hybrid")

    with pytest.raises(TypeError):
        module.is_kl_connected(fnx.path_graph(3), 2, 2, unsupported=True)
