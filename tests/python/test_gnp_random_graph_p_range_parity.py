"""Parity for gnp_random_graph (and erdos_renyi_graph alias) with
``p`` outside [0, 1].

Bead br-r37-c1-lsdek.

nx silently accepts any ``p``::

    p >= 1   → complete graph (every possible edge present)
    p <= 0   → empty graph (no edges)

The Rust ``_rust_gnp_random_graph`` binding validates p strictly
and raises a ``ValueError`` whose message leaks Rust internals::

    ValueError: FailClosed { operation: "gnp_random_graph",
                             reason: "p=1.5 is outside [0.0, 1.0]" }

Both the class and the message format break drop-in code.

Fix: gate the Rust path on ``0.0 <= p <= 1.0`` so out-of-range
values fall through to the existing Python fallback (which already
handles the p>=1 / p<=0 corner cases correctly).
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
# p > 1 → complete graph
# ---------------------------------------------------------------------------

@needs_nx
def test_gnp_random_graph_p_above_one_returns_complete():
    f = fnx.gnp_random_graph(5, 1.5, seed=42)
    n = nx.gnp_random_graph(5, 1.5, seed=42)
    assert sorted(f.edges()) == sorted(n.edges())
    # Sanity: K_5 has C(5, 2) = 10 edges
    assert f.number_of_edges() == 10


@needs_nx
def test_erdos_renyi_alias_p_above_one_returns_complete():
    f = fnx.erdos_renyi_graph(5, 1.5, seed=42)
    n = nx.erdos_renyi_graph(5, 1.5, seed=42)
    assert sorted(f.edges()) == sorted(n.edges())


@needs_nx
def test_gnp_random_graph_p_exactly_one_returns_complete():
    f = fnx.gnp_random_graph(5, 1, seed=42)
    n = nx.gnp_random_graph(5, 1, seed=42)
    assert sorted(f.edges()) == sorted(n.edges())


# ---------------------------------------------------------------------------
# p < 0 → empty graph
# ---------------------------------------------------------------------------

@needs_nx
def test_gnp_random_graph_p_below_zero_returns_empty():
    f = fnx.gnp_random_graph(5, -0.5, seed=42)
    n = nx.gnp_random_graph(5, -0.5, seed=42)
    assert list(f.edges()) == []
    assert list(n.edges()) == []
    assert f.number_of_nodes() == n.number_of_nodes() == 5


@needs_nx
def test_erdos_renyi_alias_p_below_zero_returns_empty():
    f = fnx.erdos_renyi_graph(5, -1, seed=42)
    n = nx.erdos_renyi_graph(5, -1, seed=42)
    assert list(f.edges()) == list(n.edges()) == []


@needs_nx
def test_gnp_random_graph_p_exactly_zero_returns_empty():
    f = fnx.gnp_random_graph(5, 0, seed=42)
    n = nx.gnp_random_graph(5, 0, seed=42)
    assert list(f.edges()) == list(n.edges()) == []


# ---------------------------------------------------------------------------
# Binomial alias and dense_gnm sanity
# ---------------------------------------------------------------------------

@needs_nx
def test_binomial_graph_alias_p_above_one():
    f = fnx.binomial_graph(5, 2, seed=42)
    n = nx.binomial_graph(5, 2, seed=42)
    assert sorted(f.edges()) == sorted(n.edges())


# ---------------------------------------------------------------------------
# Regressions — in-range p still goes through Rust path
# ---------------------------------------------------------------------------

@needs_nx
def test_gnp_random_graph_in_range_p_unchanged():
    f = fnx.gnp_random_graph(10, 0.3, seed=42)
    n = nx.gnp_random_graph(10, 0.3, seed=42)
    assert f.number_of_nodes() == n.number_of_nodes() == 10


@needs_nx
def test_gnp_random_graph_negative_n_still_raises_networkx_error():
    """Pre-existing br-gnpvalid invariant: n<0 raises NetworkXError."""
    with pytest.raises(fnx.NetworkXError, match=r"Negative number of nodes not valid"):
        fnx.gnp_random_graph(-1, 0.5, seed=42)
    with pytest.raises(nx.NetworkXError, match=r"Negative number of nodes not valid"):
        nx.gnp_random_graph(-1, 0.5, seed=42)
