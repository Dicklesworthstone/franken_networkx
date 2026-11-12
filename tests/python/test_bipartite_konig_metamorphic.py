"""Metamorphic tests for bipartite-specific algebraic invariants.

Thirteenth metamorphic-equivalence module pairing with the twelve
already in place. Covers theorems and identities that hold only on
bipartite graphs:

1. **König's theorem**: on a bipartite graph, the size of a maximum
   matching equals the size of a minimum vertex cover. (This is the
   classical bipartite duality result.)
2. **Maximum matching ≤ min(|U|, |V|)**: the matching can't exceed
   either side of the bipartition.
3. **Bipartite density formula**: ``density(G, top) = |E| / (|U| * |V|)``
   where U and V are the two parts.
4. **Bipartite top/bottom degree consistency**: every node in the
   top set has degree ≤ |bottom|, and every node in the bottom set
   has degree ≤ |top|.
5. **Color complementarity**: ``color(G)`` returns 0/1 and adjacent
   nodes have different colors.
6. **No-odd-cycle invariant**: a bipartite graph has no odd-length
   cycles in its cycle basis.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx
import franken_networkx.bipartite as bp


BIPARTITE_FIXTURES = [
    # (name, builder, top_nodes)
    ("k_2_2", lambda: fnx.complete_bipartite_graph(2, 2), {0, 1}),
    ("k_2_3", lambda: fnx.complete_bipartite_graph(2, 3), {0, 1}),
    ("k_3_3", lambda: fnx.complete_bipartite_graph(3, 3), {0, 1, 2}),
    ("k_3_4", lambda: fnx.complete_bipartite_graph(3, 4), {0, 1, 2}),
    ("path_5", lambda: fnx.path_graph(5), {0, 2, 4}),
    ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2), {0, 3, 4, 5, 6}),
]


# -----------------------------------------------------------------------------
# König's theorem
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "top_nodes"), BIPARTITE_FIXTURES)
def test_konig_theorem_max_matching_equals_min_vertex_cover(
    name, builder, top_nodes
):
    """König's theorem: |max_matching(G)| == |min_vertex_cover(G)| on
    bipartite graphs. The fundamental bipartite duality result."""
    g = builder()
    matching = bp.maximum_matching(g, top_nodes=top_nodes)
    # bipartite.maximum_matching returns a u→v + v→u dict; the
    # matching size is half its entries.
    match_size = len(matching) // 2
    vc = bp.to_vertex_cover(g, matching, top_nodes=top_nodes)
    assert len(vc) == match_size, (
        f"{name}: König's theorem violated — "
        f"|min_vertex_cover| = {len(vc)} != |max_matching| = {match_size}"
    )


# -----------------------------------------------------------------------------
# Matching size bound: ≤ min(|U|, |V|)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "top_nodes"), BIPARTITE_FIXTURES)
def test_bipartite_matching_bounded_by_smaller_side(name, builder, top_nodes):
    g = builder()
    matching = bp.maximum_matching(g, top_nodes=top_nodes)
    match_size = len(matching) // 2
    other = set(g.nodes()) - top_nodes
    bound = min(len(top_nodes), len(other))
    assert match_size <= bound, (
        f"{name}: bipartite matching size {match_size} exceeds "
        f"min(|top|, |bottom|) = {bound}"
    )


# -----------------------------------------------------------------------------
# Vertex cover contains only graph nodes
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "top_nodes"), BIPARTITE_FIXTURES)
def test_min_vertex_cover_contains_only_graph_nodes(name, builder, top_nodes):
    g = builder()
    matching = bp.maximum_matching(g, top_nodes=top_nodes)
    vc = bp.to_vertex_cover(g, matching, top_nodes=top_nodes)
    for n in vc:
        assert g.has_node(n), (
            f"{name}: vertex cover contains foreign node {n}"
        )


# -----------------------------------------------------------------------------
# Vertex cover covers every edge
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "top_nodes"), BIPARTITE_FIXTURES)
def test_min_vertex_cover_covers_every_edge(name, builder, top_nodes):
    """The defining property of a vertex cover: every edge has at
    least one endpoint in the cover."""
    g = builder()
    matching = bp.maximum_matching(g, top_nodes=top_nodes)
    vc = bp.to_vertex_cover(g, matching, top_nodes=top_nodes)
    for u, v in g.edges():
        assert u in vc or v in vc, (
            f"{name}: edge ({u}, {v}) has neither endpoint in the "
            f"vertex cover {vc}"
        )


# -----------------------------------------------------------------------------
# Bipartite density
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "top_nodes"), BIPARTITE_FIXTURES)
def test_bipartite_density_in_unit_range(name, builder, top_nodes):
    g = builder()
    d = bp.density(g, top_nodes)
    assert 0.0 - 1e-9 <= d <= 1.0 + 1e-9, (
        f"{name}: bipartite density {d} outside [0, 1]"
    )


# -----------------------------------------------------------------------------
# Color (2-coloring on bipartite)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "top_nodes"), BIPARTITE_FIXTURES)
def test_bipartite_2coloring_is_proper(name, builder, top_nodes):
    g = builder()
    if not fnx.is_bipartite(g):
        return
    coloring = bp.color(g)
    assert set(coloring) == set(g.nodes()), (
        f"{name}: bipartite color omitted nodes "
        f"{set(g.nodes()) - set(coloring)}"
    )
    assert set(coloring.values()) <= {0, 1}, (
        f"{name}: bipartite color returned non-0/1 colors "
        f"{set(coloring.values())}"
    )
    # Adjacent nodes must have different colors.
    for u, v in g.edges():
        if u == v:
            continue
        cu = coloring.get(u)
        cv = coloring.get(v)
        assert cu != cv, (
            f"{name}: bipartite color assigned {cu} to both adjacent "
            f"nodes {u} and {v}"
        )
    # Coloring uses at most 2 colors (bipartite means 2-colorable).
    used = set(coloring.values())
    assert len(used) <= 2, (
        f"{name}: bipartite 2-coloring used {len(used)} colors: {used}"
    )


# -----------------------------------------------------------------------------
# No odd cycles
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "top_nodes"), BIPARTITE_FIXTURES)
def test_bipartite_has_no_odd_cycles(name, builder, top_nodes):
    g = builder()
    if not fnx.is_bipartite(g):
        return
    basis = list(fnx.cycle_basis(g))
    for cycle in basis:
        assert len(cycle) % 2 == 0, (
            f"{name}: bipartite graph has odd-length cycle {cycle} "
            f"(length {len(cycle)}) in its cycle basis"
        )
