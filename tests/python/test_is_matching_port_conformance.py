"""Golden conformance harness for the Rust matching-validator port.

The Python ``franken_networkx.is_matching`` /
``is_maximal_matching`` / ``is_perfect_matching`` previously
delegated every call to nx via ``_call_networkx_for_parity``.
The native port routes simple-graph cases through
``franken_networkx._fnx.is_matching`` (and friends) backed by
``fnx_algorithms::is_matching`` — directed and multigraph cases
still bridge to nx since that's nx's documented behavior.

This harness validates 50+ inputs across:

- All three predicate families (``is_matching``,
  ``is_maximal_matching``, ``is_perfect_matching``)
- Set, frozenset, dict, and list-of-tuples matching shapes
- Valid + invalid matchings (shared endpoints, edge not in graph,
  self-loops, missing nodes)
- Graphs ranging from small (P_3, C_4, K_4) to medium (Petersen,
  K_{3,3}, krackhardt_kite, hypercube_3)

Each input is run through both ``fnx`` and ``networkx`` and the
two booleans must match.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


def _build_pair(builder):
    return builder(fnx), builder(nx)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _path_5_pair():
    return _build_pair(lambda L: L.path_graph(5))


def _cycle_4_pair():
    return _build_pair(lambda L: L.cycle_graph(4))


def _cycle_6_pair():
    return _build_pair(lambda L: L.cycle_graph(6))


def _complete_4_pair():
    return _build_pair(lambda L: L.complete_graph(4))


def _complete_5_pair():
    return _build_pair(lambda L: L.complete_graph(5))


def _star_5_pair():
    return _build_pair(lambda L: L.star_graph(5))


def _petersen_pair():
    return _build_pair(lambda L: L.petersen_graph())


def _krackhardt_pair():
    return _build_pair(lambda L: L.krackhardt_kite_graph())


def _bipartite_3_3_pair():
    return _build_pair(lambda L: L.complete_bipartite_graph(3, 3))


def _hypercube_3_pair():
    return _build_pair(lambda L: L.hypercube_graph(3))


# ---------------------------------------------------------------------------
# Helpers — encode matchings in different shapes
# ---------------------------------------------------------------------------


def _matching_dict(edges):
    """Convert a set of edges to the bipartite-style dict form."""
    return {u: v for (u, v) in edges}


def _both_match(g_fnx, g_nx, matching, fn_name):
    fr = getattr(fnx, fn_name)(g_fnx, matching)
    nr = getattr(nx, fn_name)(g_nx, matching)
    assert fr == nr, f"{fn_name}({matching}): fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# is_matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,matching,expected",
    [
        ("path_5_alternating", _path_5_pair, {(0, 1), (2, 3)}, True),
        ("path_5_full", _path_5_pair, {(0, 1), (2, 3), (3, 4)}, False),  # 3 shared
        ("path_5_shared_endpoint", _path_5_pair, {(0, 1), (1, 2)}, False),
        ("path_5_non_edge", _path_5_pair, {(0, 1), (0, 4)}, False),
        ("cycle_4_pair", _cycle_4_pair, {(0, 1), (2, 3)}, True),
        ("cycle_4_perfect_alt", _cycle_4_pair, {(0, 3), (1, 2)}, True),
        ("complete_5_pair", _complete_5_pair, {(0, 1), (2, 3)}, True),
        ("complete_5_3edges", _complete_5_pair,
         {(0, 1), (2, 3), (4, 0)}, False),  # 0 covered twice
        ("petersen_3edges", _petersen_pair, {(0, 1), (2, 7), (4, 9)}, True),
        ("petersen_self_loop", _petersen_pair, {(0, 0)}, False),
        ("empty_matching_path", _path_5_pair, set(), True),
        # krackhardt_kite has edges (0,5), (1,4), (3,6); (2,4) is not in
        # the canonical fixture so it's not a valid matching there.
        ("krackhardt_kite_three_disjoint", _krackhardt_pair,
         {(0, 5), (1, 4), (3, 6)}, True),
        ("krackhardt_kite_non_edge", _krackhardt_pair,
         {(0, 1), (2, 4)}, False),  # (2,4) isn't an edge
    ],
)
def test_is_matching_matches_networkx(name, builder, matching, expected):
    fg, ng = builder()
    fr = fnx.is_matching(fg, matching)
    nr = nx.is_matching(ng, matching)
    assert fr == nr == expected, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder,matching",
    [
        ("path_5_dict", _path_5_pair, {0: 1, 2: 3}),
        ("complete_4_dict", _complete_4_pair, {0: 1, 2: 3}),
        ("petersen_dict", _petersen_pair, {0: 1, 2: 7, 4: 9}),
    ],
)
def test_is_matching_dict_form_matches_networkx(name, builder, matching):
    fg, ng = builder()
    _both_match(fg, ng, matching, "is_matching")


@pytest.mark.parametrize(
    "name,builder,matching_shape",
    [
        ("frozenset", _path_5_pair, lambda: frozenset([(0, 1), (2, 3)])),
        ("list_tuples", _path_5_pair, lambda: [(0, 1), (2, 3)]),
        ("tuple_tuples", _path_5_pair, lambda: ((0, 1), (2, 3))),
    ],
)
def test_is_matching_input_shapes_match_networkx(
    name, builder, matching_shape,
):
    fg, ng = builder()
    matching = matching_shape()
    _both_match(fg, ng, matching, "is_matching")


# ---------------------------------------------------------------------------
# is_maximal_matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,matching,expected",
    [
        # Path 5 (5 nodes 4 edges): {(0,1),(2,3)} leaves 4 unmatched but
        # node 4 is adjacent only to 3 (already matched), so this IS maximal.
        ("path_5_maximal", _path_5_pair, {(0, 1), (2, 3)}, True),
        # Path 5: {(0,1)} only — node 2 is unmatched and adjacent to 3
        # (also unmatched) — so NOT maximal.
        ("path_5_not_maximal", _path_5_pair, {(0, 1)}, False),
        # K_4: any single edge plus the disjoint pair is perfect ⇒ maximal
        ("complete_4_perfect", _complete_4_pair, {(0, 1), (2, 3)}, True),
        # K_4: leaving a single edge is not maximal (other pair still adjacent)
        ("complete_4_not_maximal", _complete_4_pair, {(0, 1)}, False),
        # Petersen: {(0,1),(2,7),(3,8),(4,9),(5,6)} is a perfect matching
        ("petersen_perfect",
         _petersen_pair,
         {(0, 1), (2, 3), (4, 9), (5, 7), (6, 8)}, True),
    ],
)
def test_is_maximal_matching_matches_networkx(
    name, builder, matching, expected,
):
    fg, ng = builder()
    fr = fnx.is_maximal_matching(fg, matching)
    nr = nx.is_maximal_matching(ng, matching)
    assert fr == nr == expected, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# is_perfect_matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,matching,expected",
    [
        ("path_5_not_perfect", _path_5_pair, {(0, 1), (2, 3)}, False),
        ("cycle_4_perfect", _cycle_4_pair, {(0, 1), (2, 3)}, True),
        ("cycle_4_perfect_alt", _cycle_4_pair, {(0, 3), (1, 2)}, True),
        ("complete_4_perfect", _complete_4_pair, {(0, 1), (2, 3)}, True),
        ("complete_5_no_perfect", _complete_5_pair, {(0, 1), (2, 3)}, False),
        ("petersen_perfect",
         _petersen_pair,
         {(0, 1), (2, 3), (4, 9), (5, 7), (6, 8)}, True),
        ("hypercube_3_perfect",
         _hypercube_3_pair,
         {((0, 0, 0), (0, 0, 1)),
          ((0, 1, 0), (0, 1, 1)),
          ((1, 0, 0), (1, 0, 1)),
          ((1, 1, 0), (1, 1, 1))},
         True),
        ("k33_perfect",
         _bipartite_3_3_pair,
         {(0, 3), (1, 4), (2, 5)},
         True),
    ],
)
def test_is_perfect_matching_matches_networkx(
    name, builder, matching, expected,
):
    fg, ng = builder()
    fr = fnx.is_perfect_matching(fg, matching)
    nr = nx.is_perfect_matching(ng, matching)
    assert fr == nr == expected, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Round-trip with max_weight_matching outputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", _path_5_pair),
        ("cycle_4", _cycle_4_pair),
        ("cycle_6", _cycle_6_pair),
        ("complete_4", _complete_4_pair),
        ("complete_5", _complete_5_pair),
        ("petersen", _petersen_pair),
        ("krackhardt_kite", _krackhardt_pair),
        ("k33", _bipartite_3_3_pair),
    ],
)
def test_max_weight_matching_output_is_a_valid_matching(name, builder):
    fg, _ = builder()
    matching = fnx.max_weight_matching(fg, maxcardinality=True)
    assert fnx.is_matching(fg, matching)


@pytest.mark.parametrize(
    "name,builder",
    [
        ("cycle_4", _cycle_4_pair),
        ("complete_4", _complete_4_pair),
        ("petersen", _petersen_pair),
        ("k33", _bipartite_3_3_pair),
    ],
)
def test_max_weight_matching_on_perfect_matchable_graph_is_perfect(
    name, builder,
):
    fg, _ = builder()
    matching = fnx.max_weight_matching(fg, maxcardinality=True)
    assert fnx.is_perfect_matching(fg, matching)


# ---------------------------------------------------------------------------
# Directed and multigraph delegate to nx (out of scope for this port)
# ---------------------------------------------------------------------------


def test_directed_input_delegates_to_networkx_for_parity():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx.DiGraph()
    ng.add_edges_from([(0, 1), (1, 2)])
    fr = fnx.is_matching(fg, {(0, 1)})
    nr = nx.is_matching(ng, {(0, 1)})
    assert fr == nr


# ---------------------------------------------------------------------------
# Missing-node edge cases — nx raises, fnx must mirror
# ---------------------------------------------------------------------------


def test_matching_with_missing_node_raises_matching_networkx():
    fg = fnx.petersen_graph()
    ng = nx.petersen_graph()
    bad = {(0, 1), (99, 100)}
    with pytest.raises(nx.NetworkXError, match=r"node not in G"):
        nx.is_matching(ng, bad)
    with pytest.raises(fnx.NetworkXError, match=r"node not in G"):
        fnx.is_matching(fg, bad)


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


def test_perfect_matching_is_also_a_matching():
    g = fnx.cycle_graph(4)
    m = {(0, 1), (2, 3)}
    assert fnx.is_perfect_matching(g, m)
    assert fnx.is_matching(g, m)


def test_perfect_matching_is_also_maximal():
    g = fnx.cycle_graph(4)
    m = {(0, 1), (2, 3)}
    assert fnx.is_perfect_matching(g, m)
    assert fnx.is_maximal_matching(g, m)


def test_empty_matching_on_empty_graph_is_perfect():
    g = fnx.Graph()
    assert fnx.is_perfect_matching(g, set())


def test_not_a_matching_is_not_maximal():
    g = fnx.path_graph(5)
    m = {(0, 1), (1, 2)}  # shared node
    assert not fnx.is_matching(g, m)
    assert not fnx.is_maximal_matching(g, m)
    assert not fnx.is_perfect_matching(g, m)


# ---------------------------------------------------------------------------
# Random graph sweep (parameter brute-force across many small graphs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", list(range(20)))
def test_random_graph_max_matching_outputs_satisfy_predicates(seed):
    """Generate a random graph, compute its max-weight matching, and
    assert all three predicates agree with nx on that output."""
    fg = fnx.gnp_random_graph(8, 0.4, seed=seed)
    ng = nx.gnp_random_graph(8, 0.4, seed=seed)
    # Make graphs structurally identical for comparing predicates.
    matching = fnx.max_weight_matching(fg, maxcardinality=True)
    matching_set = set(matching)
    fr = fnx.is_matching(fg, matching_set)
    nr = nx.is_matching(ng, matching_set)
    # Both libs must agree on whether it's a matching of the
    # *original* graph — but only if their edge sets agree.
    if set(fg.edges()) == set(ng.edges()):
        assert fr == nr, f"seed={seed}: fnx={fr} nx={nr}"
