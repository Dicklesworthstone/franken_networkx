"""NetworkX conformance for the chordal graph algorithm family.

Covers ``is_chordal``, ``chordal_graph_cliques``,
``chordal_graph_treewidth``, ``find_induced_nodes``, and
``complete_to_chordal_graph`` against the upstream reference. Inputs
include known chordal / non-chordal graphs, low-order edge cases, and
random graphs across a range of densities so that bit-for-bit parity
is asserted across 60+ fixtures.

Each fixture builds a fresh ``fnx.Graph`` and a fresh ``nx.Graph`` with
an identical edge list / node insertion order, so any divergence is a
real algorithmic difference rather than a fixture artifact.
"""

from __future__ import annotations

import itertools
import random

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _build_pair(edges, nodes=None):
    """Return matched (fnx.Graph, nx.Graph) with identical insertion order.

    Adds nodes first (in order) so node insertion order matches between
    libraries; this is the only way to make ``complete_to_chordal_graph``
    return identical alpha maps, since alpha depends on tie-breaking
    by node iteration order.
    """
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _chordal_path(n):
    """Path graph P_n — chordal (a tree)."""
    return list(zip(range(n - 1), range(1, n)))


def _chordal_complete(n):
    """Complete graph K_n — chordal."""
    return list(itertools.combinations(range(n), 2))


def _chordal_star(n):
    """Star S_n — chordal (a tree)."""
    return [(0, i) for i in range(1, n + 1)]


def _chordal_k_tree(n, k):
    """k-tree on n nodes (n >= k+1) — chordal by construction.

    Start with a (k+1)-clique; each subsequent node is connected to a
    k-clique among the existing nodes (here: the most recent k nodes).
    """
    if n < k + 1:
        raise ValueError("n must be >= k+1")
    edges = list(itertools.combinations(range(k + 1), 2))
    for new in range(k + 1, n):
        for v in range(new - k, new):
            edges.append((v, new))
    return edges


def _non_chordal_cycle(n):
    """Cycle C_n with n >= 4 — non-chordal."""
    return [(i, (i + 1) % n) for i in range(n)]


