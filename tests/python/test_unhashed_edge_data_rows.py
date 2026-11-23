"""Live edge values for callback-sensitive directed graph copy loops."""

from __future__ import annotations

import gc
import weakref

import networkx as nx
import pytest

import franken_networkx as fnx


DIRECTIONS = [
    ("DiGraph", False),
    ("DiGraph", True),
    ("MultiDiGraph", False),
    ("MultiDiGraph", True),
]


def _edge(reverse, neighbor):
    return (neighbor, 0) if reverse else (0, neighbor)


def _add(graph, reverse, neighbor, weight, key="initial"):
    if graph.is_multigraph():
        graph.add_edge(*_edge(reverse, neighbor), key=key, weight=weight)
    else:
        graph.add_edge(*_edge(reverse, neighbor), weight=weight)


def _remove(graph, reverse, neighbor, key="initial"):
    if graph.is_multigraph():
        graph.remove_edge(*_edge(reverse, neighbor), key=key)
    else:
        graph.remove_edge(*_edge(reverse, neighbor))


def _cursor(lib, graph, reverse):
    if lib is fnx:
        return graph._fnx_unhashed_neighbor_data_items(0, reverse=reverse)
    rows = graph._pred if reverse else graph._succ
    return iter(rows[0].items())


def _value(data, multi):
    if multi:
        return [(key, dict(attrs)) for key, attrs in data.items()]
    return dict(data)


def _item(value, multi):
    neighbor, data = value
    return neighbor, _value(data, multi)


def _drain(iterator, multi):
    output = []
    while True:
        try:
            value = next(iterator)
        except StopIteration:
            return output, "stop"
        except RuntimeError as exc:
            return output, type(exc).__name__, exc.args
        output.append(_item(value, multi))


@pytest.mark.parametrize("cls_name,reverse", DIRECTIONS)
@pytest.mark.parametrize("consumed", [0, 1])
@pytest.mark.parametrize(
    "mutation",
    [
        "update_attrs",
        "replace_future_edge",
        "replace_future_then_detach",
        "replace_future_then_detach_readd",
        "replace_neighbor_then_detach",
        "add_neighbor",
        "remove_neighbor",
        "clear_edges_readd",
        "clear_then_readd",
        "bulk_attrs",
        "parallel_keys",
        "remove_nodes_owner_first",
        "remove_nodes_owner_last",
    ],
)
def test_edge_data_cursor_tracks_values_and_detached_row_edits(
    cls_name, reverse, consumed, mutation
):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from(range(20))
        for neighbor in (1, 2, 3):
            _add(graph, reverse, neighbor, neighbor)
        multi = graph.is_multigraph()
        iterator = _cursor(lib, graph, reverse)
        prefix = [_item(next(iterator), multi) for _ in range(consumed)]

        if mutation == "update_attrs":
            data = graph.get_edge_data(*_edge(reverse, 2))
            if multi:
                data = data["initial"]
            data["weight"] = 20
        elif mutation.startswith("replace_future"):
            _remove(graph, reverse, 2)
            _add(graph, reverse, 2, 20, key="replacement")
            if "detach" in mutation:
                graph.remove_node(0)
            if mutation.endswith("readd"):
                _add(graph, reverse, 2, 200, key="new-owner")
        elif mutation == "replace_neighbor_then_detach":
            _remove(graph, reverse, 2)
            _add(graph, reverse, 4, 40)
            graph.remove_node(0)
        elif mutation == "add_neighbor":
            _add(graph, reverse, 4, 40)
        elif mutation == "remove_neighbor":
            _remove(graph, reverse, 2)
        elif mutation == "clear_edges_readd":
            graph.clear_edges()
            for neighbor in (4, 5, 6):
                _add(graph, reverse, neighbor, neighbor * 10)
        elif mutation == "clear_then_readd":
            graph.clear()
            _add(graph, reverse, 2, 200)
        elif mutation == "bulk_attrs":
            graph.add_edges_from(
                [(*_edge(reverse, neighbor), {"weight": neighbor * 10}) for neighbor in range(4, 16)]
            )
        elif mutation == "parallel_keys":
            _add(graph, reverse, 2, 20, key="second")
            if multi:
                _remove(graph, reverse, 2)
        elif mutation == "remove_nodes_owner_first":
            graph.remove_nodes_from([0, 2])
        elif mutation == "remove_nodes_owner_last":
            graph.remove_nodes_from([2, 0])
        else:
            raise AssertionError(mutation)

        outcome = _drain(iterator, multi)
        current = _drain(_cursor(lib, graph, reverse), multi) if 0 in graph else None
        results.append((prefix, outcome, current))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls_name,reverse", DIRECTIONS)
