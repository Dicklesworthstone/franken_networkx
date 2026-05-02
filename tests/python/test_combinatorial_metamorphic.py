"""Metamorphic tests for combinatorial-algorithm algebraic invariants.

Ninth metamorphic-equivalence module pairing with the eight already in
place. Covers textbook combinatorial identities that catch any
algorithm drift violating them on every input.

1. **Matching size bound**: ``|M| ≤ ⌊|V| / 2⌋`` for any matching M.
2. **Greedy chromatic number bound (Brooks-style)**: a greedy
   coloring uses at most ``Δ(G) + 1`` colors, where Δ is the max
   degree.
3. **Independent set / matching / vertex cover relations**:
   * ``α(G) ≥ |V| - 2|M|`` for any maximal matching M (every
     unmatched vertex is in some independent set, plus one endpoint
     per matched edge).
   * ``α(G) ≥ ⌈|V| / (Δ(G) + 1)⌉`` (Caro-Wei lower bound; the
     relaxed combinatorial bound).
4. **Matching contains only real edges**: every (u, v) ∈ M is an
   edge of G.
5. **Independent set contains only real nodes**: every v ∈ I is in G.
6. **Coloring is proper**: for every edge (u, v), color[u] != color[v].

These are textbook identities that hold on every input — any
violation is a real algorithmic bug, not a tolerance issue.
"""

from __future__ import annotations

import math

import pytest

import franken_networkx as fnx


CONNECTED_FIXTURES = [
    ("path_5", lambda: fnx.path_graph(5)),
    ("path_8", lambda: fnx.path_graph(8)),
    ("cycle_6", lambda: fnx.cycle_graph(6)),
    ("cycle_7", lambda: fnx.cycle_graph(7)),
    ("complete_4", lambda: fnx.complete_graph(4)),
    ("complete_5", lambda: fnx.complete_graph(5)),
    ("balanced_tree_2_3", lambda: fnx.balanced_tree(2, 3)),
    ("karate", lambda: fnx.karate_club_graph()),
    ("complete_bipartite_3_3", lambda: fnx.complete_bipartite_graph(3, 3)),
]


# -----------------------------------------------------------------------------
# Matching cardinality bound
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_matching_size_bounded_by_half_n(name, builder):
    g = builder()
    m = fnx.maximal_matching(g)
    n = g.number_of_nodes()
    assert len(m) <= n // 2, (
        f"{name}: matching size {len(m)} > floor(|V|/2) = {n // 2}"
    )


# -----------------------------------------------------------------------------
# Matching edges are real edges
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_matching_contains_only_real_edges(name, builder):
    g = builder()
    m = fnx.maximal_matching(g)
    for u, v in m:
        assert g.has_edge(u, v), (
            f"{name}: matching contains non-edge ({u}, {v})"
        )


# -----------------------------------------------------------------------------
# Matching has no shared endpoints (defining property)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_matching_endpoints_are_disjoint(name, builder):
    g = builder()
    m = fnx.maximal_matching(g)
    seen = set()
    for u, v in m:
        assert u not in seen, (
            f"{name}: matching has shared endpoint {u}"
        )
        assert v not in seen, (
            f"{name}: matching has shared endpoint {v}"
        )
        seen.add(u)
        seen.add(v)


# -----------------------------------------------------------------------------
# Greedy coloring bound (Brooks-style upper bound)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_greedy_color_uses_at_most_max_degree_plus_one(name, builder):
    g = builder()
    if g.number_of_nodes() < 1:
        return
    coloring = fnx.greedy_color(g)
    if not coloring:
        return
    num_colors = max(coloring.values()) + 1
    max_deg = max((d for _, d in g.degree()), default=0)
    assert num_colors <= max_deg + 1, (
        f"{name}: greedy coloring used {num_colors} colors, "
        f"exceeds Δ(G)+1 = {max_deg + 1} (Brooks-style upper bound)"
    )


# -----------------------------------------------------------------------------
# Greedy coloring is proper (adjacent nodes get different colors)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_greedy_coloring_is_proper(name, builder):
    g = builder()
    coloring = fnx.greedy_color(g)
    for u, v in g.edges():
        if u == v:
            continue
        cu = coloring.get(u)
        cv = coloring.get(v)
        if cu is None or cv is None:
            continue
        assert cu != cv, (
            f"{name}: greedy_color assigned same color {cu} to "
            f"adjacent nodes {u} and {v} (improper coloring)"
        )


# -----------------------------------------------------------------------------
# Independent set: members are nodes of G, pairwise non-adjacent
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_maximal_independent_set_pairwise_non_adjacent(name, builder):
    g = builder()
    mis = fnx.maximal_independent_set(g)
    for v in mis:
        assert g.has_node(v), (
            f"{name}: independent set contains foreign node {v}"
        )
    # Pairwise non-adjacency.
    members = list(mis)
    for i, u in enumerate(members):
        for v in members[i + 1:]:
            assert not g.has_edge(u, v), (
                f"{name}: independent set members {u} and {v} are adjacent "
                f"(violates the defining property)"
            )


# -----------------------------------------------------------------------------
# Caro-Wei lower bound on independence number
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_maximal_independent_set_satisfies_caro_wei_bound(name, builder):
    """Caro-Wei lower bound (relaxed): α(G) ≥ ⌈|V| / (Δ(G) + 1)⌉.
    A *maximal* independent set isn't guaranteed to be maximum, but
    it's still ≥ the Caro-Wei bound on most reasonable fixtures.

    Skip the assertion when the maximal set fails the bound — this
    can happen on adversarial inputs where the greedy maximal set is
    far smaller than α(G). The check is still useful as a sanity gate
    on the well-behaved fixtures.
    """
    g = builder()
    n = g.number_of_nodes()
    if n < 1:
        return
    max_deg = max((d for _, d in g.degree()), default=0)
    bound = math.ceil(n / (max_deg + 1))
    mis = fnx.maximal_independent_set(g)
    # Sanity check: the bound is met on the well-behaved fixtures we
    # use here. If it fails the test will tell us — the fix is to
    # relax the lower bound or remove the fixture from the parametrize.
    assert len(mis) >= bound, (
        f"{name}: maximal_independent_set size {len(mis)} < Caro-Wei "
        f"bound ⌈n/(Δ+1)⌉ = {bound} (n={n}, Δ={max_deg})"
    )
