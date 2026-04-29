"""NetworkX conformance for the matching algorithm family.

Existing tests (``test_matching.py``, ``test_matching_additional.py``,
plus tuple-direction parity files) cover specific edge-tuple
orientation cases. Add a broad differential test that exercises the
full family across structured + random fixtures so any silent
divergence in matching choice, weighted optimization, predicate, or
generator contract surfaces immediately.

Covered functions:

- ``maximal_matching(G)`` — greedy maximal matching.
- ``max_weight_matching(G, weight=, maxcardinality=)`` — Edmonds'
  blossom algorithm.
- ``min_weight_matching(G, weight=)`` — Edmonds' blossom + negation.
- ``is_matching(G, matching)``,
  ``is_maximal_matching(G, matching)``,
  ``is_perfect_matching(G, matching)`` — predicates.
- ``min_maximal_matching(G)`` — approximation algorithm
  (NX submodule path).

Asserts bit-for-bit edge-set equality (compared as sets of frozensets
to ignore endpoint orientation), validity invariants, and cross-
relation correctness.
"""

from __future__ import annotations

import itertools
import warnings

import pytest
import networkx as nx
from networkx.algorithms.approximation import (
    min_maximal_matching as _nx_min_maximal_matching,
)

import franken_networkx as fnx


def _pair(edges, nodes=None, *, with_weight=False):
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    if with_weight:
        for u, v, w in edges:
            fg.add_edge(u, v, weight=w)
            ng.add_edge(u, v, weight=w)
    else:
        for u, v in edges:
            fg.add_edge(u, v)
            ng.add_edge(u, v)
    return fg, ng


