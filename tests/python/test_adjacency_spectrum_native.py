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


def test_unweighted_complete_closed_form_matches_nx_sorted_values():
    Gf = fnx.complete_graph(31)
    Gn = nx.complete_graph(31)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    expected = np.empty(31, dtype=np.complex128)
    expected[:-1] = complex(-1.0, 0.0)
    expected[-1] = complex(30.0, 0.0)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert np.allclose(np.sort_complex(fr), expected)


def test_unweighted_edgeless_closed_form_matches_nx_sorted_values():
    Gf = fnx.empty_graph(31)
    Gn = nx.empty_graph(31)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    expected = np.zeros(31, dtype=np.complex128)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert np.allclose(np.sort_complex(fr), expected)


def test_unweighted_cycle_closed_form_matches_nx_sorted_values():
    Gf = fnx.cycle_graph(31)
    Gn = nx.cycle_graph(31)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    expected = 2.0 * np.cos((2.0 * np.pi / 31.0) * np.arange(31, dtype=np.float64))
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert np.allclose(np.sort_complex(fr), np.sort(expected).astype(np.complex128))


def test_weighted_cycle_graph_stays_on_weighted_route():
    Gf = fnx.cycle_graph(9)
    Gn = nx.cycle_graph(9)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    unweighted = 2.0 * np.cos((2.0 * np.pi / 9.0) * np.arange(9, dtype=np.float64))
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert not np.allclose(np.sort_complex(fr), np.sort(unweighted).astype(np.complex128))


def test_unweighted_complete_bipartite_closed_form_matches_nx_sorted_values():
    Gf = fnx.complete_bipartite_graph(5, 7)
    Gn = nx.complete_bipartite_graph(5, 7)
    assert vars(Gf)["_fnx_complete_bipartite_shape"] == (
        Gf.nodes_seq,
        Gf.edges_seq,
        5,
        7,
    )
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    expected = np.zeros(12, dtype=np.complex128)
    root = np.sqrt(35.0)
    expected[0] = complex(-root, 0.0)
    expected[-1] = complex(root, 0.0)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert np.allclose(np.sort_complex(fr), expected)


def test_weighted_complete_bipartite_graph_stays_on_weighted_route():
    Gf = fnx.complete_bipartite_graph(4, 6)
    Gn = nx.complete_bipartite_graph(4, 6)
    Gf[0][4]["weight"] = 2.5
    Gn[0][4]["weight"] = 2.5
    assert vars(Gf)["_fnx_complete_bipartite_shape"] is not None
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    unweighted = np.zeros(10, dtype=np.complex128)
    root = np.sqrt(24.0)
    unweighted[0] = complex(-root, 0.0)
    unweighted[-1] = complex(root, 0.0)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert not np.allclose(np.sort_complex(fr), unweighted)


def test_complete_bipartite_adjacency_rejects_count_preserving_rewire():
    Gf = fnx.complete_bipartite_graph(4, 6)
    Gn = nx.complete_bipartite_graph(4, 6)
    original_shape = vars(Gf)["_fnx_complete_bipartite_shape"]
    Gf.remove_edge(0, 4)
    Gn.remove_edge(0, 4)
    Gf.add_edge(0, 1)
    Gn.add_edge(0, 1)
    assert vars(Gf)["_fnx_complete_bipartite_shape"] == original_shape
    assert Gf.edges_seq != original_shape[1]
    assert fnx._complete_bipartite_adjacency_spectrum_sorted_value_safe(Gf, "weight") is None
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)


def test_weighted_complete_graph_stays_on_weighted_route():
    Gf = fnx.complete_graph(7)
    Gn = nx.complete_graph(7)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    unweighted = np.empty(7, dtype=np.complex128)
    unweighted[:-1] = complex(-1.0, 0.0)
    unweighted[-1] = complex(6.0, 0.0)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert not np.allclose(np.sort_complex(fr), unweighted)


def test_unweighted_path_closed_form_matches_nx_sorted_values():
    Gf = fnx.path_graph(31)
    Gn = nx.path_graph(31)
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    expected = 2.0 * np.cos(np.arange(31, 0, -1, dtype=np.float64) * np.pi / 32.0)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert np.allclose(np.sort_complex(fr), expected.astype(np.complex128))


def test_weighted_path_graph_stays_on_weighted_route():
    Gf = fnx.path_graph(9)
    Gn = nx.path_graph(9)
    Gf[3][4]["weight"] = 2.0
    Gn[3][4]["weight"] = 2.0
    fr = fnx.adjacency_spectrum(Gf)
    nr = nx.adjacency_spectrum(Gn)
    unweighted = 2.0 * np.cos(np.arange(9, 0, -1, dtype=np.float64) * np.pi / 10.0)
    assert fr.dtype == nr.dtype == np.complex128
    assert _sorted_match(fr, nr)
    assert not np.allclose(np.sort_complex(fr), unweighted.astype(np.complex128))


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
