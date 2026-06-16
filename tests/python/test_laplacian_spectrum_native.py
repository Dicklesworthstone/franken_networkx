import numpy as np
import networkx as nx
import pytest
import franken_networkx as fnx


def test_unweighted_complete_laplacian_closed_form_matches_nx_sorted_values():
    Gf = fnx.complete_graph(31)
    Gn = nx.complete_graph(31)
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    expected = np.empty(31, dtype=np.float64)
    expected[0] = 0.0
    expected[1:] = 31.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_weighted_complete_laplacian_stays_on_weighted_route():
    Gf = fnx.complete_graph(7)
    Gn = nx.complete_graph(7)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.laplacian_spectrum(Gf)
    nr = nx.laplacian_spectrum(Gn)
    unweighted = np.empty(7, dtype=np.float64)
    unweighted[0] = 0.0
    unweighted[1:] = 7.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert not np.allclose(np.sort(fr), unweighted)


def test_unweighted_complete_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.complete_graph(31)
    Gn = nx.complete_graph(31)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.empty(31, dtype=np.float64)
    expected[0] = 0.0
    expected[1:] = 31.0 / 30.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_single_node_complete_normalized_laplacian_matches_nx():
    Gf = fnx.complete_graph(1)
    Gn = nx.complete_graph(1)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert fr.dtype == np.float64
    assert np.allclose(fr, nr)


def test_weighted_complete_normalized_laplacian_stays_on_weighted_route():
    Gf = fnx.complete_graph(7)
    Gn = nx.complete_graph(7)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    unweighted = np.empty(7, dtype=np.float64)
    unweighted[0] = 0.0
    unweighted[1:] = 7.0 / 6.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert not np.allclose(np.sort(fr), unweighted)


def test_unweighted_edgeless_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.empty_graph(31)
    Gn = nx.empty_graph(31)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.zeros(31, dtype=np.float64)
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_zero_node_normalized_laplacian_keeps_nx_error():
    with pytest.raises(nx.NetworkXError):
        fnx.normalized_laplacian_spectrum(fnx.empty_graph(0))


def test_unweighted_star_normalized_laplacian_closed_form_matches_nx():
    Gf = fnx.star_graph(30)
    Gn = nx.star_graph(30)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    expected = np.ones(31, dtype=np.float64)
    expected[0] = 0.0
    expected[-1] = 2.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert np.allclose(fr, expected)


def test_weighted_star_normalized_laplacian_stays_on_weighted_route():
    Gf = fnx.star_graph(8)
    Gn = nx.star_graph(8)
    Gf[0][1]["weight"] = 2.5
    Gn[0][1]["weight"] = 2.5
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    assert (
        fnx._star_normalized_laplacian_spectrum_sorted_value_safe(Gf, "weight")
        is None
    )
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))


def test_path_normalized_laplacian_stays_on_matrix_route():
    Gf = fnx.path_graph(9)
    Gn = nx.path_graph(9)
    fr = fnx.normalized_laplacian_spectrum(Gf)
    nr = nx.normalized_laplacian_spectrum(Gn)
    star = np.ones(9, dtype=np.float64)
    star[0] = 0.0
    star[-1] = 2.0
    assert fr.dtype == np.float64
    assert np.allclose(np.sort(fr), np.sort(nr))
    assert not np.allclose(np.sort(fr), star)
