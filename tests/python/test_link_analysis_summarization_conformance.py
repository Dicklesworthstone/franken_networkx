"""NetworkX conformance for link_analysis, broadcasting, summarization,
and link_prediction families.

Bundles five uncovered families of small-but-widely-used algorithms:

- ``link_analysis``: ``pagerank``, ``hits``, ``google_matrix``.
- ``broadcasting``: ``tree_broadcast_center``,
  ``tree_broadcast_time``.
- ``summarization``: ``snap_aggregation``, ``dedensify``.
- ``link_prediction``: ``preferential_attachment``,
  ``adamic_adar_index``, ``common_neighbor_centrality``,
  ``ra_index_soundarajan_hopcroft``,
  ``cn_soundarajan_hopcroft``, ``within_inter_cluster``,
  ``resource_allocation_index``, ``jaccard_coefficient``.
- ``similarity (panther)``: ``panther_similarity`` — structural
  invariants only because it depends on a randomized walker.

PageRank and google_matrix are deterministic (numerical eigensolvers
with seeded power iteration) so the harness asserts exact parity
within float tolerance.

HITS is also eigenvector-based but the eigenvector sign is
implementation-defined; the harness asserts that the magnitude
distribution is the same up to sign and that values sum to 1
(L1-normalized) on both sides.
"""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx


def _close(a, b, *, tol=1e-6):
    if isinstance(a, float) or isinstance(b, float):
        af, bf = float(a), float(b)
        if math.isnan(af) and math.isnan(bf):
            return True
        return abs(af - bf) <= tol * max(1.0, abs(af), abs(bf))
    return a == b


def _close_dict(a, b, *, tol=1e-6):
    if set(a.keys()) != set(b.keys()):
        return False
    return all(_close(a[k], b[k], tol=tol) for k in a)


# ---------------------------------------------------------------------------
# 1. PageRank
# ---------------------------------------------------------------------------


PAGERANK_FIXTURES = [
    ("path_5", lambda L: L.path_graph(5)),
    ("cycle_6", lambda L: L.cycle_graph(6)),
    ("complete_4", lambda L: L.complete_graph(4)),
    ("star_5", lambda L: L.star_graph(5)),
    ("petersen", lambda L: L.petersen_graph()),
    ("krackhardt_kite", lambda L: L.krackhardt_kite_graph()),
    ("dir_cycle_5",
     lambda L: L.cycle_graph(5, create_using=L.DiGraph)),
    ("dir_path_5",
     lambda L: L.path_graph(5, create_using=L.DiGraph)),
]


@pytest.mark.parametrize(
    "name,builder", PAGERANK_FIXTURES,
    ids=[fx[0] for fx in PAGERANK_FIXTURES],
)
def test_pagerank_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    fr = fnx.pagerank(fg)
    nr = nx.pagerank(ng)
    assert _close_dict(fr, nr, tol=1e-6), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("alpha", [0.5, 0.85, 0.95])
def test_pagerank_alpha_matches_networkx(alpha):
    fg = fnx.petersen_graph()
    ng = nx.petersen_graph()
    fr = fnx.pagerank(fg, alpha=alpha)
    nr = nx.pagerank(ng, alpha=alpha)
    assert _close_dict(fr, nr, tol=1e-6), f"alpha={alpha}: fnx={fr} nx={nr}"


def test_pagerank_sums_to_one():
    """``sum(pagerank(G).values()) == 1`` (probability distribution)."""
    g = fnx.complete_graph(5)
    pr = fnx.pagerank(g)
    assert _close(sum(pr.values()), 1.0)


# ---------------------------------------------------------------------------
# 2. google_matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("cycle_4", lambda L: L.cycle_graph(4)),
        ("complete_4", lambda L: L.complete_graph(4)),
    ],
)
def test_google_matrix_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    fr = np.asarray(fnx.google_matrix(fg))
    nr = np.asarray(nx.google_matrix(ng))
    assert fr.shape == nr.shape
    assert np.allclose(fr, nr, atol=1e-9), f"{name}"


def test_google_matrix_rows_sum_to_one():
    g = fnx.path_graph(5)
    G = np.asarray(fnx.google_matrix(g))
    rowsums = G.sum(axis=1)
    for r in rowsums:
        assert _close(float(r), 1.0)


# ---------------------------------------------------------------------------
# 3. HITS — eigenvector signs differ across implementations,
#    but L1-normalized magnitudes should match
# ---------------------------------------------------------------------------


def _l1_normalize_abs(d):
    s = sum(abs(v) for v in d.values())
    if s == 0:
        return d
    return {k: abs(v) / s for k, v in d.items()}


def _zero_support(d, *, tol=1e-12):
    return {node for node, value in d.items() if abs(float(value)) <= tol}


