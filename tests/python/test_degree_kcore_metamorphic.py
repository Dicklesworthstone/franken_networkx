"""Metamorphic tests for degree / k-core / connectivity-bound invariants.

Seventh metamorphic-equivalence module pairing with the six already in
place. Covers algebraic invariants that follow directly from textbook
graph-theory identities and so catch any algorithm drift that would
violate them on every input.

1. **Handshaking lemma**: ``sum(deg(v) for v in G) == 2 * |E|``
   on undirected graphs (every edge contributes 1 to each endpoint).
2. **Directed degree balance**:
   ``sum(in_degree) == sum(out_degree) == |E|`` on DiGraphs.
3. **k-core monotonicity**: ``k_core(G, k+1) ⊆ k_core(G, k)``
   — the (k+1)-core is a subset of the k-core for every k.
4. **Core number bound**: every node's core number ``≤ deg(v)``
   (the (k+1)-core requires every member to have ≥ k+1 neighbors in
   the subgraph, so ``core_number(v) ≤ deg(v)``).
5. **Whitney inequality (connectivity bounds)**:
   ``node_connectivity(G) ≤ edge_connectivity(G) ≤ min_degree(G)``
   — Whitney's classical inequality.
6. **Self-loops never count**: on simple graphs, every node has
   ``deg(v) ≥ 0`` and ``deg(v) < |V|``.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


CONNECTED_FIXTURES = [
    ("path_5", lambda: fnx.path_graph(5)),
    ("cycle_5", lambda: fnx.cycle_graph(5)),
    ("complete_4", lambda: fnx.complete_graph(4)),
    ("complete_5", lambda: fnx.complete_graph(5)),
    ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2)),
    ("karate", lambda: fnx.karate_club_graph()),
    ("complete_bipartite_3_3", lambda: fnx.complete_bipartite_graph(3, 3)),
]

DIRECTED_FIXTURES = [
    ("dag_chain_5",
     lambda: fnx.DiGraph([("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")])),
    ("dag_diamond",
     lambda: fnx.DiGraph(
         [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d")]
     )),
    ("two_sccs",
     lambda: fnx.DiGraph(
         [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c"), ("a", "c")]
     )),
]


# -----------------------------------------------------------------------------
# Handshaking lemma
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_handshaking_lemma_undirected(name, builder):
    g = builder()
    deg_sum = sum(d for _, d in g.degree())
    m = g.number_of_edges()
    assert deg_sum == 2 * m, (
        f"{name}: handshaking lemma violated — sum(deg)={deg_sum}, "
        f"2|E|={2 * m}"
    )


# -----------------------------------------------------------------------------
# Directed degree balance
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DIRECTED_FIXTURES)
def test_directed_degree_balance(name, builder):
    g = builder()
    in_sum = sum(d for _, d in g.in_degree())
    out_sum = sum(d for _, d in g.out_degree())
    m = g.number_of_edges()
    assert in_sum == out_sum == m, (
        f"{name}: directed degree balance violated — "
        f"in_sum={in_sum}, out_sum={out_sum}, |E|={m}"
    )


# -----------------------------------------------------------------------------
# k-core monotonicity
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_k_core_monotonicity(name, builder):
    g = builder()
    core_numbers = fnx.core_number(g)
    if not core_numbers:
        return
    max_k = max(core_numbers.values())
    # nodes_at_or_above[k] = set of nodes whose core number is >= k.
    nodes_at_or_above = {
        k: {n for n, c in core_numbers.items() if c >= k}
        for k in range(max_k + 2)
    }
    for k in range(max_k + 1):
        higher = nodes_at_or_above[k + 1]
        lower = nodes_at_or_above[k]
        assert higher.issubset(lower), (
            f"{name}: (k+1)-core {higher} not a subset of k-core {lower} "
            f"(k={k})"
        )


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_core_number_bounded_by_degree(name, builder):
    g = builder()
    core_numbers = fnx.core_number(g)
    for v, c in core_numbers.items():
        deg_v = g.degree(v)
        assert c <= deg_v, (
            f"{name}: core_number({v}) = {c} > deg({v}) = {deg_v} — "
            f"impossible (would require more neighbors than exist)"
        )


# -----------------------------------------------------------------------------
# Whitney connectivity inequality
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_whitney_connectivity_inequality(name, builder):
    """Whitney's inequality: κ(G) ≤ λ(G) ≤ δ(G), where
    κ = node connectivity, λ = edge connectivity, δ = min degree."""
    g = builder()
    if g.number_of_nodes() < 2:
        return
    nc = fnx.node_connectivity(g)
    ec = fnx.edge_connectivity(g)
    min_deg = min(d for _, d in g.degree())
    assert nc <= ec, (
        f"{name}: node_connectivity {nc} > edge_connectivity {ec} "
        f"(Whitney's first inequality)"
    )
    assert ec <= min_deg, (
        f"{name}: edge_connectivity {ec} > min_degree {min_deg} "
        f"(Whitney's second inequality)"
    )


# -----------------------------------------------------------------------------
# Degree range on simple graphs
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_degree_in_simple_graph_range(name, builder):
    g = builder()
    n = g.number_of_nodes()
    if n < 1:
        return
    for v, deg_v in g.degree():
        assert deg_v >= 0, f"{name}: deg({v}) = {deg_v} is negative"
        assert deg_v < n, (
            f"{name}: deg({v}) = {deg_v} >= |V| = {n} on a simple graph "
            f"(no self-loops, no parallel edges)"
        )
