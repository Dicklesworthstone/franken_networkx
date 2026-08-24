"""``franken_networkx.classes`` exposes fnx-native graph types + helpers.

``from networkx.classes import *`` left the core graph TYPES
(Graph/DiGraph/MultiGraph/MultiDiGraph) and ~42 helper functions bound to
networkx's objects, so ``from franken_networkx.classes import Graph``
returned ``nx.Graph`` (a serious drop-in bug) and ``fnx.classes.degree``
etc. resolved to nx's helpers. Types now alias the fnx natives; functions
route via call-time wrappers.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import classes as fnx_classes

_TYPES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
_FUNCS = [
    "add_cycle", "add_path", "all_neighbors", "create_empty_copy", "degree",
    "degree_histogram", "density", "edges", "induced_subgraph", "is_directed",
    "neighbors", "nodes", "non_edges", "number_of_edges", "number_of_nodes",
    "number_of_selfloops", "selfloop_edges", "subgraph", "to_directed",
    "to_undirected",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_classes_function"
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


@pytest.mark.parametrize("name", _TYPES)
def test_graph_type_is_fnx_native(name):
    cls = getattr(fnx_classes, name)
    assert cls is getattr(fnx, name)
    assert cls is not getattr(nx, name)


@pytest.mark.parametrize("name", _FUNCS)
def test_helper_fn_is_not_networkx_version(name):
    fn = getattr(fnx_classes, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


def test_imported_graph_type_instantiates_fnx_native():
    from franken_networkx.classes import Graph, DiGraph

    g = Graph([(0, 1), (1, 2)])
    assert type(g).__module__.startswith("franken_networkx")
    assert isinstance(g, fnx.Graph)
    assert fnx_classes.number_of_edges(g) == 2
    dg = DiGraph([(0, 1)])
    assert isinstance(dg, fnx.DiGraph)


def test_helper_function_values_match_networkx():
    g = fnx.complete_graph(4)
    ng = nx.complete_graph(4)
    assert fnx_classes.degree_histogram(g) == nx.degree_histogram(ng)
    assert fnx_classes.density(g) == pytest.approx(nx.density(ng))
    assert fnx_classes.number_of_nodes(g) == nx.number_of_nodes(ng)


def test_classes_functional_view_argument_contract_matches_legacy_oracle():
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph([("a", "b")])
    graph = fnx.Graph([("a", "b")])

    with pytest.raises(TypeError) as legacy_error:
        legacy.classes.nodes(legacy_graph, ["a"])
    with pytest.raises(type(legacy_error.value)):
        fnx_classes.nodes(graph, ["a"])

    assert list(fnx_classes.edges(graph, nbunch=["a"])) == list(
        legacy.classes.edges(legacy_graph, nbunch=["a"])
    )
    assert list(fnx_classes.degree(graph, nbunch=["a"], weight=None)) == list(
        legacy.classes.degree(legacy_graph, nbunch=["a"], weight=None)
    )


@pytest.mark.parametrize("graph_type", ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"))
def test_classes_functional_views_match_legacy_oracle_and_remain_live(graph_type):
    legacy = _legacy_networkx()
    legacy_graph = getattr(legacy, graph_type)()
    graph = getattr(fnx, graph_type)()
    for candidate in (legacy_graph, graph):
        candidate.add_edge("a", "b", weight=2)
        candidate.add_edge("a", "a", weight=3)
        candidate.add_node("isolated")

    legacy_edges = legacy.classes.edges(legacy_graph, ["a"])
    edges = fnx_classes.edges(graph, ["a"])
    legacy_degree = legacy.classes.degree(legacy_graph, ["a"], weight="weight")
    degree = fnx_classes.degree(graph, ["a"], weight="weight")

    assert list(edges) == list(legacy_edges)
    assert list(degree) == list(legacy_degree)
    assert list(fnx_classes.nodes(graph)) == list(legacy.classes.nodes(legacy_graph))

    legacy_graph.add_edge("a", "late", weight=5)
    graph.add_edge("a", "late", weight=5)
    assert list(edges) == list(legacy_edges)
    assert degree["a"] == legacy_degree["a"]
