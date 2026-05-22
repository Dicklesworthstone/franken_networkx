"""br-r37-c1-oxb5n: boundary submodule import parity."""

from __future__ import annotations

import importlib
import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def _expect(condition, message):
    if not condition:
        pytest.fail(message)


def test_boundary_module_is_directly_importable():
    module = importlib.import_module("franken_networkx.boundary")

    _expect(module.edge_boundary is fnx.edge_boundary, "edge_boundary should use fnx wrapper")
    _expect(module.node_boundary is fnx.node_boundary, "node_boundary should use fnx wrapper")


def test_boundary_module_public_surface_matches_networkx():
    fnx_boundary = importlib.import_module("franken_networkx.boundary")
    nx_boundary = importlib.import_module("networkx.algorithms.boundary")

    nx_public = {name for name in dir(nx_boundary) if not name.startswith("_")}
    fnx_public = {name for name in dir(fnx_boundary) if not name.startswith("_")}

    missing = nx_public - fnx_public
    _expect(not missing, f"franken_networkx.boundary missing {sorted(missing)}")


def test_boundary_module_signatures_match_networkx():
    fnx_boundary = importlib.import_module("franken_networkx.boundary")
    nx_boundary = importlib.import_module("networkx.algorithms.boundary")

    for name in ("edge_boundary", "node_boundary"):
        fnx_view = str(inspect.signature(getattr(fnx_boundary, name)))
        nx_view = str(inspect.signature(getattr(nx_boundary, name)))
        _expect(fnx_view == nx_view, f"{name}: fnx {fnx_view} != nx {nx_view}")


def test_boundary_module_functions_match_networkx_values():
    fnx_graph = fnx.path_graph(5)
    nx_graph = nx.path_graph(5)

    _expect(
        list(fnx.boundary.edge_boundary(fnx_graph, [0, 1]))
        == list(nx.edge_boundary(nx_graph, [0, 1])),
        "edge_boundary values should match NetworkX",
    )
    _expect(
        fnx.boundary.node_boundary(fnx_graph, [0, 1])
        == nx.node_boundary(nx_graph, [0, 1]),
        "node_boundary values should match NetworkX",
    )


def test_algorithms_boundary_path_uses_fnx_module():
    direct = importlib.import_module("franken_networkx.boundary")
    through_algorithms = importlib.import_module("franken_networkx.algorithms.boundary")

    _expect(through_algorithms is direct, "algorithms.boundary should use the fnx module")
    _expect(
        list(through_algorithms.edge_boundary(fnx.path_graph(5), [0, 1]))
        == list(nx.edge_boundary(nx.path_graph(5), [0, 1])),
        "algorithms.boundary should match NetworkX values",
    )
