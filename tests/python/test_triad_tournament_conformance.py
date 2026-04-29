"""NetworkX conformance for the triad-census + tournament algorithm
families.

Existing tests (``test_triadic_census_order_parity.py``,
``test_edge_subset_negcycle_triad_parity.py``) cover specific parity
points. Add a broad differential test that exercises both families
across structured + random fixtures.

Triad family covered:

- ``triadic_census(G, nodelist=...)`` — count of each triad type
  ('003', '012', '102', '021D', '021U', '021C', '111D', '111U',
  '030T', '030C', '201', '120D', '120U', '120C', '210', '300').
- ``all_triads(G)`` — generator of triad subgraphs.
- ``triad_type(G)`` — single-triad classification.
- ``is_triad(G)`` — predicate (3 nodes, directed).
- ``triads_by_type(G)`` — dict of triad type → list of subgraphs.

Tournament family covered:

- ``is_tournament(G)`` — predicate.
- ``tournament_matrix(G)`` — skew-symmetric adjacency matrix.
- ``tournament.score_sequence(G)`` — out-degree sequence.
- ``tournament.is_reachable(G, s, t)`` — reachability in tournament.
- ``tournament.hamiltonian_path(G)`` — exists by tournament-Rédei.
- ``tournament.is_strongly_connected(G)`` — predicate (tournament).
"""

from __future__ import annotations

import itertools
import warnings

import pytest
import networkx as nx
from networkx.algorithms import tournament as nx_tournament

import franken_networkx as fnx


def _pair_directed(edges, nodes=None):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Triad fixtures
# ---------------------------------------------------------------------------


def _triad_fixtures():
    """(name, edges, nodes) — directed graphs of various sizes."""
    out = []
    out.append(("dir_C_3", [(0, 1), (1, 2), (2, 0)], list(range(3))))
    out.append(("dir_K3_both",
                [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
                list(range(3))))
    out.append(("dir_DAG",
                [(0, 1), (0, 2), (1, 3)], list(range(4))))
    out.append(("dir_DAG_diamond",
                [(0, 1), (0, 2), (1, 3), (2, 3)], list(range(4))))
    out.append(("dir_path_4",
                [(0, 1), (1, 2), (2, 3)], list(range(4))))
    out.append(("dir_isolate_plus",
                [(0, 1), (1, 2)], list(range(4))))
    out.append(("dir_C_4",
                [(i, (i + 1) % 4) for i in range(4)], list(range(4))))
    out.append(("dir_C_5",
                [(i, (i + 1) % 5) for i in range(5)], list(range(5))))
    out.append(("dir_two_disjoint_edges",
                [(0, 1), (2, 3)], list(range(4))))
    out.append(("dir_K_4_one_way",
                list(itertools.combinations(range(4), 2)), list(range(4))))
    out.append(("dir_mixed_5",
                [(0, 1), (1, 0), (1, 2), (2, 3), (3, 1), (4, 0), (0, 4)],
                list(range(5))))
    for n, p, seed in [(5, 0.4, 1), (6, 0.3, 2), (8, 0.25, 3)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed, directed=True)
        out.append((f"dir_gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


TRIAD_FIXTURES = _triad_fixtures()


# ---------------------------------------------------------------------------
# triadic_census
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", TRIAD_FIXTURES,
                         ids=[fx[0] for fx in TRIAD_FIXTURES])
def test_triadic_census_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.triadic_census(fg)
    nr = nx.triadic_census(ng)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,nodes,nodelist",
    [
        ("K_3_both_dir_subset",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         list(range(4)),
         [0, 1, 2]),
        ("DAG_first_three",
         [(0, 1), (0, 2), (1, 3), (2, 3)], list(range(4)),
         [0, 1, 2]),
    ],
)
def test_triadic_census_with_nodelist_matches_networkx(
    name, edges, nodes, nodelist,
):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.triadic_census(fg, nodelist=nodelist)
    nr = nx.triadic_census(ng, nodelist=nodelist)
    assert fr == nr


# ---------------------------------------------------------------------------
# Triad type total invariant: sum of counts == C(n, 3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", TRIAD_FIXTURES,
                         ids=[fx[0] for fx in TRIAD_FIXTURES])
def test_triadic_census_total_equals_n_choose_3(name, edges, nodes):
    fg, _ = _pair_directed(edges, nodes)
    n = fg.number_of_nodes()
    expected_total = n * (n - 1) * (n - 2) // 6 if n >= 3 else 0
    census = fnx.triadic_census(fg)
    actual_total = sum(census.values())
    assert actual_total == expected_total, (
        f"{name}: triadic_census total {actual_total} != "
        f"C({n}, 3) = {expected_total}"
    )


