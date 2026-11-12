"""Parity for ``spectral_ordering``.

Bead br-r37-c1-xiqgr. The local fiedler_vector + argsort path picked
the eigenvector with whichever sign scipy's eigensolver returned,
which differed from nx's choice on many graphs (giving e.g.
[4,3,2,1,0] instead of nx's [0,1,2,3,4] on a path graph). The
Fiedler vector is sign-ambiguous so both are mathematically valid,
but drop-in code comparing the ordering to nx's reference broke.

Fix delegates to nx so the chosen sign + tie-break match exactly.

Note: the underlying iterative tracemin/lanczos solver in nx still
has run-to-run nondeterminism if no seed is supplied, so these tests
all pin a seed explicitly.
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


def _make_graph(lib, edges):
    g = lib.Graph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
@pytest.mark.parametrize("seed", [1, 42, 100])
def test_repro_graph_matches_nx(seed):
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.spectral_ordering(g, seed=seed) == nx.spectral_ordering(gx, seed=seed)


@needs_nx
@pytest.mark.parametrize("seed", [1, 42, 100])
def test_path_graph_matches_nx(seed):
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert fnx.spectral_ordering(g, seed=seed) == nx.spectral_ordering(gx, seed=seed)


@needs_nx
@pytest.mark.parametrize("seed", [1, 42])
def test_cycle_graph_matches_nx(seed):
    g = fnx.cycle_graph(6)
    gx = nx.cycle_graph(6)
    assert fnx.spectral_ordering(g, seed=seed) == nx.spectral_ordering(gx, seed=seed)


@needs_nx
@pytest.mark.parametrize("seed", [1, 42])
def test_complete_graph_matches_nx(seed):
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    assert fnx.spectral_ordering(g, seed=seed) == nx.spectral_ordering(gx, seed=seed)


@needs_nx
def test_normalized_laplacian_matches_nx():
    g = fnx.path_graph(6)
    gx = nx.path_graph(6)
    assert fnx.spectral_ordering(g, normalized=True, seed=42) == nx.spectral_ordering(
        gx, normalized=True, seed=42
    )


@needs_nx
def test_weighted_graph_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in [("a", "b", 2), ("b", "c", 1), ("c", "d", 3), ("a", "d", 1)]:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    assert fnx.spectral_ordering(g, seed=42) == nx.spectral_ordering(gx, seed=42)


@needs_nx
def test_custom_weight_attr_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in [("a", "b", 2), ("b", "c", 1), ("c", "d", 3), ("a", "d", 1)]:
        g.add_edge(u, v, capacity=w)
        gx.add_edge(u, v, capacity=w)
    assert fnx.spectral_ordering(g, weight="capacity", seed=42) == nx.spectral_ordering(
        gx, weight="capacity", seed=42
    )


@needs_nx
def test_method_tracemin_lu_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = fnx.spectral_ordering(g, method="tracemin_lu", seed=42)
    n = nx.spectral_ordering(gx, method="tracemin_lu", seed=42)
    assert f == n


@needs_nx
def test_repeatable_within_same_seed():
    """Same seed -> same output across repeated calls (regression
    against the earlier non-deterministic behaviour)."""
    g = _make_graph(fnx, [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")])
    runs = [tuple(fnx.spectral_ordering(g, seed=42)) for _ in range(3)]
    assert all(r == runs[0] for r in runs)


@needs_nx
def test_wsy5c_graph_edge_walk_fast_path_and_mid_walk_mutation_parity():
    """br-r37-c1-wsy5c: GraphEdgeWalk index fast path preserves exact order,
    self-loops, bool/int display keys, and mid-walk mutation semantics."""
    g_nx = nx.gnm_random_graph(40, 120, seed=7)
    g_nx.add_edge(5, 5)
    g_fnx = fnx.Graph(g_nx)
    assert list(g_fnx.edges) == list(g_nx.edges)
    assert set(g_fnx.edges) == set(g_nx.edges)

    # Edge added to a future row during iteration is visible when that row is reached.
    g_nx2 = nx.path_graph(6)
    g_fnx2 = fnx.path_graph(6)
    seen_nx, seen_fnx = [], []
    for u, v in g_nx2.edges:
        seen_nx.append((u, v))
        if len(seen_nx) == 1:
            g_nx2.add_edge(3, 5)
    for u, v in g_fnx2.edges:
        seen_fnx.append((u, v))
        if len(seen_fnx) == 1:
            g_fnx2.add_edge(3, 5)
    assert seen_fnx == seen_nx

    # Node added mid-walk triggers RuntimeError on next outer dict advance.
    g_fnx3 = fnx.path_graph(5)
    it = iter(g_fnx3.edges)
    assert next(it) == (0, 1)
    g_fnx3.add_node(99)
    with pytest.raises(RuntimeError, match="dictionary changed size during iteration"):
        list(it)


@needs_nx
def test_wsy5c_set_edge_batch_and_intersection_parity():
    """br-r37-c1-wsy5c: add_edges_from(set) and intersection(G, H) batch natively
    and preserve exact node/edge sets."""
    g_nx = nx.gnm_random_graph(120, 400, seed=11)
    h_nx = nx.gnm_random_graph(120, 400, seed=12)
    g_fnx = fnx.Graph(g_nx)
    h_fnx = fnx.Graph(h_nx)

    inter_nx = nx.intersection(g_nx, h_nx)
    inter_fnx = fnx.intersection(g_fnx, h_fnx)
    assert list(inter_fnx.nodes) == list(inter_nx.nodes)
    assert {tuple(sorted(e)) for e in inter_fnx.edges} == {
        tuple(sorted(e)) for e in inter_nx.edges
    }

    # Direct set ebunch on both existing-int-prefix and fresh string-node graphs.
    s_edges = {(0, 10), (1, 11), (2, 12), (3, 13), (4, 14), (5, 15), (6, 16), (7, 17)}
    r_fnx = fnx.Graph()
    r_fnx.add_nodes_from(range(20))
    r_fnx.add_edges_from(s_edges)
    assert {tuple(sorted(e)) for e in r_fnx.edges} == s_edges

