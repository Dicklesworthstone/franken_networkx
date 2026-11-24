"""Parity coverage for the ``franken_networkx.lowest_common_ancestors`` module."""

from __future__ import annotations

import importlib
import inspect
from itertools import islice

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "all_pairs_lowest_common_ancestor",
    "tree_all_pairs_lowest_common_ancestor",
    "lowest_common_ancestor",
)


def _build_dag_pair():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    fnx_graph.add_node(5)
    nx_graph.add_node(5)
    return fnx_graph, nx_graph


def _build_tree_pair():
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5)]
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def test_direct_lca_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_lca_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.lowest_common_ancestors")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.lowest_common_ancestors"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.lowest_common_ancestors is direct


def test_lca_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    expected = importlib.import_module("networkx.algorithms.lowest_common_ancestors")

    assert set(module.__all__) == set(expected.__all__)


def test_lca_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    expected = importlib.import_module("networkx.algorithms.lowest_common_ancestors")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


@pytest.mark.parametrize("node1,node2,default", [(1, 2, None), (3, 5, "missing")])
def test_lowest_common_ancestor_matches_networkx(node1, node2, default):
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, nx_graph = _build_dag_pair()

    assert module.lowest_common_ancestor(
        fnx_graph, node1, node2, default=default
    ) == nx.lowest_common_ancestor(nx_graph, node1, node2, default=default)


def test_all_pairs_lowest_common_ancestor_matches_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, nx_graph = _build_dag_pair()
    pairs = [(1, 2), (3, 4), (1, 4)]

    assert dict(module.all_pairs_lowest_common_ancestor(fnx_graph, pairs=pairs)) == dict(
        nx.all_pairs_lowest_common_ancestor(nx_graph, pairs=pairs)
    )


def test_tree_all_pairs_lowest_common_ancestor_matches_networkx():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, nx_graph = _build_tree_pair()
    pairs = [(3, 4), (3, 5), (1, 5)]

    assert dict(
        module.tree_all_pairs_lowest_common_ancestor(fnx_graph, root=0, pairs=pairs)
    ) == dict(nx.tree_all_pairs_lowest_common_ancestor(nx_graph, root=0, pairs=pairs))


def test_lca_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.lowest_common_ancestors")
    fnx_graph, _ = _build_dag_pair()

    with pytest.raises(TypeError):
        module.lowest_common_ancestor(fnx_graph, 1, 2, unsupported=True)


def _lca_api(namespace, name):
    if namespace == "top_level":
        return getattr(fnx, name)
    if namespace == "algorithms":
        return getattr(fnx.algorithms, name)
    return getattr(importlib.import_module(namespace), name)


LCA_NAMESPACES = (
    "top_level",
    "algorithms",
    "franken_networkx.lowest_common_ancestors",
    "franken_networkx.algorithms.lowest_common_ancestors",
)


@pytest.mark.parametrize("namespace", LCA_NAMESPACES)
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mutation", ["predecessors", "successors", "cached_ancestors"])
def test_dag_lca_keeps_only_completed_ancestor_sets(namespace, graph_type, mutation):
    def run(library, algorithm):
        graph = getattr(library, graph_type)([(0, 1), (1, 2), (1, 3), (3, 4)])
        if mutation == "predecessors":
            pairs = [(2, 3), (2, 4)]
        elif mutation == "successors":
            pairs = [(2, 3), (3, 2)]
        else:
            pairs = [(2, 3), (2, 1)]
        results = algorithm(graph, pairs=pairs)
        first = next(results)
        if mutation == "predecessors":
            graph.remove_edge(1, 3)
            graph.add_edge(0, 3)
        elif mutation == "successors":
            graph.remove_edge(0, 1)
        else:
            graph.remove_edge(1, 2)
            graph.add_edge(3, 2)
        return [first, *results]

    expected = run(nx, nx.all_pairs_lowest_common_ancestor)
    assert expected[0][1] == 1
    assert expected[1][1] == (1 if mutation == "cached_ancestors" else 0)
    assert run(fnx, _lca_api(namespace, "all_pairs_lowest_common_ancestor")) == expected


