"""Aggregate verification tests for top-level parity and late-added wrappers."""

import inspect

import networkx as nx

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


def test_networkx_public_function_parity_has_no_gaps():
    missing = sorted(_public_functions(nx) - _public_functions(fnx))
    assert missing == []


def test_lcf_graph_wrapper_matches_networkx():
    graph = fnx.LCF_graph(6, [3, -3], 3)
    graph_nx = nx.LCF_graph(6, [3, -3], 3)

    assert sorted(graph.edges()) == sorted(graph_nx.edges())


def test_lfr_benchmark_graph_wrapper_smoke():
    graph = fnx.LFR_benchmark_graph(
        30,
        3,
        1.5,
        0.1,
        average_degree=4,
        min_community=10,
        seed=1,
    )

    assert graph.number_of_nodes() == 30
    assert graph.number_of_edges() > 0
