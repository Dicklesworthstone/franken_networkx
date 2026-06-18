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

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import classes as fnx_classes

_TYPES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
_FUNCS = [
    "add_cycle", "add_path", "all_neighbors", "create_empty_copy", "degree",
    "degree_histogram", "density", "edges", "induced_subgraph", "is_directed",
    "neighbors", "nodes", "non_edges", "number_of_edges", "number_of_nodes",
    "number_of_selfloops", "selfloop_edges", "subgraph", "to_directed",
    "to_undirected",
]


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
