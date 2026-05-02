"""Metamorphic equivalence: transitive closure / reduction on DAGs.

Pairs with the existing tests/python/test_mst_algorithm_equivalence.py
and tests/python/test_shortest_path_algorithm_equivalence.py
metamorphic suites. Targets the algebraic relationship between
``transitive_closure`` and ``transitive_reduction`` on DAGs:

1. **Closure idempotency on a reduction**: for any DAG ``G``,
   ``transitive_closure(transitive_reduction(G))`` has the same edge
   set as ``transitive_closure(G)``. (The reduction strips redundant
   edges; the closure restores them.)

2. **Reduction-edge subset**: every edge in ``transitive_reduction(G)``
   is an edge of the original ``G``.

3. **Closure-edge superset**: every edge of ``G`` is an edge of
   ``transitive_closure(G)``.

4. **Self-loop absence in non-reflexive closure**: by default
   ``transitive_closure(G, reflexive=False)`` does NOT add self-loops
   (matches NX); the cycle-free DAG case never has paths ``v → v``.

5. **Reflexive closure**: ``transitive_closure(G, reflexive=True)``
   adds a self-loop on every node (NX contract). On an acyclic input
   this is the only difference from the non-reflexive variant.

Catches regressions where one of the two algorithms drifts from the
other — a class of bug that's invisible to per-function unit tests
because they only check absolute output, not the algebraic relation.
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


CONNECTED_DAG_FIXTURES = [
    # (name, builder)
    ("triangle_dag", lambda: nx.DiGraph([("a", "b"), ("b", "c"), ("a", "c")])),
    ("diamond_dag", lambda: nx.DiGraph(
        [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d")]
    )),
    ("chain_5", lambda: nx.DiGraph(
        [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"),
         ("a", "c"), ("a", "d"), ("a", "e"),
         ("b", "d"), ("b", "e"),
         ("c", "e")]
    )),
    ("balanced_tree_dag", lambda: nx.balanced_tree(2, 3, create_using=nx.DiGraph)),
    ("scale_free_15", lambda: _to_simple_dag(nx.scale_free_graph(15, seed=42))),
]


def _to_simple_dag(g):
    """Collapse parallel edges and remove cycles by keeping only edges
    that go from lower to higher node index — simple DAG fixture for
    the closure / reduction tests."""
    simple = nx.DiGraph()
    for u, v in set(g.edges()):
        if u != v and int(u) < int(v):
            simple.add_edge(u, v)
    simple.add_nodes_from(g.nodes())
    return simple


def _build_fnx_dag(nx_graph):
    f = fnx.DiGraph()
    f.add_nodes_from(nx_graph.nodes())
    f.add_edges_from(nx_graph.edges())
    return f


@needs_nx
@pytest.mark.parametrize(("name", "builder"), CONNECTED_DAG_FIXTURES)
def test_closure_of_reduction_equals_closure_of_original(name, builder):
    nx_graph = builder()
    f_graph = _build_fnx_dag(nx_graph)

    tr = fnx.transitive_reduction(f_graph)
    tc = fnx.transitive_closure(f_graph)
    tc_of_tr = fnx.transitive_closure(tr)

    assert sorted(tc.edges()) == sorted(tc_of_tr.edges()), (
        f"{name}: closure-of-reduction edge set diverged from closure"
    )


@needs_nx
@pytest.mark.parametrize(("name", "builder"), CONNECTED_DAG_FIXTURES)
def test_reduction_edges_are_subset_of_original(name, builder):
    nx_graph = builder()
    f_graph = _build_fnx_dag(nx_graph)
    tr = fnx.transitive_reduction(f_graph)
    original_edges = set(f_graph.edges())
    for u, v in tr.edges():
        assert (u, v) in original_edges, (
            f"{name}: reduction edge ({u}, {v}) not in original DAG"
        )


@needs_nx
@pytest.mark.parametrize(("name", "builder"), CONNECTED_DAG_FIXTURES)
def test_closure_edges_are_superset_of_original(name, builder):
    nx_graph = builder()
    f_graph = _build_fnx_dag(nx_graph)
    tc = fnx.transitive_closure(f_graph)
    closure_edges = set(tc.edges())
    for u, v in f_graph.edges():
        assert (u, v) in closure_edges, (
            f"{name}: original edge ({u}, {v}) missing from closure"
        )


@needs_nx
@pytest.mark.parametrize(("name", "builder"), CONNECTED_DAG_FIXTURES)
def test_closure_no_self_loops_when_non_reflexive(name, builder):
    nx_graph = builder()
    f_graph = _build_fnx_dag(nx_graph)
    tc = fnx.transitive_closure(f_graph, reflexive=False)
    for u, v in tc.edges():
        assert u != v, (
            f"{name}: non-reflexive transitive_closure should not add "
            f"self-loops, but found ({u}, {v})"
        )


@needs_nx
@pytest.mark.parametrize(("name", "builder"), CONNECTED_DAG_FIXTURES)
def test_reflexive_closure_adds_self_loop_on_every_node(name, builder):
    nx_graph = builder()
    f_graph = _build_fnx_dag(nx_graph)
    tc = fnx.transitive_closure(f_graph, reflexive=True)
    for n in f_graph.nodes():
        assert tc.has_edge(n, n), (
            f"{name}: reflexive transitive_closure missing self-loop on {n}"
        )


@needs_nx
def test_reduction_of_already_reduced_dag_is_identity():
    """If G is already a transitive reduction of itself (no shortcut
    edges), transitive_reduction(G) must equal G."""
    f = fnx.DiGraph()
    f.add_edge("a", "b")
    f.add_edge("b", "c")  # no a→c shortcut
    tr = fnx.transitive_reduction(f)
    assert sorted(tr.edges()) == sorted(f.edges())
    assert sorted(tr.nodes()) == sorted(f.nodes())


@needs_nx
def test_closure_of_already_closed_dag_is_identity():
    """If G already contains all transitively-implied edges, the
    closure is G itself (modulo node order)."""
    f = fnx.DiGraph()
    f.add_edge("a", "b")
    f.add_edge("b", "c")
    f.add_edge("a", "c")  # already closed
    tc = fnx.transitive_closure(f)
    assert sorted(tc.edges()) == sorted(f.edges())
