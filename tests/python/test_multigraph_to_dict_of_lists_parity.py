from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _build(module, graph_name):
    graph = getattr(module, graph_name)()
    graph.add_node("isolated")
    graph.add_edge("a", "b", key="first", weight=1)
    graph.add_edge("a", "b", key="second", weight=2)
    graph.add_edge("b", "c", key=3)
    graph.add_edge("c", "c", key="loop")
    graph.add_edge("c", "a", key="return")
    return graph


@needs_nx
@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
def test_to_dict_of_lists_multigraph_matches_networkx(graph_name):
    assert fnx.to_dict_of_lists(_build(fnx, graph_name)) == nx.to_dict_of_lists(
        _build(nx, graph_name)
    )


@needs_nx
@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
def test_to_dict_of_lists_multigraph_nodelist_fallback_matches_networkx(graph_name):
    nodelist = ["c", "a", "isolated"]
    assert fnx.to_dict_of_lists(_build(fnx, graph_name), nodelist=nodelist) == (
        nx.to_dict_of_lists(_build(nx, graph_name), nodelist=nodelist)
    )


@needs_nx
@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("nodelist", [None, [2, 0]])
def test_to_dict_of_lists_reads_assigned_rows(graph_name, nodelist):
    expected = getattr(nx, graph_name)()
    expected.add_nodes_from([2, 1, 0])
    expected.add_edges_from([(0, 1), (0, 2), (2, 2)])
    graph = getattr(fnx, graph_name)([("hidden", "native")])
    graph._node = expected._node
    graph._adj = expected._adj
    if graph.is_directed():
        graph._succ = expected._succ
        graph._pred = expected._pred
    assert fnx.to_dict_of_lists(graph, nodelist=nodelist) == nx.to_dict_of_lists(expected, nodelist=nodelist)
    graph.add_edge(1, 2)
    assert fnx.to_dict_of_lists(graph, nodelist=nodelist) == nx.to_dict_of_lists(expected, nodelist=nodelist)
