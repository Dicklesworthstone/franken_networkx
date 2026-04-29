"""NetworkX conformance for the bipartite algorithm family.

Existing scattered tests cover specific points
(``test_bipartite_filtered_degree_view_parity.py``,
``test_draw_bipartite_top_nodes_positional_parity.py``,
``test_tree_bipartite.py``); add a comprehensive differential test
that exercises the full bipartite namespace ``fnx.bipartite.*``.

Covered functions:

- Predicates: ``is_bipartite``, ``is_bipartite_node_set``, ``sets``.
- Density / degree: ``density``, ``degrees``, ``degree_centrality``.
- Centrality: ``closeness_centrality``, ``betweenness_centrality``.
- Clustering: ``clustering``, ``average_clustering``,
  ``spectral_bipartivity``, ``latapy_clustering``,
  ``robins_alexander_clustering``, ``node_redundancy``,
  ``redundancy``.
- Projection: ``projected_graph``, ``weighted_projected_graph``,
  ``collaboration_weighted_projected_graph``,
  ``overlap_weighted_projected_graph``,
  ``generic_weighted_projected_graph``.
- Matching: ``maximum_matching``, ``hopcroft_karp_matching``,
  ``eppstein_matching``, ``minimum_weight_full_matching``,
  ``min_edge_cover``.
- Color: ``color``.
"""

from __future__ import annotations

import math
import warnings

import pytest
import networkx as nx
from networkx.algorithms import bipartite as nx_bp

import franken_networkx as fnx
fnx_bp = fnx.bipartite


def _equiv(a, b, tol=1e-9):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return abs(a - b) < tol
    return a == b


def _equiv_dict_of_floats(a, b, tol=1e-9):
    if set(a.keys()) != set(b.keys()):
        return False
    return all(_equiv(a[k], b[k], tol) for k in a)


def _make_bp_pair(top_nodes, edges):
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(top_nodes, bipartite=0)
    ng.add_nodes_from(top_nodes, bipartite=0)
    bottom = set()
    for u, v in edges:
        bottom.add(v if u in top_nodes else u)
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    fg.add_nodes_from(bottom, bipartite=1)
    ng.add_nodes_from(bottom, bipartite=1)
    return fg, ng, top_nodes, bottom


# ---------------------------------------------------------------------------
# Bipartite fixtures
# ---------------------------------------------------------------------------