@pytest.mark.parametrize("namespace", LCA_NAMESPACES)
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("reader", ["predecessors", "successors"])
def test_dag_lca_uses_assigned_readers(namespace, graph_type, reader):
    def run(library, algorithm):
        graph = getattr(library, graph_type)([(0, 1), (1, 2), (1, 3)])
        original = getattr(graph, reader)
        calls = []

        def rows(node):
            calls.append(node)
            if reader == "predecessors" and node == 3:
                return iter([0])
            if reader == "successors" and node == 0:
                return iter(())
            return original(node)

        setattr(graph, reader, rows)
        return list(algorithm(graph, pairs=[(2, 3)])), calls

    expected = run(nx, nx.all_pairs_lowest_common_ancestor)
    assert expected[0] == [((2, 3), 0)]
    assert run(fnx, _lca_api(namespace, "all_pairs_lowest_common_ancestor")) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_dag_lca_binds_predecessor_reader_once_per_search(graph_type):
    def run(library, algorithm):
        graph = getattr(library, graph_type)([(0, 1), (1, 2), (1, 3)])
        original = graph.predecessors
        calls = []

        def replacement(node):
            calls.append(("replacement", node))
            return iter(())

        def predecessors(node):
            calls.append(("initial", node))
            graph.predecessors = replacement
            return original(node)

        graph.predecessors = predecessors
        return list(algorithm(graph, pairs=[(2, 3)])), calls

    expected = run(nx, nx.all_pairs_lowest_common_ancestor)
    assert expected[0] == []
    assert expected[1] == [("initial", 2), ("initial", 1), ("initial", 0), ("replacement", 3)]
    assert run(fnx, fnx.all_pairs_lowest_common_ancestor) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_dag_lca_validation_uses_live_degree_and_neighbor_readers(graph_type):
    def run(library, algorithm):
        graph = getattr(library, graph_type)([(0, 1), (1, 2)])
        calls = []

        def neighbors(node):
            calls.append(node)
            raise LookupError("LCA validation reader stopped")

        graph.neighbors = neighbors
        with pytest.raises(LookupError, match="LCA validation reader stopped") as exc:
            algorithm(graph, pairs=[(1, 2)])
        return calls, exc.value.args

    assert run(fnx, fnx.all_pairs_lowest_common_ancestor) == run(
        nx, nx.all_pairs_lowest_common_ancestor
    )


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_dag_lca_uses_replaced_class_readers(warm, graph_type, monkeypatch):
    def run(library, algorithm):
        graph_class = getattr(library, graph_type)
        graph = graph_class([(0, 1), (1, 2), (1, 3)])
        if warm:
            assert library.lowest_common_ancestor(graph, 2, 3) == 1
            for name in ("nodes", "edges", "pred", "succ", "adj", "in_degree"):
                getattr(graph, name)
        original = graph_class.predecessors
        calls = []

        def predecessors(self, node):
            calls.append(node)
            return iter([0]) if node == 3 else original(self, node)

        with monkeypatch.context() as patch:
            patch.setattr(graph_class, "predecessors", predecessors)
            results = list(algorithm(graph, pairs=[(2, 3)]))
        return results, calls

    assert run(fnx, fnx.all_pairs_lowest_common_ancestor) == run(
        nx, nx.all_pairs_lowest_common_ancestor
    )


@pytest.mark.parametrize("warm", [False, True])
def test_dag_lca_keeps_native_predecessor_rows_for_plain_graphs(warm, monkeypatch):
    graph = fnx.DiGraph([(0, 1), (1, 2), (1, 3)])
    if warm:
        for name in ("nodes", "edges", "pred", "succ", "adj", "in_degree"):
            getattr(graph, name)
    original = fnx._LCA_NATIVE_PREDECESSOR_ROW
    calls = []

    def native_row(owner, node):
        calls.append(node)
        return original(owner, node)

    monkeypatch.setattr(fnx, "_LCA_NATIVE_PREDECESSOR_ROW", native_row)
    assert list(fnx.all_pairs_lowest_common_ancestor(graph, pairs=[(2, 3)])) == [((2, 3), 1)]
    assert calls == [2, 1, 0, 3, 1, 0]


