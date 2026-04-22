"""Differential conformance harness for community-detection algorithms.

Bead franken_networkx-my5o: category-level Python-vs-NetworkX parity
	matrix for the core community APIs (louvain, greedy_modularity,
	label_propagation, asyn_lpa, girvan_newman, kernighan_lin_bisection,
	asyn_fluidc, modularity).

Community detection is usually non-deterministic, so the harness
compares invariants (node coverage, disjointness, count bounds, modularity
range) and — where deterministic seeds are supported — exact
normalized partitions.
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize(partition):
    """Return a tuple of sorted-tuple communities, sorted lexicographically.

    Works for list/set/iterator-of-sets outputs — the canonical form used
    to compare partitions for equality regardless of iteration order.
    """
    return tuple(sorted(tuple(sorted(c)) for c in partition))


def _assert_partition_covers_all_nodes(partition, graph):
    all_nodes = set()
    for c in partition:
        assert isinstance(c, (set, frozenset, list, tuple)), type(c)
        for node in c:
            assert node not in all_nodes, f"node {node} appears in multiple communities"
            all_nodes.add(node)
    assert all_nodes == set(graph.nodes()), (
        f"partition missed nodes: {set(graph.nodes()) - all_nodes}"
    )


def _barbell():
    fg = fnx.barbell_graph(4, 2)
    ng = nx.barbell_graph(4, 2)
    return fg, ng


def _karate():
    fg = fnx.karate_club_graph()
    ng = nx.karate_club_graph()
    return fg, ng


def _path(n=6):
    return fnx.path_graph(n), nx.path_graph(n)


# ---------------------------------------------------------------------------
# Louvain
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(_barbell, id="barbell-4-2"),
        pytest.param(_karate, id="karate"),
    ],
)
def test_louvain_partition_invariants(make):
    fg, ng = make()
    f_parts = fnx.louvain_communities(fg, seed=42)
    n_parts = nx.community.louvain_communities(ng, seed=42)

    _assert_partition_covers_all_nodes(f_parts, fg)
    _assert_partition_covers_all_nodes(n_parts, ng)

    # Modularity of each partition should land in the valid range for the
    # same graph.
    f_mod = fnx.modularity(fg, f_parts)
    n_mod = nx.community.modularity(ng, n_parts)
    assert -0.5 <= f_mod <= 1.0
    assert -0.5 <= n_mod <= 1.0
    # Both solvers should reach a reasonable modularity for the same graph;
    # allow a bounded gap since the seeds mean different things across
    # implementations.
    assert abs(f_mod - n_mod) < 0.2, (
        f"louvain modularity diverged: fnx={f_mod} nx={n_mod}"
    )


# ---------------------------------------------------------------------------
# Greedy modularity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(_barbell, id="barbell-4-2"),
        pytest.param(_karate, id="karate"),
    ],
)
def test_greedy_modularity_partition_invariants(make):
    fg, ng = make()
    f_parts = fnx.greedy_modularity_communities(fg)
    n_parts = nx.community.greedy_modularity_communities(ng)

    _assert_partition_covers_all_nodes(f_parts, fg)
    _assert_partition_covers_all_nodes(n_parts, ng)

    # Greedy modularity is typically deterministic — normalized partitions
    # should match.
    assert _normalize(f_parts) == _normalize(n_parts), (
        f"greedy_modularity partition diverged: "
        f"fnx={_normalize(f_parts)} nx={_normalize(n_parts)}"
    )


# ---------------------------------------------------------------------------
# Label propagation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(_barbell, id="barbell-4-2"),
        pytest.param(_karate, id="karate"),
    ],
)
def test_label_propagation_partition_invariants(make):
    fg, ng = make()
    f_parts = list(fnx.label_propagation_communities(fg))
    n_parts = list(nx.community.label_propagation_communities(ng))

    _assert_partition_covers_all_nodes(f_parts, fg)
    _assert_partition_covers_all_nodes(n_parts, ng)

    # Community count lands in the same ballpark for well-separated inputs.
    assert abs(len(f_parts) - len(n_parts)) <= 2


# ---------------------------------------------------------------------------
# Async label propagation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(_barbell, id="barbell-4-2"),
        pytest.param(_karate, id="karate"),
    ],
)
def test_asyn_lpa_partition_invariants(make):
    fg, ng = make()
    f_parts = list(fnx.asyn_lpa_communities(fg, seed=42))
    n_parts = list(nx.community.asyn_lpa_communities(ng, seed=42))

    _assert_partition_covers_all_nodes(f_parts, fg)
    _assert_partition_covers_all_nodes(n_parts, ng)
    assert abs(len(f_parts) - len(n_parts)) <= 2


# ---------------------------------------------------------------------------
# Girvan-Newman (iterator of partitions)
# ---------------------------------------------------------------------------


def test_girvan_newman_first_split_invariants():
    fg, ng = _barbell()
    f_gen = fnx.girvan_newman(fg)
    n_gen = nx.community.girvan_newman(ng)

    f_first = next(iter(f_gen))
    n_first = next(iter(n_gen))
    _assert_partition_covers_all_nodes(f_first, fg)
    _assert_partition_covers_all_nodes(n_first, ng)

    # First split should separate the two clusters of a barbell.
    assert len(f_first) == len(n_first) == 2


# ---------------------------------------------------------------------------
# Kernighan-Lin bisection
# ---------------------------------------------------------------------------


def test_kernighan_lin_bisection_partition_covers_nodes():
    fg, ng = _barbell()
    f_A, f_B = fnx.kernighan_lin_bisection(fg, seed=42)
    n_A, n_B = nx.community.kernighan_lin_bisection(ng, seed=42)

    for A, B, g in [(f_A, f_B, fg), (n_A, n_B, ng)]:
        assert isinstance(A, (set, frozenset))
        assert isinstance(B, (set, frozenset))
        assert not (A & B), "bisection halves overlap"
        assert (A | B) == set(g.nodes())
        assert len(A) == len(B) or abs(len(A) - len(B)) <= 1


# ---------------------------------------------------------------------------
# asyn_fluidc
# ---------------------------------------------------------------------------


def test_asyn_fluidc_partition_invariants():
    fg, ng = _barbell()
    f_parts = list(fnx.asyn_fluidc(fg, k=2, seed=42))
    n_parts = list(nx.community.asyn_fluidc(ng, k=2, seed=42))
    _assert_partition_covers_all_nodes(f_parts, fg)
    _assert_partition_covers_all_nodes(n_parts, ng)
    assert len(f_parts) == len(n_parts) == 2


# ---------------------------------------------------------------------------
# modularity scalar
# ---------------------------------------------------------------------------


def test_modularity_matches_networkx_on_trivial_partition():
    """modularity on a known partition should be close between fnx and nx
    (within tolerance for deterministic computation).
    """
    fg, ng = _barbell()
    # A deterministic partition — split the barbell's two lobes.
    communities = [set(range(0, 4)), set(range(4, 10))]
    f_mod = fnx.modularity(fg, communities)
    n_mod = nx.community.modularity(ng, communities)
    assert math.isclose(f_mod, n_mod, rel_tol=1e-5, abs_tol=1e-7)


def test_modularity_networkx_rejects_incomplete_partition():
    """Upstream nx raises NotAPartition on an incomplete partition.
    Lock that contract for upstream; fnx currently returns a value on
    the same input (known divergence tracked separately).
    """
    _, ng = _barbell()
    bad = [set(range(0, 4))]
    with pytest.raises(nx.NetworkXError):
        nx.community.modularity(ng, bad)


def test_modularity_fnx_incomplete_partition_divergence_is_visible():
    """Document the current divergence: fnx.modularity returns a float on
    an incomplete partition instead of raising NotAPartition like nx.
    When fnx tightens this validation, flip this gate to assert the raise.
    """
    fg, _ = _barbell()
    bad = [set(range(0, 4))]
    # No exception expected today; confirm fnx returns a numeric result so
    # the gap is detectable if nx ever changes behaviour.
    f_mod = fnx.modularity(fg, bad)
    assert isinstance(f_mod, float)


# ---------------------------------------------------------------------------
# Seed determinism
# ---------------------------------------------------------------------------


def test_louvain_seed_reproducibility_within_fnx():
    """Same seed → same partition on fnx (catches seed-threading regressions)."""
    fg, _ = _barbell()
    a = _normalize(fnx.louvain_communities(fg, seed=42))
    b = _normalize(fnx.louvain_communities(fg, seed=42))
    assert a == b, "louvain seed=42 produced different partitions on reruns"


def test_kernighan_lin_seed_reproducibility_within_fnx():
    fg, _ = _barbell()
    a = fnx.kernighan_lin_bisection(fg, seed=42)
    b = fnx.kernighan_lin_bisection(fg, seed=42)
    # Canonicalize by sorting each half.
    def _canon(pair):
        return tuple(sorted(tuple(sorted(h)) for h in pair))
    assert _canon(a) == _canon(b)
