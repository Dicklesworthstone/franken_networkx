"""Parity for @not_implemented_for('multigraph') guards across fnx.

Bead br-r37-c1-tqimg. An audit revealed 20+ nx functions decorated
with ``@not_implemented_for('multigraph')`` (sometimes also with
``@not_implemented_for('directed')`` or ``@not_implemented_for(
'undirected')``) that fnx silently accepted on multigraph input.
Each fnx wrapper now raises NetworkXNotImplemented with nx's exact
wording. The Rust fast paths remain the default for non-multigraph
inputs.

This test file covers a focused subset that have Python wrappers in
``__init__.py`` and were pinned in this commit. Some link-prediction
helpers (cn_soundarajan_hopcroft, ra_index_soundarajan_hopcroft,
within_inter_cluster) and Rust-direct re-exports (maximal_matching,
tree_broadcast_center, tree_broadcast_time) are out of scope here.
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
# Functions that should raise on BOTH MultiGraph and MultiDiGraph
# (nx.@not_implemented_for('multigraph') is type-agnostic).
# ---------------------------------------------------------------------------

MG_ONLY_FNS = [
    "eigenvector_centrality",
    "katz_centrality",
    "communicability",
    "communicability_betweenness_centrality",
    "girth",
    "bethe_hessian_matrix",
    "is_at_free",
    "hyper_wiener_index",
    "intersection_array",
    "mycielskian",
    "random_reference",
    "find_asteroidal_triple",
    "is_perfect_graph",
    "stoer_wagner",
]


@needs_nx
@pytest.mark.parametrize("fn_name", MG_ONLY_FNS)
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_input_raises_not_implemented(fn_name, cls_name):
    G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
    GX = getattr(nx, cls_name)([(1, 2), (2, 3)])
    f_fn = getattr(fnx, fn_name)
    n_fn = getattr(nx, fn_name)
    with pytest.raises(fnx.NetworkXNotImplemented):
        f_fn(G)
    with pytest.raises(nx.NetworkXNotImplemented):
        n_fn(GX)


@needs_nx
@pytest.mark.parametrize("fn_name", ["eigenvector_centrality", "katz_centrality", "girth", "is_at_free"])
def test_multigraph_message_matches_nx(fn_name):
    """Cross-check that the fnx exception message exactly matches nx's
    wording for one canonical case (MultiGraph)."""
    G = fnx.MultiGraph([(1, 2)])
    GX = nx.MultiGraph([(1, 2)])
    try:
        getattr(fnx, fn_name)(G)
    except fnx.NetworkXNotImplemented as e:
        f_msg = str(e)
    try:
        getattr(nx, fn_name)(GX)
    except nx.NetworkXNotImplemented as e:
        n_msg = str(e)
    assert f_msg == n_msg, (fn_name, f_msg, n_msg)


# ---------------------------------------------------------------------------
# directed_modularity_matrix is @not_implemented_for('undirected', 'multigraph')
# ---------------------------------------------------------------------------

@needs_nx
def test_directed_modularity_matrix_rejects_multidigraph():
    G = fnx.MultiDiGraph([(1, 2)])
    GX = nx.MultiDiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.directed_modularity_matrix(G)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.directed_modularity_matrix(GX)


@needs_nx
def test_directed_modularity_matrix_rejects_undirected():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented, match=r"undirected"):
        fnx.directed_modularity_matrix(G)
    with pytest.raises(nx.NetworkXNotImplemented, match=r"undirected"):
        nx.directed_modularity_matrix(GX)


# ---------------------------------------------------------------------------
# Cross-class catching
# ---------------------------------------------------------------------------

@needs_nx
def test_multigraph_guard_caught_by_nx_class():
    G = fnx.MultiGraph([(1, 2)])
    try:
        fnx.eigenvector_centrality(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail("fnx.eigenvector_centrality should raise on MultiGraph")


# ---------------------------------------------------------------------------
# Regression guards — simple graphs still work
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "fn_name",
    ["eigenvector_centrality", "katz_centrality", "girth", "communicability",
     "is_at_free", "is_perfect_graph"],
)
def test_simple_graph_unchanged(fn_name):
    """The Rust / Python fast path remains the default for non-MG
    inputs."""
    G = fnx.cycle_graph(5)
    GX = nx.cycle_graph(5)
    f_fn = getattr(fnx, fn_name)
    n_fn = getattr(nx, fn_name)
    f = f_fn(G)
    n = n_fn(GX)
    if isinstance(f, dict):
        assert set(f.keys()) == set(n.keys())
    else:
        assert f == n