@pytest.mark.parametrize("namespace", LCA_NAMESPACES)
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("pairs", [None, [(1, 1), (3, 4), (4, 3), (1, 4)]])
def test_tree_lca_reads_unvisited_branches_after_yield(namespace, graph_type, pairs):
    def run(library, algorithm):
        graph = getattr(library, graph_type)([(0, 1), (0, 2), (2, 3), (2, 4)])
        results = algorithm(graph, root=0, pairs=pairs)
        first = next(results)
        assert first == ((1, 1), 1)
        graph.remove_edge(2, 4)
        graph.add_edge(3, 4)
        return [first, *results]

    expected = run(nx, nx.tree_all_pairs_lowest_common_ancestor)
    assert dict(expected).get((3, 4), dict(expected).get((4, 3))) == 3
    assert run(fnx, _lca_api(namespace, "tree_all_pairs_lowest_common_ancestor")) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("pairs", [None, [(1, 1), (2, 2)]])
def test_tree_lca_opens_only_reached_neighbor_rows(graph_type, pairs):
    def run(library, algorithm):
        graph = getattr(library, graph_type)([(0, 1), (0, 2)])
        original = graph.neighbors
        calls = []

        def neighbors(node):
            calls.append(node)
            if node == 2:
                raise LookupError("unvisited branch")
            return original(node)

        graph.neighbors = neighbors
        results = algorithm(graph, root=0, pairs=pairs)
        assert calls == []
        first = next(results)
        assert calls == [0, 1]
        with pytest.raises(LookupError, match="unvisited branch") as exc:
            list(results)
        return first, calls, exc.value.args

    expected = run(nx, nx.tree_all_pairs_lowest_common_ancestor)
    assert run(fnx, fnx.tree_all_pairs_lowest_common_ancestor) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_tree_lca_defers_parent_row_until_after_node_results(graph_type):
    def run(library, algorithm):
        graph = getattr(library, graph_type)([(0, 1), (0, 2)])
        calls = []

        class ParentRows:
            def __getitem__(self, node):
                calls.append(node)
                raise LookupError("parent row stopped")

        graph.pred = ParentRows()
        results = algorithm(graph, root=0)
        first = next(results)
        assert calls == []
        with pytest.raises(LookupError, match="parent row stopped") as exc:
            next(results)
        return first, calls, exc.value.args

    expected = run(nx, nx.tree_all_pairs_lowest_common_ancestor)
    assert run(fnx, fnx.tree_all_pairs_lowest_common_ancestor) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_tree_lca_prefix_does_not_materialize_all_pairs(graph_type, monkeypatch):
    def no_batch(*args, **kwargs):
        raise AssertionError("tree LCA must not materialize the complete result stream")

    monkeypatch.setattr(fnx._fnx, "tree_all_pairs_lca_rust", no_batch)
    graph = getattr(fnx, graph_type)()
    expected_graph = getattr(nx, graph_type)()
    edges = [(0, child) for child in range(1, 10001)]
    graph.add_edges_from(edges)
    expected_graph.add_edges_from(edges)
    results = fnx.tree_all_pairs_lowest_common_ancestor(graph, root=0)
    expected = nx.tree_all_pairs_lowest_common_ancestor(expected_graph, root=0)
    assert list(islice(results, 3)) == list(islice(expected, 3))
    results.close()
    expected.close()


@pytest.mark.parametrize("namespace", LCA_NAMESPACES)
@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
def test_tree_lca_rejects_undirected_graphs_on_call(namespace, graph_type):
    graph = getattr(fnx, graph_type)([(0, 1)])
    algorithm = _lca_api(namespace, "tree_all_pairs_lowest_common_ancestor")
    with pytest.raises(nx.NetworkXNotImplemented, match="not implemented for undirected type"):
        algorithm(graph)


def test_tree_lca_accepts_explicit_root_for_cyclic_input_like_networkx():
    graph = fnx.DiGraph([(0, 1), (1, 0)])
    expected_graph = nx.DiGraph([(0, 1), (1, 0)])
    assert list(fnx.tree_all_pairs_lowest_common_ancestor(graph, root=0)) == list(
        nx.tree_all_pairs_lowest_common_ancestor(expected_graph, root=0)
    )
