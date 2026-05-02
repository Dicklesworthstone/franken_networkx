"""Metamorphic tests for graph-operator involutions and algebraic identities.

Pairs with the existing metamorphic suites:
- test_mst_algorithm_equivalence.py
- test_shortest_path_algorithm_equivalence.py
- test_dag_closure_reduction_equivalence.py

Covers algebraic identities on graph operators that catch a class of
bug invisible to per-function unit tests:

1. **complement(complement(G)) == G** — complement is an involution
   on simple undirected graphs.
2. **reverse(reverse(G)) == G** — reverse is an involution on
   directed graphs.
3. **condensation(G) is always a DAG** — by construction the
   condensation collapses every SCC into one node, eliminating cycles.
4. **subgraph(G, V) ⊆ G** — node-induced subgraph node and edge sets
   are subsets of G.
5. **edge_subgraph(G, E) ⊆ G** — edge-induced subgraph likewise.
6. **subgraph idempotence**: ``subgraph(subgraph(G, V), V) == subgraph(G, V)``.
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


UNDIRECTED_FIXTURES = [
    ("path_5", lambda: fnx.path_graph(5)),
    ("cycle_4", lambda: fnx.cycle_graph(4)),
    ("complete_4", lambda: fnx.complete_graph(4)),
    ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2)),
    ("isolated_3", lambda: _build_isolated(3)),
]

DIRECTED_FIXTURES = [
    ("dag_chain_5",
     lambda: fnx.DiGraph([("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")])),
    ("dag_diamond",
     lambda: fnx.DiGraph(
         [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d")]
     )),
    ("cycle_3_dir",
     lambda: fnx.DiGraph([("a", "b"), ("b", "c"), ("c", "a")])),
    ("two_sccs",
     lambda: fnx.DiGraph(
         [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c"), ("a", "c")]
     )),
]


def _build_isolated(n):
    g = fnx.Graph()
    for i in range(n):
        g.add_node(str(i))
    return g


def _canonical_edges(graph):
    """Return a sorted set of canonical edge tuples (each undirected
    edge represented by min,max-ordered endpoints)."""
    if graph.is_directed():
        return sorted(graph.edges())
    return sorted(tuple(sorted(e)) for e in graph.edges())


# -----------------------------------------------------------------------------
# Complement involution
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), UNDIRECTED_FIXTURES)
def test_complement_is_involution(name, builder):
    g = builder()
    cc = fnx.complement(fnx.complement(g))
    assert sorted(g.nodes()) == sorted(cc.nodes()), (
        f"{name}: complement(complement(G)) lost / added nodes"
    )
    assert _canonical_edges(g) == _canonical_edges(cc), (
        f"{name}: complement(complement(G)) edge set diverged"
    )


# -----------------------------------------------------------------------------
# Reverse involution (DiGraph)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DIRECTED_FIXTURES)
def test_reverse_is_involution(name, builder):
    g = builder()
    rr = g.reverse(copy=True).reverse(copy=True)
    assert sorted(g.nodes()) == sorted(rr.nodes()), (
        f"{name}: reverse(reverse(G)) lost / added nodes"
    )
    assert sorted(g.edges()) == sorted(rr.edges()), (
        f"{name}: reverse(reverse(G)) edge set diverged"
    )


# -----------------------------------------------------------------------------
# Condensation always produces a DAG
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DIRECTED_FIXTURES)
def test_condensation_is_acyclic(name, builder):
    g = builder()
    cond = fnx.condensation(g)
    # condensation may return a tuple (graph, mapping) on some fnx
    # versions; we want the graph itself.
    if isinstance(cond, tuple):
        cond_graph = cond[0]
    else:
        cond_graph = cond
    assert fnx.is_directed_acyclic_graph(cond_graph), (
        f"{name}: condensation must be a DAG (collapses every SCC)"
    )


# -----------------------------------------------------------------------------
# Subgraph subset relation
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), UNDIRECTED_FIXTURES)
def test_node_induced_subgraph_is_subset(name, builder):
    g = builder()
    nodes = list(g.nodes())
    if len(nodes) < 2:
        return
    subset = nodes[: len(nodes) // 2 + 1]
    sg = g.subgraph(subset)
    # Every node in sg is in g and in subset.
    for n in sg.nodes():
        assert n in subset, f"{name}: subgraph has foreign node {n}"
    # Every edge in sg is in g.
    g_edges = _canonical_edges(g)
    for e in _canonical_edges(sg):
        assert e in g_edges, (
            f"{name}: subgraph has edge {e} that's not in original"
        )


@pytest.mark.parametrize(("name", "builder"), UNDIRECTED_FIXTURES)
def test_subgraph_is_idempotent(name, builder):
    g = builder()
    nodes = list(g.nodes())
    if len(nodes) < 2:
        return
    subset = nodes[: len(nodes) // 2 + 1]
    sg1 = g.subgraph(subset)
    sg2 = sg1.subgraph(subset)
    assert sorted(sg1.nodes()) == sorted(sg2.nodes()), (
        f"{name}: subgraph not idempotent on node set"
    )
    assert _canonical_edges(sg1) == _canonical_edges(sg2), (
        f"{name}: subgraph not idempotent on edge set"
    )


# -----------------------------------------------------------------------------
# Edge-induced subgraph
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), UNDIRECTED_FIXTURES)
def test_edge_induced_subgraph_edges_are_subset(name, builder):
    g = builder()
    edges = list(g.edges())
    if len(edges) < 1:
        return
    take = edges[: max(1, len(edges) // 2)]
    sg = fnx.edge_subgraph(g, take)
    g_edges = _canonical_edges(g)
    for e in _canonical_edges(sg):
        assert e in g_edges, (
            f"{name}: edge_subgraph has edge {e} not in original"
        )
    # Every edge endpoint is a node of g.
    for n in sg.nodes():
        assert g.has_node(n), (
            f"{name}: edge_subgraph has node {n} not in original"
        )
