"""Behavioral parity for suspended native traversal state."""

import gc
import weakref

import networkx as nx
import pytest

import franken_networkx as fnx


GRAPH_TYPES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _graph(module, graph_type, reverse=False):
    graph = getattr(module, graph_type)()
    graph.add_nodes_from(range(8))
    edges = [(0, 1), (0, 2), (1, 3), (2, 4)]
    if reverse and graph.is_directed():
        edges = [(v, u) for u, v in edges]
    graph.add_edges_from(edges)
    if graph.is_multigraph():
        graph.add_edge(*(edges[0]), key="parallel")
    return graph


def _edge(graph, u, v, reverse):
    return (v, u) if reverse and graph.is_directed() else (u, v)


def _remaining(iterator):
    result = []
    try:
        for value in iterator:
            result.append(("yield", value))
    except Exception as error:
        result.append(("error", type(error).__name__, error.args))
    return result


@pytest.mark.parametrize("reverse", [0, 1])
@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_public_bfs_preserves_truthy_reverse_arguments(graph_type, reverse):
    graph = _graph(fnx, graph_type)
    expected_graph = _graph(nx, graph_type)
    assert list(fnx.bfs_edges(graph, 3, reverse=reverse)) == list(
        nx.bfs_edges(expected_graph, 3, reverse=reverse)
    )


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("reverse", [False, True])
def test_bfs_observes_changes_to_rows_not_opened_yet(graph_type, reverse):
    observations = []
    for module in (fnx, nx):
        graph = _graph(module, graph_type, reverse)
        walk = module.bfs_edges(graph, 0, reverse=reverse)
        first = next(walk)
        graph.add_edge(*_edge(graph, 2, 5, reverse))
        graph.remove_edge(*_edge(graph, 2, 4, reverse))
        observations.append((first, _remaining(walk)))
    assert observations[0] == observations[1]
    assert ("yield", (2, 5)) in observations[0][1]
    assert ("yield", (2, 4)) not in observations[0][1]


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("row", [0, 1])
def test_bfs_retains_active_row_iterators_and_their_errors(graph_type, reverse, row):
    observations = []
    for module in (fnx, nx):
        graph = _graph(module, graph_type, reverse)
        walk = module.bfs_edges(graph, 0, reverse=reverse)
        first = next(walk)
        # Row 0 is being consumed; row 1 was opened before its edge yielded.
        graph.add_edge(*_edge(graph, row, 5, reverse))
        observations.append((first, _remaining(walk)))
    assert observations[0] == observations[1]
    assert observations[0][1][-1][0:2] == ("error", "RuntimeError")


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("reverse", [False, True])
def test_bfs_reads_only_the_requested_prefix_and_binds_the_provider(graph_type, reverse):
    observations = []
    for module in (fnx, nx):
        graph = _graph(module, graph_type, reverse)
        method = "predecessors" if reverse and graph.is_directed() else "neighbors"
        original = getattr(graph, method)
        opened, consumed = [], []

        class Cursor:
            def __init__(self, node):
                self.node = node
                self.row = original(node)

            def __iter__(self):
                return self

            def __next__(self):
                child = next(self.row)
                consumed.append((self.node, child))
                return child

        def neighbors(node):
            opened.append(node)
            return Cursor(node)

        setattr(graph, method, neighbors)
        walk = module.bfs_edges(graph, 0, reverse=reverse)
        assert opened == consumed == []
        first = next(walk)
        prefix = (opened.copy(), consumed.copy())

        def replaced(node):
            raise AssertionError("the provider was rebound after iteration started")

        setattr(graph, method, replaced)
        second = next(walk)
        before_close = (opened.copy(), consumed.copy())
        walk.close()
        assert (opened, consumed) == before_close
        observations.append((first, prefix, second, before_close))
    assert observations[0] == observations[1]
    assert observations[0][1] == ([0, 1], [(0, 1)])


