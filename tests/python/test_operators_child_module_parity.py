"""Parity for nested ``franken_networkx.algorithms.operators`` imports."""

from __future__ import annotations

import importlib

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import operators as fnx_operators
from networkx.algorithms import operators as nx_operators


def test_algorithms_operators_child_submodules_import_like_networkx():
    for name in ("all", "binary", "product", "unary"):
        actual = importlib.import_module(
            f"franken_networkx.algorithms.operators.{name}"
        )
        expected = importlib.import_module(f"networkx.algorithms.operators.{name}")

        assert actual is expected


def test_algorithms_operators_from_import_exposes_child_module():
    from franken_networkx.algorithms.operators import product

    actual = product.cartesian_product(nx.path_graph(2), nx.path_graph(2))
    expected = nx.algorithms.operators.product.cartesian_product(
        nx.path_graph(2), nx.path_graph(2)
    )

    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert sorted(actual.edges()) == sorted(expected.edges())


def _edge_snapshot(graph):
    if graph.is_multigraph():
        edge_iter = graph.edges(keys=True, data=True)
    else:
        edge_iter = ((u, v, None, data) for u, v, data in graph.edges(data=True))
    edges = []
    for source, target, key, data in edge_iter:
        endpoints = (repr(source), repr(target))
        if not graph.is_directed():
            endpoints = tuple(sorted(endpoints))
        edges.append((endpoints, repr(key), tuple(sorted(data.items()))))
    return sorted(edges)


def _graph_snapshot(graph):
    return (
        graph.is_directed(),
        graph.is_multigraph(),
        sorted((repr(node), tuple(sorted(data.items()))) for node, data in graph.nodes(data=True)),
        _edge_snapshot(graph),
        tuple(sorted(graph.graph.items())),
    )


def _path_graph(module, n, *, label):
    graph = module.path_graph(n)
    graph.graph["label"] = label
    for node in graph:
        graph.nodes[node]["node_attr"] = f"{label}-{node}"
    for index, edge in enumerate(graph.edges()):
        graph.edges[edge]["weight"] = index + 1
    return graph


@pytest.mark.parametrize(
    ("name", "fnx_args", "nx_args"),
    [
        (
            "disjoint_union",
            lambda: (_path_graph(fnx, 2, label="left"), _path_graph(fnx, 3, label="right")),
            lambda: (_path_graph(nx, 2, label="left"), _path_graph(nx, 3, label="right")),
        ),
        (
            "cartesian_product",
            lambda: (_path_graph(fnx, 2, label="left"), _path_graph(fnx, 3, label="right")),
            lambda: (_path_graph(nx, 2, label="left"), _path_graph(nx, 3, label="right")),
        ),
        (
            "tensor_product",
            lambda: (_path_graph(fnx, 2, label="left"), _path_graph(fnx, 3, label="right")),
            lambda: (_path_graph(nx, 2, label="left"), _path_graph(nx, 3, label="right")),
        ),
        (
            "rooted_product",
            lambda: (_path_graph(fnx, 2, label="left"), _path_graph(fnx, 3, label="right"), 0),
            lambda: (_path_graph(nx, 2, label="left"), _path_graph(nx, 3, label="right"), 0),
        ),
        (
            "corona_product",
            lambda: (_path_graph(fnx, 2, label="left"), _path_graph(fnx, 2, label="right")),
            lambda: (_path_graph(nx, 2, label="left"), _path_graph(nx, 2, label="right")),
        ),
        (
            "power",
            lambda: (_path_graph(fnx, 4, label="graph"), 2),
            lambda: (_path_graph(nx, 4, label="graph"), 2),
        ),
        (
            "compose_all",
            lambda: ([_path_graph(fnx, 2, label="left"), _path_graph(fnx, [1, 2], label="right")],),
            lambda: ([_path_graph(nx, 2, label="left"), _path_graph(nx, [1, 2], label="right")],),
        ),
        (
            "disjoint_union_all",
            lambda: ([_path_graph(fnx, 2, label="left"), _path_graph(fnx, 3, label="right")],),
            lambda: ([_path_graph(nx, 2, label="left"), _path_graph(nx, 3, label="right")],),
        ),
    ],
)
def test_operators_module_wrappers_match_networkx_on_fnx_inputs(
    name, fnx_args, nx_args
):
    result = getattr(fnx_operators, name)(*fnx_args())
    expected = getattr(nx_operators, name)(*nx_args())

    assert isinstance(result, fnx.Graph)
    assert _graph_snapshot(result) == _graph_snapshot(expected)
