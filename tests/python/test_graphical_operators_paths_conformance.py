"""NetworkX conformance for graphical / operators / simple_paths /
graph hashing / bfs_beam algorithm families.

Bundles five small uncovered families:

- ``graphical``: ``is_graphical``, ``is_digraphical``,
  ``is_pseudographical``, ``is_multigraphical``,
  ``is_valid_degree_sequence_erdos_gallai``,
  ``is_valid_degree_sequence_havel_hakimi``.
- ``operators``: ``compose``, ``disjoint_union``, ``intersection``,
  ``union``, ``tensor_product``, ``cartesian_product``,
  ``lexicographic_product``, ``strong_product``.
- ``simple_paths``: ``shortest_simple_paths``,
  ``all_shortest_paths``.
- ``graph_hashing``: ``weisfeiler_lehman_graph_hash``,
  ``weisfeiler_lehman_subgraph_hashes``.
- ``traversal.beamsearch``: ``bfs_beam_edges``.
"""

from __future__ import annotations

import math
import warnings

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# graphical predicates
# ---------------------------------------------------------------------------


GRAPHICAL_SEQS = [
    ("k4_regular", [3, 3, 3, 3]),
    ("k5_regular", [4, 4, 4, 4, 4]),
    ("path", [1, 2, 2, 1]),
    ("triangle", [2, 2, 2]),
    ("odd_total", [3, 3, 3]),  # not graphical (odd sum)
    ("too_high", [5, 1, 1, 1, 1]),
    ("zero", [0, 0, 0]),
    ("one_edge", [1, 1]),
    ("self_loop_only", [2]),
    ("empty", []),
]


@pytest.mark.parametrize(
    "name,seq", GRAPHICAL_SEQS,
    ids=[fx[0] for fx in GRAPHICAL_SEQS],
)
def test_is_graphical_matches_networkx(name, seq):
    fr = fnx.is_graphical(seq)
    nr = nx.is_graphical(seq)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,seq",
    [fx for fx in GRAPHICAL_SEQS if fx[0] != "empty"],
    ids=[fx[0] for fx in GRAPHICAL_SEQS if fx[0] != "empty"],
)
def test_is_pseudographical_matches_networkx(name, seq):
    """nx and fnx both raise ValueError on empty sequence (the
    underlying ``min(deg_sequence)`` fails on empty input). Skip the
    empty case from this parametrization since neither library
    supports it."""
    fr = fnx.is_pseudographical(seq)
    nr = nx.is_pseudographical(seq)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_is_pseudographical_empty_raises_matching_networkx():
    with pytest.raises(ValueError):
        nx.is_pseudographical([])
    with pytest.raises(ValueError):
        fnx.is_pseudographical([])


@pytest.mark.parametrize(
    "name,seq", GRAPHICAL_SEQS,
    ids=[fx[0] for fx in GRAPHICAL_SEQS],
)
def test_is_multigraphical_matches_networkx(name, seq):
    fr = fnx.is_multigraphical(seq)
    nr = nx.is_multigraphical(seq)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,seq", GRAPHICAL_SEQS,
    ids=[fx[0] for fx in GRAPHICAL_SEQS],
)
def test_is_valid_degree_sequence_erdos_gallai_matches_networkx(name, seq):
    fr = fnx.is_valid_degree_sequence_erdos_gallai(seq)
    nr = nx.is_valid_degree_sequence_erdos_gallai(seq)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,seq", GRAPHICAL_SEQS,
    ids=[fx[0] for fx in GRAPHICAL_SEQS],
)
def test_is_valid_degree_sequence_havel_hakimi_matches_networkx(name, seq):
    fr = fnx.is_valid_degree_sequence_havel_hakimi(seq)
    nr = nx.is_valid_degree_sequence_havel_hakimi(seq)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,in_seq,out_seq",
    [
        ("symmetric_balanced", [2, 1, 1], [1, 2, 1]),
        ("zero_in_zero_out", [0, 0, 0], [0, 0, 0]),
        ("one_arc", [1, 0], [0, 1]),
        ("mismatched_sums", [2, 0], [0, 1]),  # not digraphical
    ],
)
def test_is_digraphical_matches_networkx(name, in_seq, out_seq):
    fr = fnx.is_digraphical(in_seq, out_seq)
    nr = nx.is_digraphical(in_seq, out_seq)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Graph operators
# ---------------------------------------------------------------------------