def test_edge_data_cursor_retains_actual_replacement_before_owner_detach(cls_name, reverse):
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        _add(graph, reverse, 1, 1)
        _add(graph, reverse, 2, 2)
        previous = graph.get_edge_data(*_edge(reverse, 2))
        iterator = _cursor(lib, graph, reverse)
        assert next(iterator)[0] == 1
        _remove(graph, reverse, 2)
        _add(graph, reverse, 2, 20, key="replacement")
        replacement = graph.get_edge_data(*_edge(reverse, 2))
        assert replacement is not previous
        graph.remove_node(0)
        _add(graph, reverse, 2, 200, key="new-owner")
        neighbor, retained = next(iterator)
        assert neighbor == 2
        assert retained is replacement
        assert retained is not graph.get_edge_data(*_edge(reverse, 2))
        expected = [("replacement", {"weight": 20})] if graph.is_multigraph() else {"weight": 20}
        assert _value(retained, graph.is_multigraph()) == expected


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("detach", [False, True])
def test_edge_data_cursor_sees_keydict_replacement_before_detach(reverse, detach):
    for lib in (nx, fnx):
        graph = lib.MultiDiGraph()
        _add(graph, reverse, 1, 1)
        _add(graph, reverse, 2, 2)
        previous = graph.get_edge_data(*_edge(reverse, 2))
        iterator = _cursor(lib, graph, reverse)
        assert next(iterator)[0] == 1
        source, target = _edge(reverse, 2)
        if lib is fnx:
            replacement = graph._fnx_replace_pair_with_edge(source, target, "fresh", {"weight": 20})
        else:
            replacement = {"fresh": {"weight": 20}}
            graph._succ[source][target] = replacement
            graph._pred[target][source] = replacement
        previous["initial"]["weight"] = -1
        if detach:
            graph.remove_node(0)
            _add(graph, reverse, 2, 200, key="new-owner")
        neighbor, retained = next(iterator)
        assert neighbor == 2
        assert retained is replacement
        assert _value(retained, True) == [("fresh", {"weight": 20})]


@pytest.mark.parametrize("cls_name,reverse", DIRECTIONS)
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("label_kind", ["int_subclass", "object"])
def test_edge_data_cursor_does_not_hash_existing_node_labels(cls_name, reverse, warm, label_kind):
    for lib in (nx, fnx):
        armed = False

        class Label:
            def __init__(self, value):
                self.value = value

            def __hash__(self):
                if armed:
                    raise RuntimeError("data row hashed an existing node")
                return self.value

            def __eq__(self, other):
                if armed:
                    raise RuntimeError("data row compared an existing node")
                return isinstance(other, Label) and self.value == other.value

        class IntLabel(int):
            def __hash__(self):
                if armed:
                    raise RuntimeError("data row hashed an existing node")
                return int.__hash__(self)

        label = IntLabel(1) if label_kind == "int_subclass" else Label(197)
        graph = getattr(lib, cls_name)()
        _add(graph, reverse, label, 10)
        if warm:
            list(_cursor(lib, graph, reverse))
        armed = True
        values = list(_cursor(lib, graph, reverse))
        armed = False
        assert len(values) == 1
        assert values[0][0] is label


@pytest.mark.parametrize("cls_name,reverse", DIRECTIONS)
def test_edge_data_cursor_retains_first_equal_label(cls_name, reverse):
    for lib in (nx, fnx):
        class Label(int):
            pass

        first, second = Label(1), Label(1)
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from([0, 1])
        _add(graph, reverse, first, 10)
        iterator = _cursor(lib, graph, reverse)
        _add(graph, reverse, second, 20)
        label, data = next(iterator)
        assert label is first
        expected = [("initial", {"weight": 20})] if graph.is_multigraph() else {"weight": 20}
        assert _value(data, graph.is_multigraph()) == expected


@pytest.mark.parametrize("cls_name,reverse", DIRECTIONS)
def test_edge_data_cursor_visits_graph_and_label_cycles(cls_name, reverse):
    class Label:
        pass

    graph = getattr(fnx, cls_name)()
    label = Label()
    label.graph = graph
    _add(graph, reverse, label, 10)
    iterator = _cursor(fnx, graph, reverse)
    assert next(iterator)[0] is label
    reference = weakref.ref(label)
    del iterator, graph, label
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("cls_name,reverse", DIRECTIONS)
def test_edge_data_cursor_preserves_directed_self_loop_detachment(cls_name, reverse):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        for neighbor in (1, 0, 2):
            _add(graph, reverse, neighbor, neighbor + 10)
        iterator = _cursor(lib, graph, reverse)
        prefix = _item(next(iterator), graph.is_multigraph())
        graph.remove_node(0)
        results.append((prefix, _drain(iterator, graph.is_multigraph())))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls_name,reverse", DIRECTIONS)
def test_edge_data_cursor_detaches_actual_values_when_native_state_is_replaced(cls_name, reverse):
    graph = getattr(fnx, cls_name)()
    _add(graph, reverse, 1, 10)
    _add(graph, reverse, 2, 20)
    iterator = _cursor(fnx, graph, reverse)
    assert next(iterator)[0] == 1
    previous = graph.get_edge_data(*_edge(reverse, 2))
    replacement = getattr(fnx, cls_name)()
    _add(replacement, reverse, 2, 200, key="new-state")
    graph.__setstate__(replacement.__getstate__())
    neighbor, retained = next(iterator)
    assert neighbor == 2
    assert retained is previous
    expected_old = [("initial", {"weight": 20})] if graph.is_multigraph() else {"weight": 20}
    assert _value(retained, graph.is_multigraph()) == expected_old
    current_neighbor, current = next(_cursor(fnx, graph, reverse))
    assert current_neighbor == 2
    assert current is not previous
    expected_new = [("new-state", {"weight": 200})] if graph.is_multigraph() else {"weight": 200}
    assert _value(current, graph.is_multigraph()) == expected_new
