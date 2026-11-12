"""br-r37-c1-y77dc: regression — centrality family accepts nx graph args
via boundary coercion. Sibling of br-r37-c1-phy2p (shortest-path).

Affected: pagerank, eigenvector_centrality, katz_centrality,
betweenness_centrality, closeness_centrality.
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


@needs_nx
def test_pagerank_accepts_nx_graph():
    ng = nx.path_graph(5)
    result = fnx.pagerank(ng)
    assert isinstance(result, dict) and len(result) == 5
    assert abs(sum(result.values()) - 1.0) < 1e-6


@needs_nx
def test_eigenvector_centrality_accepts_nx_graph():
    ng = nx.cycle_graph(5)
    result = fnx.eigenvector_centrality(ng)
    assert isinstance(result, dict) and len(result) == 5


@needs_nx
def test_katz_centrality_accepts_nx_graph():
    ng = nx.path_graph(5)
    result = fnx.katz_centrality(ng)
    assert isinstance(result, dict) and len(result) == 5


@needs_nx
def test_betweenness_centrality_accepts_nx_graph():
    ng = nx.path_graph(5)
    result = fnx.betweenness_centrality(ng)
    assert isinstance(result, dict) and len(result) == 5


@needs_nx
def test_closeness_centrality_accepts_nx_graph():
    ng = nx.path_graph(5)
    result = fnx.closeness_centrality(ng)
    assert isinstance(result, dict) and len(result) == 5


@needs_nx
def test_centrality_value_parity_nx_vs_fnx():
    """Numerical results must match between (nx_arg) and (fnx_arg)."""
    ng = nx.path_graph(5)
    fg = fnx.path_graph(5)
    pr_n = fnx.pagerank(ng)
    pr_f = fnx.pagerank(fg)
    for k in pr_n:
        assert abs(pr_n[k] - pr_f[k]) < 1e-9


@needs_nx
def test_centrality_no_regression_fnx_input():
    """Same-type call still works."""
    fg = fnx.path_graph(5)
    assert isinstance(fnx.pagerank(fg), dict)
    assert isinstance(fnx.eigenvector_centrality(fg), dict)
    assert isinstance(fnx.betweenness_centrality(fg), dict)
