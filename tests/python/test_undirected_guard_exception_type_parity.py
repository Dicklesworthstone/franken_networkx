"""Parity for @not_implemented_for('undirected') guards.

Bead br-r37-c1-n7rgh. Audit of all 53 nx functions decorated with
``@not_implemented_for('undirected')`` found 7 functions that
raised the WRONG exception type on undirected input — usually
``NetworkXError`` (parent class) or ``AttributeError`` (when the
fnx wrapper fell through to a directed-only graph method).

Drop-in code that does ``pytest.raises(NetworkXNotImplemented)``
wouldn't trigger because NetworkXNotImplemented is NOT a subclass
of NetworkXError; both descend from NetworkXException
independently.

Affected functions (all now raise NetworkXNotImplemented):
- directed_edge_swap
- in_degree_centrality (MultiGraph specifically)
- out_degree_centrality (MultiGraph specifically)
- moral_graph
- reverse_view
- triad_type
- triadic_census
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


UNDIR_GUARDED_FNS = [
    "directed_edge_swap",
    "in_degree_centrality",
    "out_degree_centrality",
    "moral_graph",
    "reverse_view",
    "triad_type",
    "triadic_census",
]


@needs_nx
@pytest.mark.parametrize("fn_name", UNDIR_GUARDED_FNS)
@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
def test_undirected_input_raises_not_implemented(fn_name, cls_name):
    G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
    GX = getattr(nx, cls_name)([(1, 2), (2, 3)])
    f_fn = getattr(fnx, fn_name)
    n_fn = getattr(nx, fn_name)
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for undirected type$",
    ):
        f_fn(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for undirected type$",
    ):
        n_fn(GX)


@needs_nx
@pytest.mark.parametrize("fn_name", UNDIR_GUARDED_FNS)
def test_undirected_caught_by_nx_class(fn_name):
    """Drop-in: each fnx-raised NetworkXNotImplemented must be
    catchable via ``except nx.NetworkXNotImplemented``."""
    G = fnx.Graph([(1, 2)])
    try:
        getattr(fnx, fn_name)(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail(
        f"fnx.{fn_name} should raise NetworkXNotImplemented on undirected input"
    )


@needs_nx
def test_directed_edge_swap_directed_input_size_check():
    """Pre-existing nx contract: <4 nodes raises NetworkXError
    (NOT NetworkXNotImplemented). Verify both libraries agree on
    the post-type-guard size check."""
    G = fnx.DiGraph([(1, 2)])
    GX = nx.DiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXError, match=r"fewer than four nodes"):
        fnx.directed_edge_swap(G)
    with pytest.raises(nx.NetworkXError, match=r"fewer than four nodes"):
        nx.directed_edge_swap(GX)


# ---------------------------------------------------------------------------
# Regression — directed inputs continue to work
# ---------------------------------------------------------------------------

@needs_nx
def test_in_degree_centrality_directed_unchanged():
    G = fnx.DiGraph([(1, 2), (2, 3), (3, 1)])
    GX = nx.DiGraph([(1, 2), (2, 3), (3, 1)])
    assert fnx.in_degree_centrality(G) == nx.in_degree_centrality(GX)


@needs_nx
def test_out_degree_centrality_directed_unchanged():
    G = fnx.DiGraph([(1, 2), (2, 3), (3, 1)])
    GX = nx.DiGraph([(1, 2), (2, 3), (3, 1)])
    assert fnx.out_degree_centrality(G) == nx.out_degree_centrality(GX)


@needs_nx
def test_moral_graph_directed_unchanged():
    G = fnx.DiGraph([(0, 2), (1, 2), (2, 3)])
    GX = nx.DiGraph([(0, 2), (1, 2), (2, 3)])
    f = sorted(fnx.moral_graph(G).edges())
    n = sorted(nx.moral_graph(GX).edges())
    assert f == n


@needs_nx
def test_reverse_view_directed_unchanged():
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    assert sorted(fnx.reverse_view(G).edges()) == sorted(nx.reverse_view(GX).edges())


@needs_nx
def test_triadic_census_directed_unchanged():
    G = fnx.DiGraph([(1, 2), (2, 3), (3, 1)])
    GX = nx.DiGraph([(1, 2), (2, 3), (3, 1)])
    assert fnx.triadic_census(G) == nx.triadic_census(GX)