def _non_chordal_two_chord_cycle(n):
    """Cycle C_n with a single chord splitting it into two cycles ≥ 4.

    Non-chordal iff at least one of the two halves has length >= 4.
    For n >= 8 with chord at (0, n//2), both halves are >= 4.
    """
    edges = [(i, (i + 1) % n) for i in range(n)]
    edges.append((0, n // 2))
    return edges


def _disconnected_two_chordal_components(a, b):
    """Two disjoint chordal pieces — disconnected, still chordal."""
    edges = [(i, j) for i, j in _chordal_complete(a)]
    edges.extend((a + i, a + j) for i, j in _chordal_complete(b))
    return edges


# ---------------------------------------------------------------------------
# Known-classification cases
# ---------------------------------------------------------------------------


CHORDAL_FIXTURES = [
    ("empty", [], list(range(0))),
    ("single", [], [0]),
    ("two_isolated", [], [0, 1]),
    ("k1", [], [0]),
    ("k2", _chordal_complete(2), list(range(2))),
    ("k3", _chordal_complete(3), list(range(3))),
    ("k4", _chordal_complete(4), list(range(4))),
    ("k5", _chordal_complete(5), list(range(5))),
    ("k6", _chordal_complete(6), list(range(6))),
    ("path_3", _chordal_path(3), list(range(3))),
    ("path_5", _chordal_path(5), list(range(5))),
    ("path_8", _chordal_path(8), list(range(8))),
    ("star_5", _chordal_star(5), list(range(6))),
    ("star_8", _chordal_star(8), list(range(9))),
    ("two_triangles_at_vertex",
     [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
     list(range(5))),
    ("k3_plus_pendant",
     [(0, 1), (1, 2), (2, 0), (2, 3)],
     list(range(4))),
    ("k4_plus_path",
     [*_chordal_complete(4), (3, 4), (4, 5)],
     list(range(6))),
    ("two_components_k3_p2",
     _disconnected_two_chordal_components(3, 2),
     list(range(5))),
    ("two_components_k4_k3",
     _disconnected_two_chordal_components(4, 3),
     list(range(7))),
    ("k_tree_2_5", _chordal_k_tree(5, 2), list(range(5))),
    ("k_tree_2_8", _chordal_k_tree(8, 2), list(range(8))),
    ("k_tree_3_7", _chordal_k_tree(7, 3), list(range(7))),
    ("k_tree_3_10", _chordal_k_tree(10, 3), list(range(10))),
    ("interval_overlap",
     # Intervals [0,2], [1,3], [2,4], [3,5] → interval graph (chordal).
     [(0, 1), (1, 2), (2, 3)],
     list(range(4))),
    ("k4_minus_one_edge",
     # K4 minus an edge: still chordal because 4-cycle has a chord.
     [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3)],
     list(range(4))),
]


NON_CHORDAL_FIXTURES = [
    ("c4", _non_chordal_cycle(4), list(range(4))),
    ("c5", _non_chordal_cycle(5), list(range(5))),
    ("c6", _non_chordal_cycle(6), list(range(6))),
    ("c8", _non_chordal_cycle(8), list(range(8))),
    ("c10", _non_chordal_cycle(10), list(range(10))),
    ("c8_with_split_chord", _non_chordal_two_chord_cycle(8), list(range(8))),
    ("c10_with_split_chord", _non_chordal_two_chord_cycle(10), list(range(10))),
    ("petersen",
     [(u, v) for u, v in nx.petersen_graph().edges()],
     list(nx.petersen_graph().nodes())),
    ("k_3_3",
     [(u, v) for u, v in nx.complete_bipartite_graph(3, 3).edges()],
     list(nx.complete_bipartite_graph(3, 3).nodes())),
    ("c5_plus_isolated",
     _non_chordal_cycle(5),
     [*range(5), 99]),
    ("two_components_c4_k3",
     [*_non_chordal_cycle(4), (4, 5), (5, 6), (6, 4)],
     list(range(7))),
    ("hypercube_q3",
     [(u, v) for u, v in nx.hypercube_graph(3).edges()],
     list(nx.hypercube_graph(3).nodes())),
]


def _random_graph_fixtures():
    """Generate random graphs at several (n, p) settings — covers the
    long tail of structures the hand-picked fixtures don't reach."""
    out = []
    for n, p, seed in [
        (8, 0.2, 1), (8, 0.4, 1), (8, 0.6, 1), (8, 0.8, 1),
        (10, 0.15, 2), (10, 0.3, 2), (10, 0.5, 2), (10, 0.7, 2),
        (12, 0.2, 3), (12, 0.4, 3), (12, 0.6, 3),
        (15, 0.15, 4), (15, 0.3, 4), (15, 0.5, 4),
        (18, 0.2, 5), (18, 0.4, 5),
        (20, 0.15, 6), (20, 0.3, 6), (20, 0.5, 6),
        (25, 0.2, 7), (25, 0.4, 7),
        (30, 0.2, 8), (30, 0.3, 8),
    ]:
        nxg = nx.gnp_random_graph(n, p, seed=seed)
        edges = list(nxg.edges())
        nodes = list(range(n))
        out.append((f"gnp_n{n}_p{p}_s{seed}", edges, nodes))
    return out


RANDOM_FIXTURES = _random_graph_fixtures()


ALL_FIXTURES = CHORDAL_FIXTURES + NON_CHORDAL_FIXTURES + RANDOM_FIXTURES


# ---------------------------------------------------------------------------
# is_chordal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_is_chordal_matches_networkx(name, edges, nodes):
    fg, ng = _build_pair(edges, nodes)
    assert fnx.is_chordal(fg) == nx.is_chordal(ng)


@pytest.mark.parametrize("name,edges,nodes",
                         CHORDAL_FIXTURES,
                         ids=[fx[0] for fx in CHORDAL_FIXTURES])
def test_known_chordal_fixtures_are_chordal(name, edges, nodes):
    fg, _ = _build_pair(edges, nodes)
    assert fnx.is_chordal(fg) is True, f"{name} should be chordal"


@pytest.mark.parametrize("name,edges,nodes",
                         NON_CHORDAL_FIXTURES,
                         ids=[fx[0] for fx in NON_CHORDAL_FIXTURES])
def test_known_non_chordal_fixtures_are_not_chordal(name, edges, nodes):
    fg, _ = _build_pair(edges, nodes)
    assert fnx.is_chordal(fg) is False, f"{name} should be non-chordal"


# ---------------------------------------------------------------------------
# chordal_graph_cliques (only valid on chordal graphs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes",
                         CHORDAL_FIXTURES,
                         ids=[fx[0] for fx in CHORDAL_FIXTURES])
def test_chordal_graph_cliques_matches_networkx(name, edges, nodes):
    fg, ng = _build_pair(edges, nodes)
    fnx_cliques = sorted(frozenset(c) for c in fnx.chordal_graph_cliques(fg))
    nx_cliques = sorted(frozenset(c) for c in nx.chordal_graph_cliques(ng))
    assert fnx_cliques == nx_cliques


@pytest.mark.parametrize("name,edges,nodes",
                         CHORDAL_FIXTURES,
                         ids=[fx[0] for fx in CHORDAL_FIXTURES])
def test_chordal_graph_cliques_yields_frozensets(name, edges, nodes):
    """``chordal_graph_cliques`` returns a generator of frozensets per
    NX's contract — not a list of lists."""
    fg, _ = _build_pair(edges, nodes)
    cliques = fnx.chordal_graph_cliques(fg)
    # generator-y: iter(x) is x for a generator
    assert iter(cliques) is cliques
    for clique in cliques:
        assert isinstance(clique, frozenset)


# ---------------------------------------------------------------------------
# chordal_graph_treewidth (only valid on chordal graphs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes",
                         CHORDAL_FIXTURES,
                         ids=[fx[0] for fx in CHORDAL_FIXTURES])
