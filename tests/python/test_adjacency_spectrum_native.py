"""br-r37-c1-04z53.9112: undirected adjacency_spectrum routes through the
safe-Rust symmetric eigensolver (no C LAPACK) and matches nx's
``scipy.linalg.eigvals`` on dtype (complex128) + sorted values.

Solver order is unstable (LAPACK/QR Schur deflation order is not portable),
so parity is asserted on sorted values, mirroring the project's existing
``test_adjacency_spectrum_returns_complex_match_nx`` contract.
"""

import numpy as np
import networkx as nx
import franken_networkx as fnx


def _sorted_match(fr, nr, atol=1e-9):
    return np.allclose(np.sort_complex(fr), np.sort_complex(nr), atol=atol)


def test_undirected_native_route_matches_nx():
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
        assert _sorted_match(fr, nr)


def test_weighted_default_weight_matches_nx():
    edges = [(0, 1, 2.5), (1, 2, 0.7), (2, 3, 3.1), (3, 0, 1.2), (0, 2, 4.0)]
    Gf, Gn = fnx.Graph(), nx.Graph()
    for u, v, w in edges:
        Gf.add_edge(u, v, weight=w)
        Gn.add_edge(u, v, weight=w)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    assert fr.dtype == np.complex128
    assert _sorted_match(fr, nr)


def test_unweighted_star_closed_form_matches_nx_sorted_values():
    Gf = fnx.star_graph(31)
    Gn = nx.star_graph(31)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    expected = np.zeros(32, dtype=np.complex128)
    expected[0] = complex(-np.sqrt(31), 0.0)
    expected[-1] = complex(np.sqrt(31), 0.0)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert np.allclose(np.sort_complex(fr), expected)


def test_directed_fallback_matches_nx():
    e = [(0, 1), (1, 2), (2, 0), (0, 3), (3, 1)]
    fr = fnx.adjacency_spectrum(fnx.DiGraph(e))
    nr = nx.adjacency_spectrum(nx.DiGraph(e))
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)


def test_empty_graph_raises_like_nx():
    import pytest

    with pytest.raises(nx.NetworkXError):
        fnx.adjacency_spectrum(fnx.Graph())
