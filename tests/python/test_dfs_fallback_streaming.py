"""Edge DFS keeps its own suspension and row-provider behavior on Python routes."""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "route",
    ["native_view", "networkx", "networkx_view", "sorted", "float_depth", "zero_depth"],
)
def test_non_reflexive_nodes_do_not_create_synthetic_root_edges(graph_type, route):
    root = float("nan")
    edges = [(root, "branch"), ("branch", "leaf"), (root, "sibling")]
    source_lib = nx if route.startswith("networkx") else fnx
    actual = getattr(source_lib, graph_type)(edges)
    expected = getattr(nx, graph_type)(edges)
    if route.endswith("view"):
        actual = actual.subgraph([root, "branch", "leaf", "sibling"])
        expected = expected.subgraph([root, "branch", "leaf", "sibling"])
    kwargs = {}
    if route == "sorted":
        kwargs["sort_neighbors"] = lambda values: reversed(list(values))
    elif route == "float_depth":
        kwargs["depth_limit"] = 1.5
    elif route == "zero_depth":
        kwargs["depth_limit"] = 0
    for source in (root, None):
        result = list(fnx.dfs_edges(actual, source=source, **kwargs))
        assert result == list(nx.dfs_edges(expected, source=source, **kwargs))
        assert all(parent is not child for parent, child in result)


def test_edge_dfs_does_not_compare_a_root_to_itself():
    class Label:
        __hash__ = object.__hash__

        def __ne__(self, other):
            raise AssertionError("DFS must not compare endpoints of an artificial root edge")

    root = Label()
    graph = nx.DiGraph([(root, "child")])
    actual = fnx.dfs_edges(graph, source=root)
    expected = nx.dfs_edges(graph, source=root)
    assert next(actual) == next(expected) == (root, "child")
    assert list(actual) == list(expected) == []


def _graph_with_row_events(lib, as_view, provider_kind):
    graph = lib.DiGraph()
    graph.add_nodes_from(range(7))
    graph.add_edges_from([(0, 1), (0, 2), (1, 3), (1, 4), (3, 5)])
    view = graph.subgraph(range(7)) if as_view else graph
    events = []

    class Cursor:
        def __init__(self, node):
            self.node = node
            self.values = iter(view.adj[node])

        def __iter__(self):
            events.append(("cursor_iter", self.node))
            return self

        def __next__(self):
            events.append(("next", self.node))
            return next(self.values)

    class Row:
        def __init__(self, node):
            self.node = node

        def __iter__(self):
            events.append(("row_iter", self.node))
            return Cursor(self.node)

    def neighbors(node):
        events.append(("neighbors", node))
        return Cursor(node) if provider_kind == "iterator" else Row(node)

    view.neighbors = neighbors
    return graph, view, events


def _next_event(iterator):
    try:
        return "edge", next(iterator)
    except StopIteration:
        return ("stop",)


@pytest.mark.parametrize("input_kind", ["native_view", "networkx"])
@pytest.mark.parametrize("provider_kind", ["iterator", "iterable"])
@pytest.mark.parametrize("sorted_rows", [False, True])
def test_custom_rows_are_iterated_at_the_same_suspension_points(input_kind, provider_kind, sorted_rows):
    source_lib = fnx if input_kind == "native_view" else nx
    as_view = input_kind == "native_view"
    _, actual_graph, actual_events = _graph_with_row_events(source_lib, as_view, provider_kind)
    _, expected_graph, expected_events = _graph_with_row_events(nx, as_view, provider_kind)

    def sorter(events):
        def retain_order(values):
            events.append(("sort",))
            return values
        return retain_order

    actual_sort = sorter(actual_events) if sorted_rows else None
    expected_sort = sorter(expected_events) if sorted_rows else None
    actual = fnx.dfs_edges(actual_graph, source=0, sort_neighbors=actual_sort)
    expected = nx.dfs_edges(expected_graph, source=0, sort_neighbors=expected_sort)
    assert actual_events == expected_events == []
    for _ in range(16):
        result = _next_event(actual)
        assert result == _next_event(expected)
        assert actual_events == expected_events
        if result == ("stop",):
            assert _next_event(actual) == _next_event(expected) == ("stop",)
            break
    else:
        pytest.fail("DFS did not finish the bounded graph")


@pytest.mark.parametrize("input_kind", ["native_view", "networkx"])
def test_resuming_a_reiterable_parent_observes_a_new_edge(input_kind):
    source_lib = fnx if input_kind == "native_view" else nx
    as_view = input_kind == "native_view"
    actual_root, actual_graph, actual_events = _graph_with_row_events(source_lib, as_view, "iterable")
    expected_root, expected_graph, expected_events = _graph_with_row_events(nx, as_view, "iterable")
    actual = fnx.dfs_edges(actual_graph, source=0)
    expected = nx.dfs_edges(expected_graph, source=0)
    assert next(actual) == next(expected) == (0, 1)
    assert next(actual) == next(expected) == (1, 3)
    actual_root.add_edge(1, 6)
    expected_root.add_edge(1, 6)
    remainder = list(actual)
    assert remainder == list(expected)
    assert (1, 6) in remainder
    assert actual_events == expected_events


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("depth_limit", [-1, 0, False, 0.5, 1.5, float("inf"), float("nan")])
def test_python_depth_limits_keep_networkx_comparison_semantics(graph_type, depth_limit):
    edges = [(0, 1), (0, 2), (1, 3), (3, 4), (2, 4), (5, 6)]
    actual = getattr(fnx, graph_type)(edges)
    expected = getattr(nx, graph_type)(edges)
    for source in (0, None):
        assert list(fnx.dfs_edges(actual, source=source, depth_limit=depth_limit)) == list(
            nx.dfs_edges(expected, source=source, depth_limit=depth_limit)
        )