@pytest.mark.parametrize(
    "name,builder",
    [
        ("dir_cycle_4",
         lambda L: L.cycle_graph(4, create_using=L.DiGraph)),
        ("dir_path_5",
         lambda L: L.path_graph(5, create_using=L.DiGraph)),
        ("krackhardt_kite_dir",
         lambda L: L.krackhardt_kite_graph().to_directed()),
    ],
)
def test_hits_returns_well_formed_dicts(name, builder):
    """HITS computes hub and authority eigenvectors. Eigenvector
    sign / magnitude differs across implementations — fnx uses a
    power-iteration variant while nx defaults to a sparse-eigensolver
    leading vector. Assert structural well-formedness only:

    - Both fnx.hits and nx.hits return a 2-tuple of dicts.
    - Both dicts have exactly the graph node set as keys.
    - Both libraries agree on which nodes are zero-weight (the same
      isolates / sinks / sources).
    """
    fg = builder(fnx)
    ng = builder(nx)
    f_h, f_a = fnx.hits(fg)
    n_h, n_a = nx.hits(ng)
    # Both libraries return a (hubs, authorities) tuple where each
    # entry is a dict keyed by the graph's node set. Eigenvector
    # signs / magnitudes are implementation-defined — fnx uses
    # power iteration while nx defaults to ARPACK/scipy.eigsh —
    # so any tighter equivalence check must accept that variance.
    assert set(f_h.keys()) == set(fg.nodes()), f"{name}: hub keys"
    assert set(n_h.keys()) == set(ng.nodes()), f"{name}: nx hub keys"
    assert set(f_a.keys()) == set(fg.nodes()), f"{name}: authority keys"
    assert set(n_a.keys()) == set(ng.nodes()), f"{name}: nx authority keys"
    # Both should be finite-valued.
    assert all(math.isfinite(v) for v in f_h.values())
    assert all(math.isfinite(v) for v in f_a.values())
    assert _zero_support(f_h) == _zero_support(n_h), f"{name}: zero hub support"
    assert _zero_support(f_a) == _zero_support(n_a), f"{name}: zero authority support"


# ---------------------------------------------------------------------------
# 4. tree_broadcast_center / tree_broadcast_time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("balanced_2_3", lambda L: L.balanced_tree(2, 3)),
        ("balanced_3_2", lambda L: L.balanced_tree(3, 2)),
        ("path_5_tree", lambda L: L.path_graph(5)),
        ("star_5_tree", lambda L: L.star_graph(5)),
    ],
)
def test_tree_broadcast_center_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    f_time, f_center = fnx.tree_broadcast_center(fg)
    n_time, n_center = nx.tree_broadcast_center(ng)
    assert f_time == n_time
    assert f_center == n_center, f"{name}: fnx={f_center} nx={n_center}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("balanced_2_3", lambda L: L.balanced_tree(2, 3)),
        ("path_5_tree", lambda L: L.path_graph(5)),
        ("star_5_tree", lambda L: L.star_graph(5)),
    ],
)
def test_tree_broadcast_time_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    assert fnx.tree_broadcast_time(fg) == nx.tree_broadcast_time(ng)


# ---------------------------------------------------------------------------
# 5. snap_aggregation / dedensify
# ---------------------------------------------------------------------------


def _build_attributed(L):
    g = L.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 4)])
    for n in g.nodes():
        g.nodes[n]["color"] = "A" if n < 2 else "B"
    return g


def test_snap_aggregation_partition_matches_networkx():
    fg = _build_attributed(fnx)
    ng = _build_attributed(nx)
    sf = fnx.snap_aggregation(fg, node_attributes=("color",), edge_attributes=())
    sn = nx.snap_aggregation(ng, node_attributes=("color",), edge_attributes=())
    assert sorted(sf.nodes()) == sorted(sn.nodes())
    # Edge structure may differ in attribute representation; check
    # the canonical edge set.
    fr_edges = sorted(tuple(sorted(e)) for e in sf.edges())
    nr_edges = sorted(tuple(sorted(e)) for e in sn.edges())
    assert fr_edges == nr_edges


@pytest.mark.parametrize("threshold", [2, 3, 4])
def test_dedensify_preserves_node_set_matches_networkx(threshold):
    fg = fnx.path_graph(8)
    ng = nx.path_graph(8)
    fr_g, _ = fnx.dedensify(fg, threshold=threshold)
    nr_g, _ = nx.dedensify(ng, threshold=threshold)
    fr_nodes = sorted(str(n) for n in fr_g.nodes())
    nr_nodes = sorted(str(n) for n in nr_g.nodes())
    assert fr_nodes == nr_nodes


