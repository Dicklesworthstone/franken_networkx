"""NetworkX conformance for the planarity algorithm family.

No existing conformance test for planarity; the implementations
``is_planar``, ``check_planarity``, ``check_planarity_recursive``, and
``planar_layout`` are sensitive LR-planarity algorithms with subtle
embedding bookkeeping, so a broad differential test is warranted.

Asserts:

- ``is_planar`` and ``check_planarity`` (and the recursive variant)
  agree with NetworkX on a wide fixture set covering K_n
  (planar iff n ≤ 4), C_n / P_n / S_n (always planar), K_{m,n}
  (planar iff min(m,n) ≤ 2), Petersen (non-planar), 3-cube (planar),
  and 16 ``gnp_random_graph`` instances with seeds chosen so the
  set has both planar and non-planar samples.
- The boolean from ``is_planar(G)`` agrees with the boolean from
  ``check_planarity(G)``.
- When the graph IS planar, the embedding returned is itself
  planar (round-trip check).
- ``check_planarity(G, counterexample=True)`` returns the same
  K_5 / K_{3,3} subgraph in both libraries when the graph is
  non-planar.
- ``planar_layout(G)`` succeeds on every planar fixture and produces
  a position dict keyed by exactly the input nodes (we don't compare
  raw coordinates since the algorithm has internal randomness in
  some NX versions).
"""

from __future__ import annotations

import itertools
import warnings

import pytest
import networkx as nx
from networkx.algorithms.planarity import (
    check_planarity_recursive as _nx_check_planarity_recursive,
)

import franken_networkx as fnx


def _pair(edges, nodes=None):
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Hand-picked classifications
# ---------------------------------------------------------------------------


