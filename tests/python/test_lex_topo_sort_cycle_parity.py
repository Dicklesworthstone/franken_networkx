"""Parity for ``lexicographical_topological_sort`` cycle detection.

Bead br-r37-c1-kw1ke. fnx silently yielded a partial order on cyclic
input — the prefix of nodes that drained into the cycle, then stopped.
nx raises ``NetworkXUnfeasible('Graph contains a cycle or graph
changed during iteration')``. Drop-in code that catches the exception
to detect cycles failed on fnx — silent partial result masked the
contract violation.
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
def test_lex_topo_sort_full_cycle_raises_unfeasible():
    G = fnx.DiGraph([(0, 1), (1, 0)])
    GX = nx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(fnx.NetworkXUnfeasible) as fnx_exc:
        list(fnx.lexicographical_topological_sort(G))
    with pytest.raises(nx.NetworkXUnfeasible) as nx_exc:
        list(nx.lexicographical_topological_sort(GX))
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_lex_topo_sort_partial_cycle_raises_unfeasible():
    """Cycle reachable only after some prefix should still raise."""
    G = fnx.DiGraph([(0, 1), (1, 2), (2, 1)])
    GX = nx.DiGraph([(0, 1), (1, 2), (2, 1)])
    with pytest.raises(fnx.NetworkXUnfeasible):
        list(fnx.lexicographical_topological_sort(G))
    with pytest.raises(nx.NetworkXUnfeasible):
        list(nx.lexicographical_topological_sort(GX))


@needs_nx
def test_lex_topo_sort_dag_unchanged():
    """The fix must not regress DAG topological ordering."""
    G = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    GX = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    assert list(fnx.lexicographical_topological_sort(G)) == list(
        nx.lexicographical_topological_sort(GX)
    )


@needs_nx
def test_lex_topo_sort_empty_graph_yields_nothing():
    G = fnx.DiGraph()
    assert list(fnx.lexicographical_topological_sort(G)) == []


@needs_nx
def test_lex_topo_sort_single_node_yields_one():
    G = fnx.DiGraph()
    G.add_node(42)
    assert list(fnx.lexicographical_topological_sort(G)) == [42]


@needs_nx
def test_lex_topo_sort_self_loop_raises_unfeasible():
    """A self-loop is a (length-1) cycle."""
    G = fnx.DiGraph([(0, 0), (0, 1)])
    GX = nx.DiGraph([(0, 0), (0, 1)])
    with pytest.raises(fnx.NetworkXUnfeasible):
        list(fnx.lexicographical_topological_sort(G))
    with pytest.raises(nx.NetworkXUnfeasible):
        list(nx.lexicographical_topological_sort(GX))


@needs_nx
def test_lex_topo_sort_cycle_message_matches_networkx():
    G = fnx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(fnx.NetworkXUnfeasible) as exc:
        list(fnx.lexicographical_topological_sort(G))
    assert "cycle or graph changed during iteration" in str(exc.value)


@needs_nx
def test_lex_topo_sort_with_key_on_dag_unchanged():
    G = fnx.DiGraph([("c", "a"), ("c", "b")])
    GX = nx.DiGraph([("c", "a"), ("c", "b")])
    assert list(fnx.lexicographical_topological_sort(G, key=str)) == list(
        nx.lexicographical_topological_sort(GX, key=str)
    )


@needs_nx
def test_lex_topo_sort_disconnected_dag_yields_all():
    """Disconnected DAGs (no cycle anywhere) yield all nodes."""
    G = fnx.DiGraph([(0, 1), (2, 3), (4, 5)])
    GX = nx.DiGraph([(0, 1), (2, 3), (4, 5)])
    f = list(fnx.lexicographical_topological_sort(G))
    n = list(nx.lexicographical_topological_sort(GX))
    assert sorted(f) == sorted(n) == [0, 1, 2, 3, 4, 5]