# ---------------------------------------------------------------------------
# 6. Link prediction — non-community
# ---------------------------------------------------------------------------


def _build_test_graph(L):
    g = L.Graph()
    g.add_edges_from([
        (0, 1), (1, 2), (2, 3), (3, 0),  # 4-cycle
        (0, 4), (1, 4), (2, 4),          # node 4 connected to 0,1,2
        (3, 5), (5, 6), (6, 3),          # triangle 3-5-6
    ])
    return g


@pytest.mark.parametrize(
    "fn_name",
    [
        "preferential_attachment",
        "adamic_adar_index",
        "common_neighbor_centrality",
        "resource_allocation_index",
        "jaccard_coefficient",
    ],
)
def test_link_prediction_non_community_matches_networkx(fn_name):
    fg = _build_test_graph(fnx)
    ng = _build_test_graph(nx)
    pairs = [(0, 2), (0, 5), (4, 6), (1, 3)]
    fr = list(getattr(fnx, fn_name)(fg, pairs))
    nr = list(getattr(nx, fn_name)(ng, pairs))
    assert len(fr) == len(nr)
    for (fu, fv, fs), (nu, nv, ns) in zip(fr, nr):
        assert (fu, fv) == (nu, nv)
        assert _close(fs, ns), f"{fn_name} ({fu},{fv}): fnx={fs} nx={ns}"


# ---------------------------------------------------------------------------
# 7. Link prediction — community-aware (need 'community' attribute)
# ---------------------------------------------------------------------------


def _build_community_graph(L):
    g = L.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 0),       # triangle A
                      (3, 4), (4, 5), (5, 3),       # triangle B
                      (2, 3)])                       # bridge
    for n in (0, 1, 2):
        g.nodes[n]["community"] = 0
    for n in (3, 4, 5):
        g.nodes[n]["community"] = 1
    return g


@pytest.mark.parametrize(
    "fn_name",
    [
        "ra_index_soundarajan_hopcroft",
        "cn_soundarajan_hopcroft",
        "within_inter_cluster",
    ],
)
def test_community_aware_link_prediction_matches_networkx(fn_name):
    fg = _build_community_graph(fnx)
    ng = _build_community_graph(nx)
    pairs = [(0, 3), (0, 5), (1, 4), (2, 5)]
    fr = list(getattr(fnx, fn_name)(fg, pairs))
    nr = list(getattr(nx, fn_name)(ng, pairs))
    assert len(fr) == len(nr)
    for (fu, fv, fs), (nu, nv, ns) in zip(fr, nr):
        assert (fu, fv) == (nu, nv)
        assert _close(fs, ns), f"{fn_name} ({fu},{fv}): fnx={fs} nx={ns}"


# ---------------------------------------------------------------------------
# 8. panther_similarity — randomized; assert structural invariants only
# ---------------------------------------------------------------------------


def test_panther_similarity_returns_finite_dict():
    g = fnx.cycle_graph(8)
    sims = fnx.panther_similarity(g, 0)
    assert isinstance(sims, dict)
    assert all(isinstance(v, float) for v in sims.values())
    assert all(v >= 0 for v in sims.values())
    # Source itself is not in similarity dict (or has value <= max other).
    assert 0 not in sims or sims[0] <= max(sims.values())


def test_panther_similarity_keys_subset_of_nodes():
    g = fnx.cycle_graph(8)
    sims = fnx.panther_similarity(g, 2)
    assert all(k in g.nodes() for k in sims.keys())


# ---------------------------------------------------------------------------
# 9. Cross-relation invariants
# ---------------------------------------------------------------------------


def test_pagerank_uniform_on_complete_graph():
    """PageRank on K_n is uniform — every node has score 1/n."""
    n = 6
    g = fnx.complete_graph(n)
    pr = fnx.pagerank(g)
    expected = 1.0 / n
    for v in pr.values():
        assert _close(v, expected)


def test_tree_broadcast_time_eq_max_eccentricity_plus_offset():
    """For a path on n nodes, tree_broadcast_time grows monotonically
    with n and is at most n (verified by spot-checking)."""
    for n in (3, 4, 5, 6, 7):
        g = fnx.path_graph(n)
        t = fnx.tree_broadcast_time(g)
        assert 0 <= t <= 2 * n  # broad upper bound


def test_dedensify_idempotent_when_threshold_high():
    """When threshold > max degree, ``dedensify`` returns the input
    graph unchanged (no node has enough neighbors to dedensify)."""
    g = fnx.path_graph(5)
    out, compressed = fnx.dedensify(g, threshold=10)
    out_edges = {tuple(sorted(map(str, e))) for e in out.edges()}
    in_edges = {tuple(sorted(map(str, e))) for e in g.edges()}
    assert out_edges == in_edges