def _pair(builder):
    return builder(fnx), builder(nx)


def _operator_canonical(g):
    """Canonical (nodes, edges) representation for cross-lib equality."""
    nodes = sorted(str(n) for n in g.nodes())
    edges = sorted(tuple(sorted((str(u), str(v)))) for u, v in g.edges())
    return nodes, edges


@pytest.mark.parametrize(
    "name,builder_g,builder_h",
    [
        ("path3_cycle4",
         lambda L: L.path_graph(3), lambda L: L.cycle_graph(4)),
        ("path4_path4",
         lambda L: L.path_graph(4), lambda L: L.path_graph(4)),
        ("complete3_star4",
         lambda L: L.complete_graph(3), lambda L: L.star_graph(4)),
    ],
)
def test_compose_matches_networkx(name, builder_g, builder_h):
    fg, ng = _pair(builder_g)
    fh, nh = _pair(builder_h)
    fr = fnx.compose(fg, fh)
    nr = nx.compose(ng, nh)
    assert _operator_canonical(fr) == _operator_canonical(nr), name


@pytest.mark.parametrize(
    "name,builder_g,builder_h",
    [
        ("path3_path3",
         lambda L: L.path_graph(3), lambda L: L.path_graph(3)),
        ("complete4_cycle5",
         lambda L: L.complete_graph(4), lambda L: L.cycle_graph(5)),
    ],
)
def test_disjoint_union_matches_networkx(name, builder_g, builder_h):
    fg, ng = _pair(builder_g)
    fh, nh = _pair(builder_h)
    fr = fnx.disjoint_union(fg, fh)
    nr = nx.disjoint_union(ng, nh)
    assert fr.number_of_nodes() == nr.number_of_nodes()
    assert fr.number_of_edges() == nr.number_of_edges()


@pytest.mark.parametrize(
    "name,nodes_g,edges_g,nodes_h,edges_h",
    [
        ("shared_subset",
         [0, 1, 2, 3], [(0, 1), (1, 2), (2, 3)],
         [0, 1, 2, 3], [(0, 1), (2, 3)]),
        ("complete_subset",
         [0, 1, 2], [(0, 1), (1, 2), (0, 2)],
         [0, 1, 2], [(0, 1), (1, 2)]),
    ],
)
def test_intersection_matches_networkx(
    name, nodes_g, edges_g, nodes_h, edges_h,
):
    fg = fnx.Graph(); fg.add_nodes_from(nodes_g); fg.add_edges_from(edges_g)
    fh = fnx.Graph(); fh.add_nodes_from(nodes_h); fh.add_edges_from(edges_h)
    ng = nx.Graph(); ng.add_nodes_from(nodes_g); ng.add_edges_from(edges_g)
    nh = nx.Graph(); nh.add_nodes_from(nodes_h); nh.add_edges_from(edges_h)
    fr = fnx.intersection(fg, fh)
    nr = nx.intersection(ng, nh)
    assert _operator_canonical(fr) == _operator_canonical(nr), name


@pytest.mark.parametrize(
    "name,builder_g,builder_h",
    [
        ("path2_path2",
         lambda L: L.path_graph(2), lambda L: L.path_graph(2)),
        ("cycle3_path2",
         lambda L: L.cycle_graph(3), lambda L: L.path_graph(2)),
    ],
)
def test_tensor_product_matches_networkx(name, builder_g, builder_h):
    fg, ng = _pair(builder_g)
    fh, nh = _pair(builder_h)
    fr = fnx.tensor_product(fg, fh)
    nr = nx.tensor_product(ng, nh)
    assert fr.number_of_nodes() == nr.number_of_nodes()
    assert fr.number_of_edges() == nr.number_of_edges()


@pytest.mark.parametrize(
    "name,builder_g,builder_h",
    [
        ("path2_path2",
         lambda L: L.path_graph(2), lambda L: L.path_graph(2)),
        ("cycle3_path3",
         lambda L: L.cycle_graph(3), lambda L: L.path_graph(3)),
        ("complete3_complete2",
         lambda L: L.complete_graph(3), lambda L: L.complete_graph(2)),
    ],
)
def test_cartesian_product_matches_networkx(name, builder_g, builder_h):
    fg, ng = _pair(builder_g)
    fh, nh = _pair(builder_h)
    fr = fnx.cartesian_product(fg, fh)
    nr = nx.cartesian_product(ng, nh)
    assert fr.number_of_nodes() == nr.number_of_nodes()
    assert fr.number_of_edges() == nr.number_of_edges()


