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
    "is_arborescence", "is_branching", "is_forest", "is_tree", "join_trees",
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
    assert round(fnx_tree.number_of_spanning_trees(fnx.complete_graph(4))) == 16
    # prufer round-trip through the namespace.
    rebuilt = fnx.from_prufer_sequence([0, 0])
    assert list(fnx_tree.to_prufer_sequence(rebuilt)) == [0, 0]


def test_edge_partition_class_routed():
    # EdgePartition is fnx's enum (used as a parameter); class identity matters.
    assert fnx_tree.EdgePartition is fnx.EdgePartition