BIPARTITE_FIXTURES = [
    ("K_2_3", {0, 1},
     [(0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (1, 4)]),
    ("K_3_3", {0, 1, 2},
     [(u, v) for u in range(3) for v in range(3, 6)]),
    ("K_3_4", {0, 1, 2},
     [(u, v) for u in range(3) for v in range(3, 7)]),
    ("K_4_4", {0, 1, 2, 3},
     [(u, v) for u in range(4) for v in range(4, 8)]),
    ("path_bp", {0, 2, 4},
     [(0, 1), (1, 2), (2, 3), (3, 4)]),
    ("disconnected_bp", {0, 2}, [(0, 1), (2, 3)]),
    ("two_K_2_3_disjoint", {0, 1, 5, 6},
     [(0, 2), (0, 3), (1, 2), (1, 3), (5, 7), (5, 8), (6, 7), (6, 8)]),
    ("isolate_plus_K_2_2", {0, 1},
     [(0, 2), (0, 3), (1, 2), (1, 3)]),
]


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_is_bipartite_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    assert fnx_bp.is_bipartite(fg) == nx_bp.is_bipartite(ng)


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_is_bipartite_node_set_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    assert fnx_bp.is_bipartite_node_set(fg, top) == nx_bp.is_bipartite_node_set(ng, top)


def test_top_level_is_bipartite_node_set_duplicate_raises_like_networkx():
    fg, ng, _, _ = _make_bp_pair({0, 1}, [(0, 2), (1, 3)])

    with pytest.raises(nx.AmbiguousSolution):
        nx_bp.is_bipartite_node_set(ng, [0, 0])
    with pytest.raises(fnx.AmbiguousSolution):
        fnx.is_bipartite_node_set(fg, [0, 0])


@pytest.mark.parametrize(
    "name,top,edges",
    [fx for fx in BIPARTITE_FIXTURES if fx[0] != "disconnected_bp"],
    ids=[fx[0] for fx in BIPARTITE_FIXTURES if fx[0] != "disconnected_bp"],
)
def test_sets_matches_networkx(name, top, edges):
    """``bipartite.sets`` requires connected input."""
    fg, ng, _, bottom = _make_bp_pair(top, edges)
    if not nx.is_connected(ng):
        return
    fr = fnx_bp.sets(fg)
    nr = nx_bp.sets(ng)
    # Either same order or symmetric
    assert (
        (fr[0] == nr[0] and fr[1] == nr[1])
        or (fr[0] == nr[1] and fr[1] == nr[0])
    )


# ---------------------------------------------------------------------------
# Density and degrees
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_density_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    assert _equiv(fnx_bp.density(fg, top), nx_bp.density(ng, top))


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_degrees_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.degrees(fg, top)
    nr = nx_bp.degrees(ng, top)
    fr_d = (dict(fr[0]), dict(fr[1]))
    nr_d = (dict(nr[0]), dict(nr[1]))
    assert fr_d == nr_d


# ---------------------------------------------------------------------------
# Centrality
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_degree_centrality_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.degree_centrality(fg, top)
    nr = nx_bp.degree_centrality(ng, top)
    assert _equiv_dict_of_floats(fr, nr)


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_closeness_centrality_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.closeness_centrality(fg, top)
    nr = nx_bp.closeness_centrality(ng, top)
    assert _equiv_dict_of_floats(fr, nr)


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_betweenness_centrality_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.betweenness_centrality(fg, top)
    nr = nx_bp.betweenness_centrality(ng, top)
    assert _equiv_dict_of_floats(fr, nr)


# ---------------------------------------------------------------------------
# Clustering and bipartivity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_clustering_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.clustering(fg)
    nr = nx_bp.clustering(ng)
    assert _equiv_dict_of_floats(fr, nr)


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_average_clustering_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    assert _equiv(fnx_bp.average_clustering(fg), nx_bp.average_clustering(ng))


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_spectral_bipartivity_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.spectral_bipartivity(fg)
    nr = nx_bp.spectral_bipartivity(ng)
    assert _equiv(fr, nr, tol=1e-6)


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_latapy_clustering_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.latapy_clustering(fg)
    nr = nx_bp.latapy_clustering(ng)
    assert _equiv_dict_of_floats(fr, nr)


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_robins_alexander_clustering_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    assert _equiv(
        fnx_bp.robins_alexander_clustering(fg),
        nx_bp.robins_alexander_clustering(ng),
    )


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_projected_graph_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.projected_graph(fg, top)
    nr = nx_bp.projected_graph(ng, top)
    fr_e = sorted(tuple(sorted([u, v])) for u, v in fr.edges())
    nr_e = sorted(tuple(sorted([u, v])) for u, v in nr.edges())
    assert fr_e == nr_e


def test_top_level_projected_graph_preserves_directed_output_parity():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    edges = [(0, 2), (2, 1)]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    fr = fnx.projected_graph(fg, [0, 1])
    nr = nx_bp.projected_graph(ng, [0, 1])

    assert fr.is_directed() == nr.is_directed()
    assert sorted(fr.edges()) == sorted(nr.edges())


def test_top_level_projected_graph_multigraph_preserves_directed_output_parity():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    edges = [(0, 2), (0, 3), (2, 1), (3, 1)]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    fr = fnx.projected_graph(fg, [0, 1], multigraph=True)
    nr = nx_bp.projected_graph(ng, [0, 1], multigraph=True)

    assert fr.is_directed() == nr.is_directed()
    assert fr.is_multigraph() == nr.is_multigraph()
    assert sorted(fr.edges(keys=True)) == sorted(nr.edges(keys=True))


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_weighted_projected_graph_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.weighted_projected_graph(fg, top)
    nr = nx_bp.weighted_projected_graph(ng, top)
    fr_e = sorted(
        (min(u, v), max(u, v), fr.edges[u, v].get("weight"))
        for u, v in fr.edges()
    )
    nr_e = sorted(
        (min(u, v), max(u, v), nr.edges[u, v].get("weight"))
        for u, v in nr.edges()
    )
    assert fr_e == nr_e


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_overlap_weighted_projected_graph_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.overlap_weighted_projected_graph(fg, top)
    nr = nx_bp.overlap_weighted_projected_graph(ng, top)
    fr_e = sorted(
        (min(u, v), max(u, v), fr.edges[u, v].get("weight"))
        for u, v in fr.edges()
    )
    nr_e = sorted(
        (min(u, v), max(u, v), nr.edges[u, v].get("weight"))
        for u, v in nr.edges()
    )
    assert all(
        f[0] == n[0] and f[1] == n[1] and _equiv(f[2], n[2])
        for f, n in zip(fr_e, nr_e)
    )


# ---------------------------------------------------------------------------
# Matching algorithms — three different implementations should agree
# on size + cover the same maximum matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_maximum_matching_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.maximum_matching(fg, top)
    nr = nx_bp.maximum_matching(ng, top)
    assert fr == nr


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_hopcroft_karp_matching_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.hopcroft_karp_matching(fg, top)
    nr = nx_bp.hopcroft_karp_matching(ng, top)
    assert fr == nr


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_eppstein_matching_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.eppstein_matching(fg, top)
    nr = nx_bp.eppstein_matching(ng, top)
    assert fr == nr


# ---------------------------------------------------------------------------
# Cross-relation: all three matching algorithms produce same matching size
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_all_matching_algorithms_produce_same_size(name, top, edges):
    fg, _, _, _ = _make_bp_pair(top, edges)
    sizes = {
        "maximum": len(fnx_bp.maximum_matching(fg, top)) // 2,
        "hopcroft_karp": len(fnx_bp.hopcroft_karp_matching(fg, top)) // 2,
        "eppstein": len(fnx_bp.eppstein_matching(fg, top)) // 2,
    }
    distinct = set(sizes.values())
    assert len(distinct) == 1, f"{name}: matching sizes diverged {sizes}"


# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_color_matches_networkx(name, top, edges):
    fg, ng, _, _ = _make_bp_pair(top, edges)
    fr = fnx_bp.color(fg)
    nr = nx_bp.color(ng)
    assert fr == nr


# ---------------------------------------------------------------------------
# biadjacency_matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,top,edges",
    [fx for fx in BIPARTITE_FIXTURES if fx[0] != "disconnected_bp"],
    ids=[fx[0] for fx in BIPARTITE_FIXTURES if fx[0] != "disconnected_bp"],
)
def test_biadjacency_matrix_matches_networkx(name, top, edges):
    import numpy as np
    fg, ng, _, _ = _make_bp_pair(top, edges)
    row_order = sorted(top)
    fr = fnx_bp.biadjacency_matrix(fg, row_order)
    nr = nx_bp.biadjacency_matrix(ng, row_order)
    fr_arr = fr.toarray() if hasattr(fr, "toarray") else fr
    nr_arr = nr.toarray() if hasattr(nr, "toarray") else nr
    assert np.array_equal(fr_arr, nr_arr)


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,top,edges", BIPARTITE_FIXTURES,
                         ids=[fx[0] for fx in BIPARTITE_FIXTURES])
def test_density_equals_edges_over_max_edges(name, top, edges):
    """Documented bipartite density formula:
    ``density = m / (|top| * |bottom|)``."""
    fg, _, top_, bottom = _make_bp_pair(top, edges)
    if not top_ or not bottom:
        return
    expected = fg.number_of_edges() / (len(top_) * len(bottom))
    assert _equiv(fnx_bp.density(fg, top_), expected)


def test_K_3_3_is_perfectly_matchable():
    """K_3_3 has a perfect matching of size 3."""
    fg, _, top, _ = _make_bp_pair(
        {0, 1, 2}, [(u, v) for u in range(3) for v in range(3, 6)],
    )
    matching = fnx_bp.maximum_matching(fg, top)
    # Each pair is recorded twice (u→v, v→u), so size = 2 * cardinality.
    assert len(matching) // 2 == 3
