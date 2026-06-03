"""Parity for normalized_laplacian on graphs with isolated (degree-0) nodes.

Bead br-r37-c1-mxe39.

The normalized Laplacian is ``N = D^{-1/2} (D - A) D^{-1/2}``. fnx computed the
algebraically-different ``I - D^{-1/2} A D^{-1/2}`` with a *constant* identity,
so an isolated node's diagonal came out as 1 instead of nx's 0 (the
``D^{-1/2} D D^{-1/2}`` term vanishes when 1/sqrt(0) is clamped to 0). The two
agree for every node with degree > 0, but diverge whenever the graph has an
isolated node — e.g. a disconnected graph, where a k-component graph must yield
k zero eigenvalues, not k-1 zeros plus a spurious 1.0.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_isolated_node_diagonal_is_zero():
    f, n = fnx.Graph(), nx.Graph()
    for g in (f, n):
        g.add_edge(0, 1)
        g.add_node(2)  # isolated
    fm = fnx.normalized_laplacian_matrix(f).toarray()
    nm = nx.normalized_laplacian_matrix(n).toarray()
    assert np.allclose(fm, nm, atol=1e-12)
    # the isolated node's diagonal must be 0 (regression guard)
    assert fm[2, 2] == pytest.approx(0.0)


@needs_nx
def test_default_weight_nodelist_self_loop_and_isolate_match():
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for graph in (fnx_graph, nx_graph):
        graph.add_edge("a", "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_node("z")

    nodelist = ["z", "c", "a", "b"]
    fm = fnx.normalized_laplacian_matrix(fnx_graph, nodelist=nodelist).toarray()
    nm = nx.normalized_laplacian_matrix(nx_graph, nodelist=nodelist).toarray()
    assert np.allclose(fm, nm, atol=1e-12)


@needs_nx
def test_present_default_weight_attr_uses_weighted_semantics():
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for graph in (fnx_graph, nx_graph):
        graph.add_edge("a", "b", weight=3.5)
        graph.add_edge("b", "c")

    fm = fnx.normalized_laplacian_matrix(fnx_graph).toarray()
    nm = nx.normalized_laplacian_matrix(nx_graph).toarray()
    assert np.allclose(fm, nm, atol=1e-12)


@needs_nx
def test_disconnected_spectrum_has_k_zeros():
    f, n = fnx.Graph(), nx.Graph()
    for g in (f, n):
        g.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
        g.add_node(9)  # second component (isolated)
    fs = np.sort(fnx.normalized_laplacian_spectrum(f))
    ns = np.sort(nx.normalized_laplacian_spectrum(n))
    assert np.allclose(fs, ns, atol=1e-9)
    # 2 connected components -> exactly 2 (near-)zero eigenvalues
    assert int(np.sum(np.isclose(ns, 0.0, atol=1e-9))) == 2


@needs_nx
@pytest.mark.parametrize("seed", list(range(40)))
def test_random_matrix_and_spectrum_match(seed):
    rng = random.Random(seed * 47 + 11)
    n = rng.randint(1, 12)
    ng = nx.gnp_random_graph(n, rng.choice([0.0, 0.15, 0.3, 0.5]), seed=seed)
    for u in list(ng.nodes()):
        if rng.random() < 0.2:
            ng.add_edge(u, u)
    fg = fnx.Graph()
    for u in ng.nodes():
        fg.add_node(u)
    for u, v in ng.edges():
        fg.add_edge(u, v)
    nm = nx.normalized_laplacian_matrix(ng).toarray()
    fm = fnx.normalized_laplacian_matrix(fg).toarray()
    assert nm.shape == fm.shape
    assert np.allclose(nm, fm, atol=1e-9)
    ns = np.sort(nx.normalized_laplacian_spectrum(ng))
    fs = np.sort(fnx.normalized_laplacian_spectrum(fg))
    assert len(ns) == len(fs)
    assert np.allclose(ns, fs, atol=1e-7)


@needs_nx
@pytest.mark.parametrize("seed", list(range(15)))
def test_weighted_isolated_match(seed):
    rng = random.Random(seed * 13 + 3)
    n = rng.randint(2, 9)
    ng = nx.Graph()
    fg = fnx.Graph()
    for u in range(n):
        ng.add_node(u)
        fg.add_node(u)
    for _ in range(rng.randint(0, n)):
        u, v = rng.sample(range(n), 2)
        w = float(rng.choice([0.5, 1.0, 2.0, 3.0]))
        ng.add_edge(u, v, weight=w)
        fg.add_edge(u, v, weight=w)
    nm = nx.normalized_laplacian_matrix(ng).toarray()
    fm = fnx.normalized_laplacian_matrix(fg).toarray()
    assert np.allclose(nm, fm, atol=1e-9)