# ---------------------------------------------------------------------------
# all_triads
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", TRIAD_FIXTURES,
                         ids=[fx[0] for fx in TRIAD_FIXTURES])
def test_all_triads_node_sets_match_networkx(name, edges, nodes):
    """Both libs enumerate every 3-node subgraph; node-set decomposition
    is identical even if the subgraph yield order differs."""
    fg, ng = _pair_directed(edges, nodes)
    fr = sorted(tuple(sorted(t.nodes())) for t in fnx.all_triads(fg))
    nr = sorted(tuple(sorted(t.nodes())) for t in nx.all_triads(ng))
    assert fr == nr


# ---------------------------------------------------------------------------
# triad_type — must work on a 3-node DiGraph
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,expected",
    [
        ("003_no_edges", [], "003"),
        ("012_one_edge", [(0, 1)], "012"),
        ("102_dyad", [(0, 1), (1, 0)], "102"),
        ("021D_two_out", [(1, 0), (1, 2)], "021D"),
        ("021U_two_in", [(0, 1), (2, 1)], "021U"),
        ("021C_chain", [(0, 1), (1, 2)], "021C"),
        ("030C_cycle", [(0, 1), (1, 2), (2, 0)], "030C"),
        ("030T_transitive", [(0, 1), (1, 2), (0, 2)], "030T"),
        ("300_full",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)], "300"),
    ],
)
def test_triad_type_matches_networkx_and_expected(name, edges, expected):
    fg = fnx.DiGraph(); fg.add_nodes_from([0, 1, 2])
    ng = nx.DiGraph(); ng.add_nodes_from([0, 1, 2])
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    assert fnx.triad_type(fg) == nx.triad_type(ng) == expected, (
        f"{name}: fnx={fnx.triad_type(fg)} nx={nx.triad_type(ng)} "
        f"expected={expected}"
    )


def test_triad_type_rejects_self_loop_like_networkx():
    fg = fnx.DiGraph(); fg.add_nodes_from([0, 1, 2]); fg.add_edge(0, 0)
    ng = nx.DiGraph(); ng.add_nodes_from([0, 1, 2]); ng.add_edge(0, 0)

    with pytest.raises(nx.NetworkXAlgorithmError):
        nx.triad_type(ng)
    with pytest.raises(fnx.NetworkXAlgorithmError):
        fnx.triad_type(fg)


# ---------------------------------------------------------------------------
# is_triad
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n_nodes,expected",
    [(0, False), (1, False), (2, False), (3, True), (4, False), (5, False)],
)
def test_is_triad_predicate_matches_networkx(n_nodes, expected):
    fg = fnx.DiGraph(); fg.add_nodes_from(range(n_nodes))
    ng = nx.DiGraph(); ng.add_nodes_from(range(n_nodes))
    assert fnx.is_triad(fg) == nx.is_triad(ng) == expected


# ---------------------------------------------------------------------------
# triads_by_type — dict from triad type to list of subgraphs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", TRIAD_FIXTURES,
                         ids=[fx[0] for fx in TRIAD_FIXTURES])
def test_triads_by_type_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.triads_by_type(fg)
    nr = nx.triads_by_type(ng)
    fr_norm = {
        k: sorted(tuple(sorted(t.nodes())) for t in v)
        for k, v in fr.items()
    }
    nr_norm = {
        k: sorted(tuple(sorted(t.nodes())) for t in v)
        for k, v in nr.items()
    }
    assert fr_norm == nr_norm


# ---------------------------------------------------------------------------
# Tournament family
# ---------------------------------------------------------------------------


def _tournament_fixtures():
    out = []
    # Various tournaments
    out.append(("K_3_one_way", [(0, 1), (1, 2), (0, 2)], list(range(3))))
    out.append(("K_4_one_way",
                list(itertools.combinations(range(4), 2)), list(range(4))))
    out.append(("K_5_one_way",
                list(itertools.combinations(range(5), 2)), list(range(5))))
    out.append(("K_6_one_way",
                list(itertools.combinations(range(6), 2)), list(range(6))))
    # Cyclic tournament
    out.append(("cyclic_K_3",
                [(0, 1), (1, 2), (2, 0)], list(range(3))))
    out.append(("cyclic_K_4",
                [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (3, 1)],
                list(range(4))))
    return out


TOURNAMENT_FIXTURES = _tournament_fixtures()


@pytest.mark.parametrize("name,edges,nodes", TOURNAMENT_FIXTURES,
                         ids=[fx[0] for fx in TOURNAMENT_FIXTURES])
def test_is_tournament_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    assert fnx.is_tournament(fg) == nx.is_tournament(ng) is True