@pytest.mark.parametrize("depth_limit", [0, 1, None])
def test_bfs_defers_iterating_custom_row_objects_until_their_level(depth_limit):
    observations = []
    for module in (fnx, nx):
        graph = _graph(module, "Graph")
        original = graph.neighbors
        events = []

        class Row:
            def __init__(self, node):
                self.node = node
                self.children = original(node)

            def __iter__(self):
                events.append(("iter", self.node))
                return self

            def __next__(self):
                child = next(self.children)
                events.append(("next", self.node, child))
                return child

        def neighbors(node):
            events.append(("open", node))
            return Row(node)

        graph.neighbors = neighbors
        walk = module.bfs_edges(graph, 0, depth_limit=depth_limit)
        prefixes = []
        for _ in range(3):
            try:
                value = next(walk)
            except StopIteration:
                prefixes.append(("stop", events.copy()))
                break
            prefixes.append((value, events.copy()))
        walk.close()
        observations.append(prefixes)
    assert observations[0] == observations[1]


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("depth_limit", [100, 1 << 100])
def test_bfs_explicit_depth_is_not_clamped_to_the_original_graph_size(graph_type, depth_limit):
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(range(5))
        graph.add_edges_from([(0, 1), (0, 2)])
        walk = module.bfs_edges(graph, 0, depth_limit=depth_limit)
        first = next(walk)
        # This row grows the seen set past the original count in one parent;
        # the following chain must still reach the caller's explicit depth.
        graph.add_edges_from([(2, 3), (2, 4), (2, 5), (2, 6)])
        graph.add_edges_from((node, node + 1) for node in range(6, 15))
        observations.append((first, _remaining(walk)))
    assert observations[0] == observations[1]
    assert observations[0][1][-1] == ("yield", (14, 15))


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_bfs_private_storage_replacement_affects_future_row_lookups(graph_type):
    observations = []
    for module in (fnx, nx):
        graph = _graph(module, graph_type)
        walk = module.bfs_edges(graph, 0)
        first = next(walk)
        replacement = _graph(nx, graph_type)
        replacement.add_edge(2, 5)
        if graph.is_directed():
            graph._succ = replacement._succ
            graph._pred = replacement._pred
        else:
            graph._adj = replacement._adj
        observations.append((first, _remaining(walk)))
    assert observations[0] == observations[1]
    assert ("yield", (2, 5)) in observations[0][1]


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_bfs_preserves_exceptions_raised_by_the_bound_neighbor_provider(graph_type):
    graph = _graph(fnx, graph_type)
    error = fnx.NodeNotFound("raised by the caller's provider")

    def neighbors(node):
        raise error

    graph.neighbors = neighbors
    walk = fnx.bfs_edges(graph, 0)
    with pytest.raises(fnx.NodeNotFound) as raised:
        next(walk)
    assert raised.value is error


def test_bfs_preserves_generator_stopiteration_conversion_from_callbacks():
    for module in (fnx, nx):
        graph = _graph(module, "Graph")
        error = StopIteration("neighbor provider stopped unexpectedly")

        def neighbors(node):
            raise error

        graph.neighbors = neighbors
        walk = module.bfs_edges(graph, 0)
        with pytest.raises(RuntimeError, match="generator raised StopIteration") as raised:
            next(walk)
        assert raised.value.__cause__ is error
        assert raised.value.__context__ is error
        assert list(walk) == []


def test_native_bfs_state_participates_in_cyclic_garbage_collection():
    # The native helper owns Python references, including arbitrary node
    # objects. This cycle exercises its GC protocol independently of the
    # native graph classes' separate lifecycle.
    from franken_networkx._fnx import bfs_edges_iter

    class Node:
        pass

    def abandoned():
        source, child = Node(), Node()
        graph = nx.Graph([(source, child)])
        iterator = bfs_edges_iter(graph, source)
        assert next(iterator) == (source, child)
        source.iterator = iterator
        return weakref.ref(source)

    reference = abandoned()
    gc.collect()
    assert reference() is None
