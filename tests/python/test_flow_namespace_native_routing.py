"""``franken_networkx.flow`` routes high-level helpers to fnx natives.

``from networkx.algorithms.flow import *`` left max-flow/min-cut/min-cost
helpers bound to NetworkX's implementations even though fnx has top-level
native versions with local parity/perf fixes. The root flow module now routes
through those fnx implementations; deeper child modules remain NetworkX
aliases.

br-r37-c1-ojs7g
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import flow as fnx_flow
from franken_networkx.algorithms import flow as fnx_alg_flow


_ROUTED_NAMES = (
    "capacity_scaling",
    "cost_of_flow",
    "gomory_hu_tree",
    "max_flow_min_cost",
    "maximum_flow",
    "maximum_flow_value",
    "min_cost_flow",
    "min_cost_flow_cost",
    "minimum_cut",
    "minimum_cut_value",
    "network_simplex",
)


def _max_flow_graph(lib):
    graph = lib.DiGraph()
    graph.add_edge("s", "a", capacity=3)
    graph.add_edge("s", "b", capacity=2)
    graph.add_edge("a", "b", capacity=1)
    graph.add_edge("a", "t", capacity=2)
    graph.add_edge("b", "t", capacity=4)
    return graph


def _min_cost_graph(lib):
    graph = lib.DiGraph()
    graph.add_node("s", demand=-4)
    graph.add_node("a", demand=0)
    graph.add_node("b", demand=0)
    graph.add_node("t", demand=4)
    graph.add_edge("s", "a", capacity=3, weight=1)
    graph.add_edge("s", "b", capacity=2, weight=3)
    graph.add_edge("a", "t", capacity=3, weight=2)
    graph.add_edge("b", "t", capacity=2, weight=1)
    return graph


def _gomory_hu_graph(lib):
    graph = lib.Graph()
    graph.add_edge(0, 1, capacity=3)
    graph.add_edge(1, 2, capacity=2)
    graph.add_edge(0, 2, capacity=4)
    graph.add_edge(2, 3, capacity=5)
    return graph


def _weighted_edges(graph):
    return sorted(
        (min(u, v), max(u, v), data.get("weight"))
        for u, v, data in graph.edges(data=True)
    )


@pytest.mark.parametrize("name", _ROUTED_NAMES)
def test_flow_namespace_routes_through_top_level_fnx(monkeypatch, name):
    marker = object()

    def sentinel(*args, **kwargs):
        assert args == ("payload",)
        assert kwargs == {"flag": True}
        return marker

    monkeypatch.setattr(fnx, name, sentinel)

    assert getattr(fnx_flow, name)("payload", flag=True) is marker
    assert getattr(fnx_alg_flow, name)("payload", flag=True) is marker


@pytest.mark.parametrize("name", _ROUTED_NAMES)
def test_flow_namespace_function_is_not_networkx_version(name):
    assert getattr(fnx_flow, name) is not getattr(nx.algorithms.flow, name)
    assert getattr(fnx_alg_flow, name) is getattr(fnx_flow, name)


def test_flow_namespace_max_flow_and_min_cut_values_match_networkx():
    fg = _max_flow_graph(fnx)
    ng = _max_flow_graph(nx)

    assert fnx_flow.maximum_flow_value(fg, "s", "t") == nx.maximum_flow_value(
        ng,
        "s",
        "t",
    )
    assert fnx_flow.minimum_cut_value(fg, "s", "t") == nx.minimum_cut_value(
        ng,
        "s",
        "t",
    )
    assert fnx_alg_flow.maximum_flow(fg, "s", "t")[0] == nx.maximum_flow(
        ng,
        "s",
        "t",
    )[0]
    assert fnx_alg_flow.minimum_cut(fg, "s", "t")[0] == nx.minimum_cut(
        ng,
        "s",
        "t",
    )[0]


def test_flow_namespace_min_cost_values_match_networkx():
    fg = _min_cost_graph(fnx)
    ng = _min_cost_graph(nx)

    assert fnx_flow.min_cost_flow_cost(fg) == nx.min_cost_flow_cost(ng)
    assert fnx_alg_flow.network_simplex(fg)[0] == nx.network_simplex(ng)[0]
    assert fnx_flow.capacity_scaling(fg)[0] == nx.capacity_scaling(ng)[0]

    fnx_flow_dict = fnx_flow.max_flow_min_cost(_max_flow_graph(fnx), "s", "t")
    nx_flow_dict = nx.max_flow_min_cost(_max_flow_graph(nx), "s", "t")
    fnx_cost = fnx_flow.cost_of_flow(_max_flow_graph(fnx), fnx_flow_dict)
    nx_cost = nx.cost_of_flow(
        _max_flow_graph(nx),
        nx_flow_dict,
    )
    assert fnx_cost == nx_cost


def test_flow_namespace_gomory_hu_tree_matches_networkx_edges():
    fg = _gomory_hu_graph(fnx)
    ng = _gomory_hu_graph(nx)

    ft = fnx_flow.gomory_hu_tree(fg)
    nt = nx.gomory_hu_tree(ng)

    assert isinstance(ft, fnx.Graph)
    assert _weighted_edges(ft) == _weighted_edges(nt)
