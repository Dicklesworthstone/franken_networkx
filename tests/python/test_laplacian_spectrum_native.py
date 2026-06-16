import numpy as np
import networkx as nx
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
