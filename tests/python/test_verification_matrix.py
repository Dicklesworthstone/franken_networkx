"""Aggregate verification tests for top-level parity and late-added wrappers."""

import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def _public_functions(module):
    names = set()
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if inspect.isfunction(obj) or inspect.isbuiltin(obj):
            names.add(name)
    return names


def _public_classes(module):
    names = set()
    for name in dir(module):
        if name.startswith("_"):
            continue
        if inspect.isclass(getattr(module, name)):
            names.add(name)
    return names


def _public_other_attrs(module):
    names = set()
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if not (inspect.isfunction(obj) or inspect.isbuiltin(obj) or inspect.isclass(obj)):
            names.add(name)
    return names


def test_networkx_public_function_parity_has_no_gaps():
    missing = sorted(_public_functions(nx) - _public_functions(fnx))
    assert missing == []


def test_networkx_public_namespace_parity_has_no_class_or_attr_gaps():
    missing_classes = sorted(_public_classes(nx) - _public_classes(fnx))
    missing_other_attrs = sorted(_public_other_attrs(nx) - _public_other_attrs(fnx))

    assert missing_classes == []
    assert missing_other_attrs == []


def test_lcf_graph_wrapper_matches_networkx():
    graph = fnx.LCF_graph(6, [3, -3], 3)
    graph_nx = nx.LCF_graph(6, [3, -3], 3)

    assert sorted(graph.edges()) == sorted(graph_nx.edges())


def test_lfr_benchmark_graph_wrapper_smoke():
    params = {
        "n": 30,
        "tau1": 3,
        "tau2": 1.5,
        "mu": 0.1,
        "average_degree": 4,
        "min_community": 10,
        "seed": 1,
    }
    expected = nx.LFR_benchmark_graph(**params)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            nx,
            "LFR_benchmark_graph",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("networkx fallback should not be used"),
            ),
        )
        graph = fnx.LFR_benchmark_graph(**params)

    assert graph.number_of_nodes() == 30
    assert graph.number_of_edges() == expected.number_of_edges()
    assert {frozenset(edge) for edge in graph.edges()} == {
        frozenset(edge) for edge in expected.edges()
    }
    assert {
        node: frozenset(graph.nodes[node]["community"])
        for node in graph.nodes()
    } == {
        node: frozenset(expected.nodes[node]["community"])
        for node in expected.nodes()
    }
