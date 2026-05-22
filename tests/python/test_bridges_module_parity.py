"""br-r37-c1-euvmn: bridges submodule import parity."""

from __future__ import annotations

import importlib
import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def _expect(condition, message):
    if not condition:
        pytest.fail(message)


def test_bridges_module_is_directly_importable():
    module = importlib.import_module("franken_networkx.bridges")
    _expect(module is not None, "franken_networkx.bridges did not import")
    _expect(module.has_bridges is fnx.has_bridges, "has_bridges should use the fnx wrapper")
    _expect(module.local_bridges is fnx.local_bridges, "local_bridges should use the fnx wrapper")


def test_bridges_module_public_surface_matches_networkx():
    fnx_bridges = importlib.import_module("franken_networkx.bridges")
    nx_bridges = importlib.import_module("networkx.algorithms.bridges")

    nx_public = {name for name in dir(nx_bridges) if not name.startswith("_")}
    fnx_public = {name for name in dir(fnx_bridges) if not name.startswith("_")}

    missing = nx_public - fnx_public
    _expect(not missing, f"franken_networkx.bridges missing {sorted(missing)}")


def test_bridges_module_signatures_match_networkx():
    fnx_bridges = importlib.import_module("franken_networkx.bridges")
    nx_bridges = importlib.import_module("networkx.algorithms.bridges")

    for name in ("bridges", "has_bridges", "local_bridges"):
        fnx_view = str(inspect.signature(getattr(fnx_bridges, name)))
        nx_view = str(inspect.signature(getattr(nx_bridges, name)))
        _expect(fnx_view == nx_view, f"{name}: fnx {fnx_view} != nx {nx_view}")


def test_bridges_module_functions_match_networkx_values():
    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    _expect(
        list(fnx.bridges.bridges(fnx_graph)) == list(nx.bridges(nx_graph)),
        "bridges values should match NetworkX",
    )
    _expect(
        fnx.bridges.has_bridges(fnx_graph) == nx.has_bridges(nx_graph),
        "has_bridges values should match NetworkX",
    )
    _expect(
        list(fnx.bridges.local_bridges(fnx_graph, with_span=False))
        == list(nx.local_bridges(nx_graph, with_span=False)),
        "local_bridges values should match NetworkX",
    )


def test_importing_bridges_module_keeps_top_level_bridges_callable():
    importlib.import_module("franken_networkx.bridges")

    fnx_view = str(inspect.signature(fnx.bridges))
    nx_view = str(inspect.signature(nx.bridges))

    _expect(callable(fnx.bridges), "fnx.bridges should remain callable after module import")
    _expect(fnx_view == nx_view, f"fnx.bridges signature {fnx_view} != nx {nx_view}")
    _expect(
        list(fnx.bridges(fnx.path_graph(4))) == list(nx.bridges(nx.path_graph(4))),
        "top-level fnx.bridges should keep matching NetworkX after module import",
    )


def test_algorithms_bridges_path_uses_fnx_module():
    direct = importlib.import_module("franken_networkx.bridges")
    through_algorithms = importlib.import_module("franken_networkx.algorithms.bridges")

    _expect(through_algorithms is direct, "algorithms.bridges should use the fnx module")
    _expect(
        list(through_algorithms.bridges(fnx.path_graph(4))) == list(nx.bridges(nx.path_graph(4))),
        "algorithms.bridges should match NetworkX values",
    )
