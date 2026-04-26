"""Parity coverage for random-sequence utilities.

Bead br-r37-c1-m4msi: powerlaw_sequence, zipf_rv, cumulative_distribution,
is_valid_tree_degree_sequence. Claimed missing; actually all four are
exposed at the top level of franken_networkx and (for the three that
exist in networkx.utils) match nx output bit-for-bit when seeded.
``is_valid_tree_degree_sequence`` is a fnx-only helper that validates
a degree sequence describes a tree (the upstream PR proposed a similar
helper in networkx; not yet merged).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# powerlaw_sequence
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("seed", [0, 1, 42, 12345])
@pytest.mark.parametrize("n", [1, 5, 20, 100])
@pytest.mark.parametrize("exponent", [1.5, 2.0, 3.0])
def test_powerlaw_sequence_matches_networkx(seed, n, exponent):
    actual = fnx.powerlaw_sequence(n, exponent=exponent, seed=seed)
    expected = nx.utils.powerlaw_sequence(n, exponent=exponent, seed=seed)
    assert actual == expected
    assert len(actual) == n
    assert all(x > 0 for x in actual)


# ---------------------------------------------------------------------------
# zipf_rv
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("seed", [0, 1, 42])
@pytest.mark.parametrize("alpha", [1.5, 2.0, 3.5])
@pytest.mark.parametrize("xmin", [1, 5])
def test_zipf_rv_matches_networkx(seed, alpha, xmin):
    actual = fnx.zipf_rv(alpha, xmin=xmin, seed=seed)
    expected = nx.utils.zipf_rv(alpha, xmin=xmin, seed=seed)
    assert actual == expected
    assert isinstance(actual, int)
    assert actual >= xmin


# ---------------------------------------------------------------------------
# cumulative_distribution
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "distribution",
    [
        [0.1, 0.3, 0.6],
        [0.25, 0.25, 0.25, 0.25],
        [1.0],
        [0.0, 1.0, 0.0],
        [3, 1, 6],  # unnormalised int counts also accepted
    ],
)
def test_cumulative_distribution_matches_networkx(distribution):
    actual = fnx.cumulative_distribution(distribution)
    expected = nx.utils.cumulative_distribution(distribution)
    assert actual == expected
    # cdf starts at 0; nx normalises by sum so it ends at 1.0
    assert actual[0] == 0
    assert actual[-1] == pytest.approx(1.0)
    assert len(actual) == len(distribution) + 1


# ---------------------------------------------------------------------------
# discrete_sequence  (lives on fnx.utils, not the top level — same as nx)
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("seed", [0, 1, 42])
@pytest.mark.parametrize("n", [1, 5, 20])
def test_discrete_sequence_matches_networkx(seed, n):
    distribution = [0.1, 0.2, 0.3, 0.4]
    actual = fnx.utils.discrete_sequence(n, distribution=distribution, seed=seed)
    expected = nx.utils.discrete_sequence(n, distribution=distribution, seed=seed)
    assert actual == expected
    assert len(actual) == n


# ---------------------------------------------------------------------------
# is_valid_tree_degree_sequence  (fnx-only, no nx counterpart yet)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("sequence", "valid"),
    [
        ([1, 1], True),               # K2
        ([1, 2, 1], True),            # path P3
        ([3, 1, 1, 1], True),         # star S3
        ([2, 2, 2], False),           # cycle, not a tree
        ([3, 3, 1, 1, 1, 1], True),   # legitimate tree degree seq
        ([4, 1, 1, 1], False),        # sum != 2*(n-1)
        ([], False),                  # empty
        ([0], True),                  # single isolated node — degenerate "tree"
    ],
)
def test_is_valid_tree_degree_sequence(sequence, valid):
    result = fnx.is_valid_tree_degree_sequence(sequence)
    # fnx returns (bool, reason) tuple — first element is the bool.
    if isinstance(result, tuple):
        assert result[0] == valid, f"seq={sequence}: got {result}, expected valid={valid}"
    else:
        assert result == valid


def test_is_valid_tree_degree_sequence_returns_tuple_with_reason():
    """The fnx helper returns ``(valid, reason)`` so callers can surface
    a useful error message. Lock that contract."""
    valid, reason = fnx.is_valid_tree_degree_sequence([2, 2, 2])
    assert valid is False
    assert isinstance(reason, str)
    assert reason  # non-empty
