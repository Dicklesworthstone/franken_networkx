"""br-r37-c1-04z53.9113: adjacency_spectrum must preserve NetworkX's raw
``scipy.linalg.eigvals`` order.

The safe-Rust symmetric eigensolver is valid for sorted spectra in other public
APIs, but it is not a public ``adjacency_spectrum`` replacement until it also
proves SciPy/LAPACK raw output order.
"""

import numpy as np
import networkx as nx
import franken_networkx as fnx


def _raw_match(fr, nr, atol=1e-9):
    return np.allclose(fr, nr, atol=atol)


def test_undirected_raw_order_matches_nx():
    cases = [
        lambda M: M.path_graph(5),
        lambda M: M.cycle_graph(7),
        lambda M: M.complete_graph(6),
        lambda M: M.star_graph(10),
        lambda M: M.barabasi_albert_graph(96, 3, seed=1),
        lambda M: M.grid_2d_graph(5, 4),
    ]
    for b in cases:
        fr = fnx.adjacency_spectrum(b(fnx))
        nr = nx.adjacency_spectrum(b(nx))
        assert fr.dtype == nr.dtype == np.complex128
        assert _raw_match(fr, nr)


def test_weighted_default_weight_matches_nx():
    edges = [(0, 1, 2.5), (1, 2, 0.7), (2, 3, 3.1), (3, 0, 1.2), (0, 2, 4.0)]
    Gf, Gn = fnx.Graph(), nx.Graph()
    for u, v, w in edges:
        Gf.add_edge(u, v, weight=w)
        Gn.add_edge(u, v, weight=w)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    assert fr.dtype == nr.dtype == np.complex128
    assert _raw_match(fr, nr)


def test_directed_fallback_matches_nx():
    e = [(0, 1), (1, 2), (2, 0), (0, 3), (3, 1)]
    fr = fnx.adjacency_spectrum(fnx.DiGraph(e))
    nr = nx.adjacency_spectrum(nx.DiGraph(e))
    assert fr.dtype == nr.dtype == np.complex128
    assert _raw_match(fr, nr)


def test_star_center_first_closed_form_matches_nx_raw_order():
    Gf = fnx.star_graph(31)
    Gn = nx.star_graph(31)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    assert fr.dtype == nr.dtype == np.complex128
    assert _raw_match(fr, nr)
    assert fr[0] == complex(np.sqrt(31), 0.0)
    assert fr[1] == complex(-np.sqrt(31), 0.0)
    assert np.count_nonzero(fr[2:]) == 0


def test_star_center_not_first_keeps_scipy_raw_order():
    Gf, Gn = fnx.Graph(), nx.Graph()
    nodes = [f"leaf-{i}" for i in range(7)] + ["center"]
    Gf.add_nodes_from(nodes)
    Gn.add_nodes_from(nodes)
    for leaf in nodes[:-1]:
        Gf.add_edge("center", leaf)
        Gn.add_edge("center", leaf)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    assert fr.dtype == nr.dtype == np.complex128
    assert _raw_match(fr, nr)


def test_weighted_star_fallback_matches_nx_raw_order():
    Gf, Gn = fnx.Graph(), nx.Graph()
    for leaf in range(1, 8):
        Gf.add_edge(0, leaf, weight=2.0 if leaf == 1 else 1.0)
        Gn.add_edge(0, leaf, weight=2.0 if leaf == 1 else 1.0)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    assert fr.dtype == nr.dtype == np.complex128
    assert _raw_match(fr, nr)


def test_empty_graph_raises_like_nx():
    import pytest

    with pytest.raises(nx.NetworkXError):
        fnx.adjacency_spectrum(fnx.Graph())
