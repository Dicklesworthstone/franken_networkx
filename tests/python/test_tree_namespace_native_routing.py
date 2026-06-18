"""``franken_networkx.tree`` routes to fnx-native tree functions/classes.

``from networkx.algorithms.tree import *`` left the tree predicates,
branching / spanning-tree builders, prufer/nested-tuple codecs and the
iterator / partition classes bound to networkx's objects instead of fnx's
native versions. Functions route via call-time closures; classes via direct
alias (so isinstance / class semantics are preserved).

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import tree as fnx_tree

_FUNCS = [
    "center", "is_arborescence", "is_branching", "is_forest", "is_tree", "join_trees",
    "maximum_branching", "maximum_spanning_arborescence", "maximum_spanning_edges",
    "minimum_branching", "minimum_spanning_arborescence", "minimum_spanning_edges",
    "number_of_spanning_trees", "partition_spanning_tree", "random_spanning_tree",
    "to_nested_tuple", "to_prufer_sequence",
]
_CLASSES = ["ArborescenceIterator", "EdgePartition", "SpanningTreeIterator"]


@pytest.mark.parametrize("name", _FUNCS + _CLASSES)
def test_tree_object_is_not_networkx_version(name):
    obj = getattr(fnx_tree, name)
    if hasattr(nx, name):
        assert obj is not getattr(nx, name)
    # Classes are routed by direct alias, so they ARE the fnx object. Functions
    # are routed via call-time closure wrappers (the namespace object is a
    # wrapper that forwards to fnx's native fn — value-forwarding is checked in
    # test_tree_function_values_match_networkx), so only "not nx" is asserted.
    if name in _CLASSES:
        assert obj is getattr(fnx, name)


def test_tree_function_values_match_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 3)])
    assert fnx_tree.is_tree(g) == nx.is_tree(ng)
    assert fnx_tree.is_forest(g) == nx.is_forest(ng)
    assert fnx_tree.center(g) == nx.algorithms.tree.center(ng)
    assert round(fnx_tree.number_of_spanning_trees(fnx.complete_graph(4))) == 16
    # prufer round-trip through the namespace.
    rebuilt = fnx.from_prufer_sequence([0, 0])
    assert list(fnx_tree.to_prufer_sequence(rebuilt)) == [0, 0]


def test_tree_center_routes_through_fnx_top_level(monkeypatch):
    from franken_networkx.algorithms import tree as algorithms_tree

    graph = fnx.path_graph(5)
    sentinel = object()
    calls = []

    def fake_center(G):
        calls.append(G)
        return sentinel

    monkeypatch.setattr(fnx, "center", fake_center)

    assert fnx_tree.center(graph) is sentinel
    assert algorithms_tree.center(graph) is sentinel
    assert calls == [graph, graph]


@pytest.mark.parametrize(
    "builder",
    [
        lambda lib: lib.Graph(),
        lambda lib: lib.Graph([(0, 1), (2, 3)]),
        lambda lib: lib.cycle_graph(4),
    ],
)
def test_tree_center_not_tree_guards_match_networkx(builder):
    graph = builder(fnx)
    expected = builder(nx)

    with pytest.raises(nx.NotATree) as fnx_exc:
        fnx_tree.center(graph)
    with pytest.raises(nx.NotATree) as nx_exc:
        nx.algorithms.tree.center(expected)

    assert str(fnx_exc.value) == str(nx_exc.value)


def test_tree_center_directed_guard_matches_networkx():
    graph = fnx.DiGraph([(0, 1), (1, 2)])
    expected = nx.DiGraph([(0, 1), (1, 2)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        fnx_tree.center(graph)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.algorithms.tree.center(expected)

    assert str(fnx_exc.value) == str(nx_exc.value)


def test_edge_partition_class_routed():
    # EdgePartition is fnx's enum (used as a parameter); class identity matters.
    assert fnx_tree.EdgePartition is fnx.EdgePartition