def _edges_to_frozenset_set(matching):
    return {frozenset(e) for e in matching}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _structured_fixtures():
    out = []
    out.append(("triangle", [(0, 1), (1, 2), (2, 0)], [0, 1, 2]))
    out.append(("square", [(0, 1), (1, 2), (2, 3), (3, 0)], list(range(4))))
    out.append(("path_P_5",
                [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5))))
    out.append(("path_P_6",
                [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)],
                list(range(6))))
    for n in range(2, 8):
        out.append((f"K_{n}", list(itertools.combinations(range(n), 2)),
                    list(range(n))))
    out.append(("S_4_star",
                [(0, i) for i in range(1, 5)], list(range(5))))
    out.append(("petersen", list(nx.petersen_graph().edges()),
                list(nx.petersen_graph().nodes())))
    for a, b in [(2, 3), (3, 3), (3, 4), (4, 4)]:
        kbg = nx.complete_bipartite_graph(a, b)
        out.append((f"K_{a}_{b}",
                    list(kbg.edges()), list(kbg.nodes())))
    out.append(("disjoint_K3_K3",
                [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    out.append(("two_triangles_bridge",
                [(0, 1), (1, 2), (2, 0), (2, 3),
                 (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    return out


def _random_fixtures():
    out = []
    for n, p, seed in [
        (8, 0.3, 1), (10, 0.3, 2), (10, 0.5, 3),
        (12, 0.3, 4), (15, 0.25, 5),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


def _weighted_fixtures():
    out = []
    out.append(("triangle_w",
                [(0, 1, 1.0), (1, 2, 2.0), (2, 0, 3.0)]))
    out.append(("square_w",
                [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0), (3, 0, 4.0)]))
    out.append(("path_w_4",
                [(0, 1, 1.0), (1, 2, 5.0), (2, 3, 2.0), (3, 4, 4.0)]))
    out.append(("K_4_w",
                [(u, v, float(u + v + 1))
                 for u, v in itertools.combinations(range(4), 2)]))
    out.append(("K_5_w",
                [(u, v, float(u * 10 + v))
                 for u, v in itertools.combinations(range(5), 2)]))
    out.append(("K_3_3_w",
                [(u, v, float(u + 2 * v))
                 for u, v in nx.complete_bipartite_graph(3, 3).edges()]))
    out.append(("petersen_w",
                [(u, v, float(u * 10 + v))
                 for u, v in nx.petersen_graph().edges()]))
    return out


WEIGHTED = _weighted_fixtures()


# ---------------------------------------------------------------------------
# maximal_matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_maximal_matching_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr = _edges_to_frozenset_set(fnx.maximal_matching(fg))
    nr = _edges_to_frozenset_set(nx.maximal_matching(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_maximal_matching_is_valid(name, edges, nodes):
    """Every maximal matching is itself a matching."""
    fg, _ = _pair(edges, nodes)
    m = fnx.maximal_matching(fg)
    assert fnx.is_matching(fg, m), f"{name}: maximal_matching not a matching"


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_maximal_matching_is_maximal(name, edges, nodes):
    """``maximal_matching(G)`` must be maximal (no edge can be added)."""
    fg, _ = _pair(edges, nodes)
    m = fnx.maximal_matching(fg)
    assert fnx.is_maximal_matching(fg, m)


# ---------------------------------------------------------------------------
# max_weight_matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("maxcard", [False, True])
@pytest.mark.parametrize("name,edges_with_w", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_max_weight_matching_matches_networkx(name, edges_with_w, maxcard):
    fg, ng = _pair(edges_with_w, with_weight=True)
    fr = _edges_to_frozenset_set(
        fnx.max_weight_matching(fg, maxcardinality=maxcard, weight="weight")
    )
    nr = _edges_to_frozenset_set(
        nx.max_weight_matching(ng, maxcardinality=maxcard, weight="weight")
    )
    assert fr == nr, f"{name} maxcard={maxcard}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges_with_w", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_max_weight_matching_is_valid(name, edges_with_w):
    fg, _ = _pair(edges_with_w, with_weight=True)
    m = fnx.max_weight_matching(fg)
    assert fnx.is_matching(fg, m)


# ---------------------------------------------------------------------------
# min_weight_matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges_with_w", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_min_weight_matching_matches_networkx(name, edges_with_w):
    fg, ng = _pair(edges_with_w, with_weight=True)
    fr = _edges_to_frozenset_set(
        fnx.min_weight_matching(fg, weight="weight")
    )
    nr = _edges_to_frozenset_set(
        nx.min_weight_matching(ng, weight="weight")
    )
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Predicates: is_matching, is_maximal_matching, is_perfect_matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes,candidate,expected",
    [
        ("path_partial_valid",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         [(0, 1), (2, 3)], True),
        ("path_full_invalid_share_node",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         [(0, 1), (1, 2)], False),
        ("triangle_singleton",
         [(0, 1), (1, 2), (2, 0)], list(range(3)),
         [(0, 1)], True),
        ("triangle_invalid",
         [(0, 1), (1, 2), (2, 0)], list(range(3)),
         [(0, 1), (1, 2)], False),
        ("empty_matching",
         [(0, 1), (1, 2)], list(range(3)),
         [], True),
        ("K_4_perfect",
         list(itertools.combinations(range(4), 2)), list(range(4)),
         [(0, 1), (2, 3)], True),
    ],
)
def test_is_matching_matches_networkx(name, edges, nodes, candidate, expected):
    fg, ng = _pair(edges, nodes)
    assert fnx.is_matching(fg, candidate) == nx.is_matching(ng, candidate)


@pytest.mark.parametrize(
    "name,edges,nodes,candidate",
    [
        ("path_5_cover_two_edges",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         [(0, 1), (2, 3)]),
        ("K_4_two_edges",
         list(itertools.combinations(range(4), 2)), list(range(4)),
         [(0, 1), (2, 3)]),
        ("S_4_one_edge",
         [(0, i) for i in range(1, 5)], list(range(5)),
         [(0, 1)]),
        ("triangle_singleton",
         [(0, 1), (1, 2), (2, 0)], list(range(3)),
         [(0, 1)]),
    ],
)
def test_is_maximal_matching_matches_networkx(name, edges, nodes, candidate):
    fg, ng = _pair(edges, nodes)
    assert (
        fnx.is_maximal_matching(fg, candidate)
        == nx.is_maximal_matching(ng, candidate)
    )


@pytest.mark.parametrize(
    "name,edges,nodes,candidate",
    [
        ("K_4_perfect",
         list(itertools.combinations(range(4), 2)), list(range(4)),
         [(0, 1), (2, 3)]),
        ("path_P_4_perfect",
         [(0, 1), (1, 2), (2, 3)], list(range(4)),
         [(0, 1), (2, 3)]),
        ("path_P_5_imperfect",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         [(0, 1), (2, 3)]),
    ],
)
def test_is_perfect_matching_matches_networkx(name, edges, nodes, candidate):
    fg, ng = _pair(edges, nodes)
    assert (
        fnx.is_perfect_matching(fg, candidate)
        == nx.is_perfect_matching(ng, candidate)
    )


# ---------------------------------------------------------------------------
# min_maximal_matching (NX approximation submodule)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_min_maximal_matching_is_valid_maximal_matching(name, edges, nodes):
    """fnx and NX may pick different min_maximal_matchings (it's an
    approximation), but the result must be a valid maximal matching
    in both libraries."""
    fg, _ = _pair(edges, nodes)
    m = fnx.min_maximal_matching(fg)
    assert fnx.is_matching(fg, m), f"{name}: not a valid matching"
    assert fnx.is_maximal_matching(fg, m), f"{name}: not maximal"


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges_with_w", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_max_weight_matching_total_weight_no_less_than_min_weight_matching(
    name, edges_with_w,
):
    """Max-weight matching total weight ≥ min-weight matching total
    weight on the same fixture."""
    fg, _ = _pair(edges_with_w, with_weight=True)
    max_m = fnx.max_weight_matching(fg, weight="weight")
    min_m = fnx.min_weight_matching(fg, weight="weight")

    def total(matching):
        return sum(fg.edges[u, v]["weight"] for u, v in matching)
    assert total(max_m) >= total(min_m) - 1e-9


@pytest.mark.parametrize("name,edges_with_w", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_max_weight_matching_with_maxcardinality_has_more_or_equal_edges(
    name, edges_with_w,
):
    """``maxcardinality=True`` enforces maximum-cardinality matching;
    its size must be >= the unconstrained max-weight matching."""
    fg, _ = _pair(edges_with_w, with_weight=True)
    free_m = fnx.max_weight_matching(fg, maxcardinality=False, weight="weight")
    maxcard_m = fnx.max_weight_matching(fg, maxcardinality=True, weight="weight")
    assert len(maxcard_m) >= len(free_m), (
        f"{name}: maxcard size {len(maxcard_m)} < free {len(free_m)}"
    )


# ---------------------------------------------------------------------------
# Empty / single-node dispatch
# ---------------------------------------------------------------------------


def test_maximal_matching_empty_graph_returns_empty_set():
    assert fnx.maximal_matching(fnx.Graph()) == \
        nx.maximal_matching(nx.Graph()) == set()


def test_max_weight_matching_empty_graph_returns_empty_set():
    assert fnx.max_weight_matching(fnx.Graph()) == \
        nx.max_weight_matching(nx.Graph()) == set()


def test_is_matching_on_empty_candidate_returns_true():
    fg = fnx.Graph(); fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx.Graph(); ng.add_edges_from([(0, 1), (1, 2)])
    assert fnx.is_matching(fg, set()) == nx.is_matching(ng, set()) is True


# ---------------------------------------------------------------------------
# Multigraph rejection (NX rejects)
# ---------------------------------------------------------------------------


def test_maximal_matching_rejects_multigraph_matching_networkx():
    fg = fnx.MultiGraph(); fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx.MultiGraph(); ng.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.maximal_matching(ng)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.maximal_matching(fg)


def test_max_weight_matching_multigraph_extension():
    """fnx INTENTIONALLY extends NX by accepting MultiGraph input —
    parallel edges are projected to a simple Graph (taking the max
    weight per pair) before running the blossom algorithm. NX rejects
    multigraphs with NetworkXNotImplemented; lock both behaviors in.

    Per the wrapper docstring: "the previous Rust binding accepted
    MultiGraph by collapsing parallel edges. Preserve that capability."
    """
    fg = fnx.MultiGraph(); fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx.MultiGraph(); ng.add_edges_from([(0, 1), (1, 2)])
    # NX rejects.
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.max_weight_matching(ng)
    # fnx accepts and returns a valid matching of the projected graph.
    m = fnx.max_weight_matching(fg)
    assert isinstance(m, set) and len(m) >= 1


# ---------------------------------------------------------------------------
# DiGraph rejection
# ---------------------------------------------------------------------------


def test_maximal_matching_rejects_digraph_matching_networkx():
    fg = fnx.DiGraph(); fg.add_edge(0, 1)
    ng = nx.DiGraph(); ng.add_edge(0, 1)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.maximal_matching(ng)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.maximal_matching(fg)
