"""The parallel-edge dictionaries yielded by adjacency() belong to the graph."""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
def test_held_adjacency_keydict_shares_storage_and_writes(class_name):
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_edge("a", "b", key="first", weight=1)
        if graph.is_directed():
            graph.add_edge("b", "a", key="back")

        rows = dict(graph.adjacency())
        keys = rows["a"]["b"]
        assert keys is graph.get_edge_data("a", "b")
        assert (keys is rows["b"]["a"]) == (not graph.is_directed())

        graph.add_edge("a", "b", key="second", weight=2)
        assert list(keys) == ["first", "second"]
        assert dict(graph.adjacency())["a"]["b"] is keys

        keys["inserted"] = {"weight": 3}
        assert graph.get_edge_data("a", "b", "inserted") is keys["inserted"]
        assert graph.number_of_edges("a", "b") == 3
        assert ("a", "b", "inserted") in graph.edges(keys=True)
        del keys["second"]
        assert not graph.has_edge("a", "b", "second")
        assert graph.number_of_edges("a", "b") == 2
        if graph.is_directed():
            assert list(rows["b"]["a"]) == ["back"]


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("operation", ["remove_edge", "remove_node", "clear_edges", "clear"])
def test_retired_adjacency_keydict_stays_detached(class_name, operation):
    def observe(module):
        graph = getattr(module, class_name)()
        graph.add_edge("a", "a", key="old", weight=1)
        held = dict(graph.adjacency())["a"]["a"]
        if operation == "remove_edge":
            graph.remove_edge("a", "a", "old")
        elif operation == "remove_node":
            graph.remove_node("a")
        else:
            getattr(graph, operation)()

        graph.add_edge("a", "a", key="fresh", weight=2)
        replacement = dict(graph.adjacency())["a"]["a"]
        held["local"] = {"weight": 3}
        return (
            dict(held),
            dict(replacement),
            held is replacement,
            replacement is graph.get_edge_data("a", "a"),
            graph.number_of_edges(),
        )

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
def test_converted_rows_and_graph_copies_remain_independent(class_name):
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_edge("a", "b", key=0)
        row = dict(graph.adjacency())["a"]
        converted = module.to_dict_of_dicts(graph)
        assert converted["a"] is not row
        assert converted["a"]["b"] is row["b"]
        converted["a"].clear()
        assert "b" in dict(graph.adjacency())["a"]

        copied = graph.copy()
        copied.add_edge("a", "b", key=1)
        assert list(row["b"]) == [0]
        assert list(copied.get_edge_data("a", "b")) == [0, 1]
