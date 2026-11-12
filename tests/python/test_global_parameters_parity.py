"""Parity coverage for global_parameters(b, c) intersection-array API.

Bead franken_networkx-ykcd: the public surface was exposing a graph-only
helper under the `global_parameters` name. Upstream NetworkX expects
`global_parameters(b, c)` over an intersection array and yields
(c_i, a_i, b_i) triples where `a_i = b[0] - b_i - c_i`.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_global_parameters_matches_networkx_bead_example():
    b = [3, 2, 1]
    c = [0, 1, 1, 3]
    assert list(fnx.global_parameters(b, c)) == list(nx.global_parameters(b, c))


def test_global_parameters_round_trip_with_intersection_array():
    """intersection_array(G) → global_parameters(b, c) matches nx on the
    dodecahedral distance-regular graph.
    """
    G = fnx.dodecahedral_graph()
    nG = nx.dodecahedral_graph()
    fb, fc = fnx.intersection_array(G)
    nb, nc = nx.intersection_array(nG)
    assert (fb, fc) == (nb, nc)
    assert list(fnx.global_parameters(fb, fc)) == list(nx.global_parameters(nb, nc))


def test_global_parameters_empty_intersection_array():
    assert list(fnx.global_parameters([0], [0])) == list(nx.global_parameters([0], [0]))