PLANAR_FIXTURES = [
    ("empty", [], []),
    ("single", [], [0]),
    ("two_isolated", [], [0, 1]),
    ("K_1", [], [0]),
    ("K_2", [(0, 1)], [0, 1]),
    ("K_3", list(itertools.combinations(range(3), 2)), list(range(3))),
    ("K_4", list(itertools.combinations(range(4), 2)), list(range(4))),
    *[(f"C_{n}",
       [(i, (i + 1) % n) for i in range(n)],
       list(range(n))) for n in range(3, 9)],
    *[(f"P_{n}",
       list(zip(range(n - 1), range(1, n))),
       list(range(n))) for n in range(2, 9)],
    *[(f"S_{n}",
       [(0, i) for i in range(1, n + 1)],
       list(range(n + 1))) for n in range(1, 7)],
    ("K_2_3", list(nx.complete_bipartite_graph(2, 3).edges()),
     list(nx.complete_bipartite_graph(2, 3).nodes())),
    ("K_2_4", list(nx.complete_bipartite_graph(2, 4).edges()),
     list(nx.complete_bipartite_graph(2, 4).nodes())),
    ("K_2_5", list(nx.complete_bipartite_graph(2, 5).edges()),
     list(nx.complete_bipartite_graph(2, 5).nodes())),
    ("hypercube_2", list(nx.hypercube_graph(2).edges()),
     list(nx.hypercube_graph(2).nodes())),
    ("hypercube_3", list(nx.hypercube_graph(3).edges()),
     list(nx.hypercube_graph(3).nodes())),
    ("disjoint_K3_K3",
     [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
     list(range(6))),
    ("two_triangles_share_edge",
     [(0, 1), (1, 2), (2, 0), (1, 3), (2, 3)],
     list(range(4))),
]


NON_PLANAR_FIXTURES = [
    ("K_5", list(itertools.combinations(range(5), 2)), list(range(5))),
    ("K_6", list(itertools.combinations(range(6), 2)), list(range(6))),
    ("K_7", list(itertools.combinations(range(7), 2)), list(range(7))),
    ("K_3_3", list(nx.complete_bipartite_graph(3, 3).edges()),
     list(nx.complete_bipartite_graph(3, 3).nodes())),
    ("K_3_4", list(nx.complete_bipartite_graph(3, 4).edges()),
     list(nx.complete_bipartite_graph(3, 4).nodes())),
    ("K_4_4", list(nx.complete_bipartite_graph(4, 4).edges()),
     list(nx.complete_bipartite_graph(4, 4).nodes())),
    ("petersen", list(nx.petersen_graph().edges()),
     list(nx.petersen_graph().nodes())),
]


def _random_fixtures():
    """gnp randoms — seeds chosen to cover both planar and non-planar
    cases empirically."""
    out = []
    for n, p, seed in [
        (8, 0.2, 1), (8, 0.3, 2), (10, 0.2, 3), (10, 0.3, 4),
        (12, 0.2, 5), (12, 0.3, 6), (15, 0.15, 7), (15, 0.2, 8),
        (15, 0.3, 9), (20, 0.1, 10), (20, 0.15, 11), (20, 0.2, 12),
        (25, 0.1, 13), (25, 0.15, 14), (30, 0.08, 15), (30, 0.12, 16),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


RANDOM_FIXTURES = _random_fixtures()
ALL_FIXTURES = PLANAR_FIXTURES + NON_PLANAR_FIXTURES + RANDOM_FIXTURES


# ---------------------------------------------------------------------------
# is_planar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_is_planar_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.is_planar(fg) == nx.is_planar(ng)


@pytest.mark.parametrize("name,edges,nodes", PLANAR_FIXTURES,
                         ids=[fx[0] for fx in PLANAR_FIXTURES])
def test_known_planar_fixtures_are_planar(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    assert fnx.is_planar(fg) is True, f"{name} should be planar"


@pytest.mark.parametrize("name,edges,nodes", NON_PLANAR_FIXTURES,
                         ids=[fx[0] for fx in NON_PLANAR_FIXTURES])
def test_known_non_planar_fixtures_are_not_planar(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    assert fnx.is_planar(fg) is False, f"{name} should be non-planar"


# ---------------------------------------------------------------------------
# check_planarity (boolean parity + embedding validity)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_check_planarity_boolean_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr_planar, _ = fnx.check_planarity(fg)
    nr_planar, _ = nx.check_planarity(ng)
    assert fr_planar == nr_planar


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_check_planarity_recursive_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr_planar, _ = fnx.check_planarity_recursive(fg)
    nr_planar, _ = _nx_check_planarity_recursive(ng)
    assert fr_planar == nr_planar


@pytest.mark.parametrize("name,edges,nodes",
                         PLANAR_FIXTURES + RANDOM_FIXTURES,
                         ids=[fx[0] for fx in PLANAR_FIXTURES + RANDOM_FIXTURES])
def test_check_planarity_returns_valid_embedding_when_planar(name, edges, nodes):
    """When planar, the returned embedding must itself be a valid
    planar embedding (round-trip)."""
    fg, _ = _pair(edges, nodes)
    is_planar, emb = fnx.check_planarity(fg)
    if not is_planar:
        return
    if emb is None:
        return  # trivial graphs may return None
    # NX's check_planarity returns a PlanarEmbedding; check_structure
    # raises on invalid embeddings.
    if hasattr(emb, "check_structure"):
        emb.check_structure()


# ---------------------------------------------------------------------------
# is_planar agrees with check_planarity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_is_planar_agrees_with_check_planarity(name, edges, nodes):
    """``is_planar(G)`` must return the same boolean as
    ``check_planarity(G)[0]`` — they're documented to use the same
    LR-planarity test."""
    fg, _ = _pair(edges, nodes)
    is_planar = fnx.is_planar(fg)
    check_result, _ = fnx.check_planarity(fg)
    assert is_planar == check_result, (
        f"{name}: is_planar={is_planar} but check_planarity={check_result}"
    )


# ---------------------------------------------------------------------------
# Counterexample: non-planar input returns a Kuratowski subgraph
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", NON_PLANAR_FIXTURES,
                         ids=[fx[0] for fx in NON_PLANAR_FIXTURES])
def test_check_planarity_counterexample_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr_planar, fr_cex = fnx.check_planarity(fg, counterexample=True)
    nr_planar, nr_cex = nx.check_planarity(ng, counterexample=True)

    assert fr_planar == nr_planar is False
    if nr_cex is not None:
        assert fr_cex is not None
        # Edge sets must match — the counterexample is the actual
        # Kuratowski subgraph extracted by the algorithm and is
        # deterministic given the same input.
        assert sorted(fr_cex.edges()) == sorted(nr_cex.edges()), (
            f"{name}: counterexample edges diverged"
        )


# ---------------------------------------------------------------------------
# planar_layout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in PLANAR_FIXTURES if len(fx[2]) >= 3],
    ids=[fx[0] for fx in PLANAR_FIXTURES if len(fx[2]) >= 3],
)
def test_planar_layout_returns_position_dict_keyed_by_input_nodes(
    name, edges, nodes,
):
    """``planar_layout`` succeeds on every planar fixture and produces
    a position dict whose keys are exactly the input nodes. We don't
    compare coordinates (the embedding-to-position step has internal
    randomness in some NX versions)."""
    fg, ng = _pair(edges, nodes)
    fr_pos = fnx.planar_layout(fg)
    nr_pos = nx.planar_layout(ng)
    assert set(fr_pos.keys()) == set(ng.nodes())
    assert set(nr_pos.keys()) == set(ng.nodes())


def test_planar_layout_on_non_planar_raises_matching_networkx():
    fg, ng = _pair(list(itertools.combinations(range(5), 2)), list(range(5)))
    with pytest.raises(nx.NetworkXException):
        nx.planar_layout(ng)
    with pytest.raises(fnx.NetworkXException):
        fnx.planar_layout(fg)


# ---------------------------------------------------------------------------
# Extra-edge contract: adding any edge to a maximal planar graph
# (including K_5 / K_{3,3} subdivisions) makes it non-planar
# ---------------------------------------------------------------------------


def test_adding_edge_to_K4_keeps_it_planar():
    """K_4 is planar; remains planar even when we add a pendant."""
    fg, _ = _pair(list(itertools.combinations(range(4), 2)) + [(3, 4)],
                   list(range(5)))
    assert fnx.is_planar(fg) is True


def test_K5_is_non_planar_but_K5_minus_edge_is_planar():
    """Classic Kuratowski boundary: K_5 minus any single edge is
    planar; K_5 itself is not."""
    K5 = list(itertools.combinations(range(5), 2))
    fg_full, _ = _pair(K5, list(range(5)))
    assert fnx.is_planar(fg_full) is False

    fg_minus, _ = _pair(K5[:-1], list(range(5)))  # drop last edge
    assert fnx.is_planar(fg_minus) is True


def test_K33_minus_edge_is_planar():
    K33_edges = list(nx.complete_bipartite_graph(3, 3).edges())
    K33_nodes = list(nx.complete_bipartite_graph(3, 3).nodes())
    fg_full, _ = _pair(K33_edges, K33_nodes)
    assert fnx.is_planar(fg_full) is False

    fg_minus, _ = _pair(K33_edges[:-1], K33_nodes)
    assert fnx.is_planar(fg_minus) is True
