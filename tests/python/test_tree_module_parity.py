"""No-mock parity coverage for the ``franken_networkx.tree`` module path."""

from __future__ import annotations

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import tree as fnx_tree
from networkx.algorithms import tree as nx_tree


def _weighted_triangle(module):
    graph = module.Graph()
    graph.add_edge(0, 1, weight=3)
    graph.add_edge(1, 2, weight=1)
    graph.add_edge(0, 2, weight=5)
    return graph


def _edge_snapshot(graph):
    edges = []
    for source, target, data in graph.edges(data=True):
        endpoints = tuple(sorted((repr(source), repr(target))))
        edges.append((endpoints, tuple(sorted(data.items()))))
    return sorted(edges)


def _graph_snapshot(graph):
    return (
        graph.is_directed(),
        graph.is_multigraph(),
        sorted(repr(node) for node in graph.nodes()),
        _edge_snapshot(graph),
    )


@pytest.mark.parametrize(
    ("name", "fnx_args", "nx_args"),
    [
        (
            "from_prufer_sequence",
            lambda: ([0, 0, 0],),
            lambda: ([0, 0, 0],),
        ),
        (
            "from_nested_tuple",
            lambda: (((), ((), ())),),
            lambda: (((), ((), ())),),
        ),
        (
            "junction_tree",
            lambda: (fnx.cycle_graph(4),),
            lambda: (nx.cycle_graph(4),),
        ),
        (
            "minimum_spanning_tree",
            lambda: (_weighted_triangle(fnx),),
            lambda: (_weighted_triangle(nx),),
        ),
        (
            "maximum_spanning_tree",
            lambda: (_weighted_triangle(fnx),),
            lambda: (_weighted_triangle(nx),),
        ),
    ],
)
def test_tree_module_graph_returning_wrappers_match_networkx(name, fnx_args, nx_args):
    fnx_kwargs = {"sensible_relabeling": True} if name == "from_nested_tuple" else {}
    nx_kwargs = dict(fnx_kwargs)

    result = getattr(fnx_tree, name)(*fnx_args(), **fnx_kwargs)
    expected = getattr(nx_tree, name)(*nx_args(), **nx_kwargs)

    assert isinstance(result, fnx.Graph)
    assert _graph_snapshot(result) == _graph_snapshot(expected)


@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.MultiGraph, nx.MultiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)],
)
def test_tree_module_junction_tree_multigraph_guard_matches_networkx(fnx_cls, nx_cls):
    graph = fnx_cls([(0, 1), (1, 2)])
    expected = nx_cls([(0, 1), (1, 2)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        fnx_tree.junction_tree(graph)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx_tree.junction_tree(expected)

    assert str(fnx_exc.value) == str(nx_exc.value)