@pytest.mark.parametrize(
    "name,builder_g,builder_h",
    [
        ("path2_path2",
         lambda L: L.path_graph(2), lambda L: L.path_graph(2)),
        ("cycle3_path2",
         lambda L: L.cycle_graph(3), lambda L: L.path_graph(2)),
    ],
)
def test_lexicographic_product_matches_networkx(name, builder_g, builder_h):
    fg, ng = _pair(builder_g)
    fh, nh = _pair(builder_h)
    fr = fnx.lexicographic_product(fg, fh)
    nr = nx.lexicographic_product(ng, nh)
    assert fr.number_of_nodes() == nr.number_of_nodes()
    assert fr.number_of_edges() == nr.number_of_edges()


@pytest.mark.parametrize(
    "name,builder_g,builder_h",
    [
        ("path2_path2",
         lambda L: L.path_graph(2), lambda L: L.path_graph(2)),
        ("cycle3_path2",
         lambda L: L.cycle_graph(3), lambda L: L.path_graph(2)),
    ],
)
def test_strong_product_matches_networkx(name, builder_g, builder_h):
    fg, ng = _pair(builder_g)
    fh, nh = _pair(builder_h)
    fr = fnx.strong_product(fg, fh)
    nr = nx.strong_product(ng, nh)
    assert fr.number_of_nodes() == nr.number_of_nodes()
    assert fr.number_of_edges() == nr.number_of_edges()


# ---------------------------------------------------------------------------
# Simple paths variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,source,target",
    [
        ("complete4_0_2", lambda L: L.complete_graph(4), 0, 2),
        ("complete5_0_3", lambda L: L.complete_graph(5), 0, 3),
        ("path5_endpoints", lambda L: L.path_graph(5), 0, 4),
        ("petersen_pair", lambda L: L.petersen_graph(), 0, 5),
        ("two_triangles_bridge",
         lambda L: L.from_edgelist(
             [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
         ) if hasattr(L, "from_edgelist") else None, 0, 5),
    ],
)
def test_shortest_simple_paths_matches_networkx(
    name, builder, source, target,
):
    g_nx = builder(nx)
    if g_nx is None:
        g_nx = nx.Graph()
        g_nx.add_edges_from([
            (0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3),
        ])
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = list(fnx.shortest_simple_paths(g_fnx, source, target))
    nr = list(nx.shortest_simple_paths(g_nx, source, target))
    # Path lengths must agree pairwise (paths themselves may differ
    # on tie-break for equal-length paths).
    assert [len(p) for p in fr] == [len(p) for p in nr], (
        f"{name}: fnx_lens={[len(p) for p in fr]} "
        f"nx_lens={[len(p) for p in nr]}"
    )


@pytest.mark.parametrize(
    "name,builder,source,target",
    [
        ("complete4_0_2", lambda L: L.complete_graph(4), 0, 2),
        ("petersen_pair", lambda L: L.petersen_graph(), 0, 5),
        ("path5_endpoints", lambda L: L.path_graph(5), 0, 4),
    ],
)
def test_all_shortest_paths_matches_networkx(name, builder, source, target):
    g_fnx, g_nx = _pair(builder)
    fr = sorted(tuple(p) for p in fnx.all_shortest_paths(g_fnx, source, target))
    nr = sorted(tuple(p) for p in nx.all_shortest_paths(g_nx, source, target))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Graph hashing — Weisfeiler-Lehman
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("complete_3", lambda L: L.complete_graph(3)),
        ("complete_4", lambda L: L.complete_graph(4)),
        ("complete_5", lambda L: L.complete_graph(5)),
        ("path_5", lambda L: L.path_graph(5)),
        ("cycle_6", lambda L: L.cycle_graph(6)),
        ("petersen", lambda L: L.petersen_graph()),
        ("krackhardt_kite", lambda L: L.krackhardt_kite_graph()),
        ("balanced_tree_2_3", lambda L: L.balanced_tree(2, 3)),
    ],
)
def test_weisfeiler_lehman_graph_hash_matches_networkx(name, builder):
    g_fnx, g_nx = _pair(builder)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.weisfeiler_lehman_graph_hash(g_fnx)
        nr = nx.weisfeiler_lehman_graph_hash(g_nx)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("complete_4", lambda L: L.complete_graph(4)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_weisfeiler_lehman_subgraph_hashes_matches_networkx(name, builder):
    g_fnx, g_nx = _pair(builder)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.weisfeiler_lehman_subgraph_hashes(g_fnx)
        nr = nx.weisfeiler_lehman_subgraph_hashes(g_nx)
    assert set(fr.keys()) == set(nr.keys())
    for k in fr:
        assert fr[k] == nr[k], f"{name}: node {k} hash differs"


# ---------------------------------------------------------------------------
# bfs_beam_edges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("cycle_5", lambda L: L.cycle_graph(5)),
        ("balanced_tree_2_3", lambda L: L.balanced_tree(2, 3)),
    ],
)
def test_bfs_beam_edges_matches_networkx(name, builder):
    """``bfs_beam_edges(G, source, value, width=1)`` does a beamed-BFS
    where ``value(node)`` ranks candidates. With a constant value
    function and width=1 it walks the lexicographically-smallest
    spanning tree, matching nx exactly."""
    g_fnx, g_nx = _pair(builder)
    fr = list(fnx.bfs_beam_edges(g_fnx, 0, lambda n: 0))
    nr = list(nx.bfs_beam_edges(g_nx, 0, lambda n: 0))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