def test_chordal_graph_treewidth_matches_networkx(name, edges, nodes):
    fg, ng = _build_pair(edges, nodes)

    try:
        nx_tw = nx.chordal_graph_treewidth(ng)
    except Exception as nx_exc:
        with pytest.raises(type(nx_exc)):
            fnx.chordal_graph_treewidth(fg)
        return

    fnx_tw = fnx.chordal_graph_treewidth(fg)
    assert fnx_tw == nx_tw


# ---------------------------------------------------------------------------
# find_induced_nodes (only valid on chordal graphs)
# ---------------------------------------------------------------------------


def _connected_chordal_pairs():
    """Yield (name, edges, nodes, s, t) — chordal fixtures with an
    (s, t) pair where s and t are both in the graph."""
    for name, edges, nodes in CHORDAL_FIXTURES:
        if len(nodes) < 2:
            continue
        # pick first two nodes for determinism
        yield name, edges, nodes, nodes[0], nodes[1]


CHORDAL_INDUCED_PAIRS = list(_connected_chordal_pairs())


@pytest.mark.parametrize(
    "name,edges,nodes,s,t",
    CHORDAL_INDUCED_PAIRS,
    ids=[fx[0] for fx in CHORDAL_INDUCED_PAIRS],
)
def test_find_induced_nodes_matches_networkx(name, edges, nodes, s, t):
    fg, ng = _build_pair(edges, nodes)

    try:
        nx_result = nx.find_induced_nodes(ng, s, t)
    except Exception as nx_exc:
        with pytest.raises(type(nx_exc)):
            fnx.find_induced_nodes(fg, s, t)
        return

    fnx_result = fnx.find_induced_nodes(fg, s, t)
    assert set(fnx_result) == set(nx_result)