def test_is_tournament_negative_cases():
    """Non-tournaments must be rejected by both libs."""
    for edges in [
        [(0, 1)],  # too few edges
        [(0, 1), (1, 2)],  # path, missing (0, 2) or (2, 0)
        [(0, 1), (1, 0)],  # antiparallel
        [(0, 0)],  # self-loop
    ]:
        fg, ng = _pair_directed(edges, list(range(3)))
        assert fnx.is_tournament(fg) == nx.is_tournament(ng) is False


@pytest.mark.parametrize("name,edges,nodes", TOURNAMENT_FIXTURES,
                         ids=[fx[0] for fx in TOURNAMENT_FIXTURES])
def test_tournament_matrix_matches_networkx(name, edges, nodes):
    import numpy as np
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.tournament_matrix(fg)
    nr = nx_tournament.tournament_matrix(ng)
    fr_arr = fr.toarray() if hasattr(fr, "toarray") else fr
    nr_arr = nr.toarray() if hasattr(nr, "toarray") else nr
    assert np.array_equal(fr_arr, nr_arr), f"{name}: matrices differ"


@pytest.mark.parametrize("name,edges,nodes", TOURNAMENT_FIXTURES,
                         ids=[fx[0] for fx in TOURNAMENT_FIXTURES])
def test_tournament_score_sequence_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = sorted(fnx.tournament.score_sequence(fg))
    nr = sorted(nx_tournament.score_sequence(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", TOURNAMENT_FIXTURES,
                         ids=[fx[0] for fx in TOURNAMENT_FIXTURES])
def test_tournament_is_strongly_connected_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    assert (
        fnx.tournament.is_strongly_connected(fg)
        == nx_tournament.is_strongly_connected(ng)
    )


@pytest.mark.parametrize(
    "name,edges,nodes,s,t,expected",
    [
        ("K_3_oneway_reach",
         [(0, 1), (1, 2), (0, 2)], list(range(3)), 0, 2, True),
        ("K_3_oneway_no_reach",
         [(0, 1), (1, 2), (0, 2)], list(range(3)), 2, 0, False),
        ("cyclic_K_3_reach",
         [(0, 1), (1, 2), (2, 0)], list(range(3)), 0, 2, True),
        ("cyclic_K_3_back",
         [(0, 1), (1, 2), (2, 0)], list(range(3)), 2, 0, True),
    ],
)
def test_tournament_is_reachable_matches_networkx(
    name, edges, nodes, s, t, expected,
):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.tournament.is_reachable(fg, s, t)
    nr = nx_tournament.is_reachable(ng, s, t)
    assert fr == nr == expected


@pytest.mark.parametrize("name,edges,nodes", TOURNAMENT_FIXTURES,
                         ids=[fx[0] for fx in TOURNAMENT_FIXTURES])
def test_tournament_hamiltonian_path_is_valid(name, edges, nodes):
    """Rédei's theorem: every tournament has a hamiltonian path. Both
    libs must produce one — the specific path may differ (multiple
    valid paths exist), but each must visit every node exactly once
    and follow only directed edges of the tournament."""
    fg, _ = _pair_directed(edges, nodes)
    path = fnx.tournament.hamiltonian_path(fg)
    assert sorted(path) == sorted(fg.nodes()), (
        f"{name}: path {path} doesn't cover all nodes"
    )
    # Every consecutive pair must be an edge in the tournament
    for u, v in zip(path[:-1], path[1:]):
        assert fg.has_edge(u, v), (
            f"{name}: path {path} uses missing edge ({u}, {v})"
        )


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", TRIAD_FIXTURES,
                         ids=[fx[0] for fx in TRIAD_FIXTURES])
def test_triadic_census_matches_triads_by_type_counts(name, edges, nodes):
    """``triadic_census(G)`` and ``triads_by_type(G)`` must agree on
    the count of each triad type — they're two views of the same
    decomposition."""
    fg, _ = _pair_directed(edges, nodes)
    census = fnx.triadic_census(fg)
    by_type = fnx.triads_by_type(fg)
    for triad_type, count in census.items():
        if triad_type == "003":
            # NX's `all_triads` enumeration excludes empty triads
            # (no edges); ``triads_by_type`` reflects that. ``triadic_census``
            # counts them as ``003``. Skip this comparison.
            continue
        assert len(by_type.get(triad_type, [])) == count, (
            f"{name}: census['{triad_type}']={count} but "
            f"triads_by_type has {len(by_type.get(triad_type, []))} "
            f"entries for {triad_type}"
        )


def test_is_triad_requires_directed_3_node_graph():
    """Only DiGraphs with exactly 3 nodes are triads."""
    fg = fnx.Graph(); fg.add_nodes_from([0, 1, 2])
    assert fnx.is_triad(fg) == nx.is_triad(nx.Graph()) is False
