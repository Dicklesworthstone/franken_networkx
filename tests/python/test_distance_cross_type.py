"""br-r37-c1-eg0jk: regression — distance family accepts nx graph args."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_diameter_accepts_nx_graph():
    assert fnx.diameter(nx.path_graph(5)) == 4


@needs_nx
def test_radius_accepts_nx_graph():
    assert fnx.radius(nx.path_graph(5)) == 2


@needs_nx
def test_center_accepts_nx_graph():
    assert fnx.center(nx.path_graph(5)) == [2]


@needs_nx
def test_periphery_accepts_nx_graph():
    assert fnx.periphery(nx.path_graph(5)) == [0, 4]


@needs_nx
def test_eccentricity_accepts_nx_graph():
    assert fnx.eccentricity(nx.path_graph(5)) == {0: 4, 1: 3, 2: 2, 3: 3, 4: 4}


@needs_nx
def test_distance_family_no_regression_fnx_input():
    fg = fnx.path_graph(5)
    assert fnx.diameter(fg) == 4
    assert fnx.eccentricity(fg) == {0: 4, 1: 3, 2: 2, 3: 3, 4: 4}
