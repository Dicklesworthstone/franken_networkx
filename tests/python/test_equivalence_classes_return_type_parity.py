"""Parity for ``equivalence_classes`` return type + iteration order.

Bead br-r37-c1-8hshk. fnx returned a ``list`` of frozensets in
input-iteration order; nx returns a ``set`` of frozensets (which
iterates in Python hash order). Both the return type and the
iteration order differed.

Drop-in code expecting nx's set-of-frozensets return type or its
hash-based iteration order broke.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_returns_set_not_list():
    """nx contract: return type is ``set`` (of frozensets)."""
    result = fnx.equivalence_classes(["a", "b", "c"], lambda x, y: x == y)
    assert isinstance(result, set)


@needs_nx
def test_str_node_identity_relation_matches_nx():
    nodes = ["a", "b", "c", "d", "e"]
    eq = lambda x, y: x == y
    assert fnx.equivalence_classes(nodes, eq) == nx.equivalence_classes(nodes, eq)


@needs_nx
def test_int_node_identity_relation_matches_nx():
    nodes = [1, 2, 3, 4, 5]
    eq = lambda x, y: x == y
    assert fnx.equivalence_classes(nodes, eq) == nx.equivalence_classes(nodes, eq)


@needs_nx
def test_modulo_relation_matches_nx():
    nodes = [1, 2, 3, 4, 5, 6]
    eq = lambda x, y: x % 2 == y % 2
    assert fnx.equivalence_classes(nodes, eq) == nx.equivalence_classes(nodes, eq)


@needs_nx
def test_modulo_relation_iteration_order_matches_nx():
    """list(set) order is hash-based but stable per process — fnx
    must match nx exactly."""
    nodes = [1, 2, 3, 4, 5, 6]
    eq = lambda x, y: x % 2 == y % 2
    assert list(fnx.equivalence_classes(nodes, eq)) == list(
        nx.equivalence_classes(nodes, eq)
    )


@needs_nx
def test_all_equal_yields_single_class():
    nodes = ["a", "b", "c"]
    always_true = lambda x, y: True
    f = fnx.equivalence_classes(nodes, always_true)
    n = nx.equivalence_classes(nodes, always_true)
    assert f == n
    assert len(f) == 1


@needs_nx
def test_all_distinct_yields_n_classes():
    nodes = ["a", "b", "c", "d"]
    always_false = lambda x, y: x == y  # only identity
    f = fnx.equivalence_classes(nodes, always_false)
    n = nx.equivalence_classes(nodes, always_false)
    assert f == n
    assert len(f) == len(nodes)


@needs_nx
def test_empty_iterable_returns_empty_set():
    f = fnx.equivalence_classes([], lambda x, y: x == y)
    n = nx.equivalence_classes([], lambda x, y: x == y)
    assert f == n == set()


@needs_nx
def test_string_substring_relation():
    """Custom relation: same first character."""
    words = ["apple", "ant", "bear", "bee", "cat"]
    eq = lambda x, y: x[0] == y[0]
    assert fnx.equivalence_classes(words, eq) == nx.equivalence_classes(words, eq)


@needs_nx
def test_iteration_order_matches_nx_str_nodes():
    """Specific regression: iteration order must match (hash-based but stable)."""
    nodes = ["a", "b", "c", "d", "e"]
    eq = lambda x, y: x == y
    assert list(fnx.equivalence_classes(nodes, eq)) == list(
        nx.equivalence_classes(nodes, eq)
    )