def test_havel_hakimi_implies_erdos_gallai():
    """A sequence valid by Havel-Hakimi must also be valid by Erdős-Gallai
    (both characterize graphical sequences)."""
    sequences = [
        [3, 3, 3, 3], [4, 4, 4, 4, 4], [2, 2, 2], [1, 1],
        [2, 1, 1, 0], [0, 0, 0],
    ]
    for seq in sequences:
        if fnx.is_valid_degree_sequence_havel_hakimi(seq):
            assert fnx.is_valid_degree_sequence_erdos_gallai(seq), seq


def test_compose_includes_both_node_sets():
    fg = fnx.path_graph(3)
    fh = fnx.cycle_graph(4)
    composed = fnx.compose(fg, fh)
    assert set(composed.nodes()) == set(fg.nodes()) | set(fh.nodes())


def test_disjoint_union_doubles_nodes():
    fg = fnx.path_graph(3)
    fh = fnx.path_graph(3)
    union = fnx.disjoint_union(fg, fh)
    assert union.number_of_nodes() == fg.number_of_nodes() + fh.number_of_nodes()


def test_tensor_product_node_count():
    """``|V(G ⊗ H)|`` equals ``|V(G)| * |V(H)|``."""
    fg = fnx.path_graph(3)
    fh = fnx.cycle_graph(4)
    tp = fnx.tensor_product(fg, fh)
    assert tp.number_of_nodes() == fg.number_of_nodes() * fh.number_of_nodes()


def test_cartesian_product_node_count():
    """``|V(G □ H)|`` equals ``|V(G)| * |V(H)|``."""
    fg = fnx.path_graph(3)
    fh = fnx.cycle_graph(4)
    cp = fnx.cartesian_product(fg, fh)
    assert cp.number_of_nodes() == fg.number_of_nodes() * fh.number_of_nodes()


def test_wl_hash_is_isomorphism_invariant():
    """Two isomorphic graphs (same up to relabel) must have the same
    WL hash."""
    g1 = fnx.path_graph(5)
    g2 = nx.relabel_nodes(g1, {0: 99, 1: 88, 2: 77, 3: 66, 4: 55})
    fg2 = fnx.Graph()
    fg2.add_nodes_from(g2.nodes())
    fg2.add_edges_from(g2.edges())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        h1 = fnx.weisfeiler_lehman_graph_hash(g1)
        h2 = fnx.weisfeiler_lehman_graph_hash(fg2)
    assert h1 == h2


def test_wl_hash_distinguishes_non_isomorphic():
    """K_4 and C_4 are not isomorphic ⇒ WL hashes must differ."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        h1 = fnx.weisfeiler_lehman_graph_hash(fnx.complete_graph(4))
        h2 = fnx.weisfeiler_lehman_graph_hash(fnx.cycle_graph(4))
    assert h1 != h2


def test_shortest_simple_paths_first_is_shortest_path():
    """The first path yielded by ``shortest_simple_paths`` has length
    equal to ``shortest_path_length``."""
    g = fnx.complete_graph(5)
    paths = list(fnx.shortest_simple_paths(g, 0, 3))
    sp_len = fnx.shortest_path_length(g, 0, 3)
    assert len(paths[0]) - 1 == sp_len