# ---------------------------------------------------------------------------
# complete_to_chordal_graph
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_complete_to_chordal_graph_matches_networkx(name, edges, nodes):
    fg, ng = _build_pair(edges, nodes)

    fnx_H, fnx_alpha = fnx.complete_to_chordal_graph(fg)
    nx_H, nx_alpha = nx.complete_to_chordal_graph(ng)

    assert sorted(fnx_H.edges()) == sorted(nx_H.edges()), (
        f"{name}: chordal completion edges diverged"
    )
    assert fnx.is_chordal(fnx_H), (
        f"{name}: completion is supposed to be chordal but isn't"
    )
    # Alpha is the elimination ordering returned by MCS-M; it depends
    # on node-iteration tie-breaking, so the build-helper above
    # establishes identical insertion order on both sides to make this
    # comparison meaningful.
    assert fnx_alpha == nx_alpha, (
        f"{name}: elimination ordering alpha diverged "
        f"(fnx={sorted(fnx_alpha.items())}, "
        f"nx={sorted(nx_alpha.items())})"
    )


# ---------------------------------------------------------------------------
# Self-loop dispatch — NX's _is_complete_graph helper raises when a
# chordal candidate clique contains a self-loop. fnx must mirror the
# selectivity (raise on K_n + self-loop, accept on triangle + self-loop).
# ---------------------------------------------------------------------------


def test_self_loop_on_triangle_is_chordal_no_raise():
    """A triangle plus a self-loop never reaches `_is_complete_graph`
    in NX's algorithm, so no raise — both libraries return True."""
    fg = fnx.Graph()
    ng = nx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 0), (0, 0)]:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    assert fnx.is_chordal(fg) == nx.is_chordal(ng) is True


def test_self_loop_on_k4_raises_matching_networkx():
    """K_4 with a self-loop reaches `_is_complete_graph` and must
    raise NetworkXError with NX's exact wording."""
    fg = fnx.Graph()
    ng = nx.Graph()
    for u, v in itertools.combinations(range(4), 2):
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    fg.add_edge(0, 0)
    ng.add_edge(0, 0)

    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.is_chordal(ng)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.is_chordal(fg)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# find_induced_nodes error parity on non-chordal input
# ---------------------------------------------------------------------------


def test_find_induced_nodes_on_non_chordal_raises_matching_networkx():
    fg, ng = _build_pair(_non_chordal_cycle(4), list(range(4)))
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.find_induced_nodes(ng, 0, 2)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.find_induced_nodes(fg, 0, 2)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_find_induced_nodes_with_missing_target_returns_empty_set_like_nx():
    """NX returns ``set()`` when the target isn't in the graph."""
    fg, ng = _build_pair([(0, 1), (1, 2)], list(range(3)))
    assert fnx.find_induced_nodes(fg, 0, 99) == nx.find_induced_nodes(ng, 0, 99)


# ---------------------------------------------------------------------------
# Multigraph / DiGraph dispatch
# ---------------------------------------------------------------------------


def test_is_chordal_rejects_directed_input():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.is_chordal(fg)


def test_is_chordal_rejects_multigraph_input():
    fg = fnx.MultiGraph()
    fg.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.is_chordal(fg)


def test_chordal_graph_treewidth_rejects_directed_input():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.chordal_graph_treewidth(fg)


# ---------------------------------------------------------------------------
# Idempotence of chordal completion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 0 < len(fx[2]) <= 12],
    ids=[fx[0] for fx in ALL_FIXTURES if 0 < len(fx[2]) <= 12],
)
def test_complete_to_chordal_graph_is_idempotent(name, edges, nodes):
    """Applying chordal completion twice must equal applying it once —
    H is already chordal, so the second pass is a no-op on edges."""
    fg, _ = _build_pair(edges, nodes)
    H, _alpha = fnx.complete_to_chordal_graph(fg)
    HH, _alpha2 = fnx.complete_to_chordal_graph(H)
    assert sorted(H.edges()) == sorted(HH.edges())
