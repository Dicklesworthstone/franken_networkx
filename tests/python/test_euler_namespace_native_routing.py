"""``franken_networkx.euler`` routes to fnx-native Eulerian functions.

``from networkx.algorithms.euler import *`` left is_eulerian,
eulerian_circuit, is_semieulerian, has_eulerian_path and eulerian_path
bound to networkx's implementations instead of fnx's native versions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import euler as fnx_euler

_NAMES = [
    "is_eulerian", "eulerian_circuit", "is_semieulerian", "has_eulerian_path",
    "eulerian_path",
]


@pytest.mark.parametrize("name", _NAMES)
def test_euler_fn_is_not_networkx_version(name):
    fn = getattr(fnx_euler, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


def test_euler_values_match_networkx():
    cyc = fnx.cycle_graph(5)
    ncyc = nx.cycle_graph(5)
    assert fnx_euler.is_eulerian(cyc) == nx.is_eulerian(ncyc)
    circuit = list(fnx_euler.eulerian_circuit(cyc))
    # Eulerian circuit uses every edge exactly once.
    assert len(circuit) == cyc.number_of_edges()
    assert {tuple(sorted(e[:2])) for e in circuit} == {
        tuple(sorted(e)) for e in cyc.edges()
    }
    path = fnx.path_graph(4)
    npath = nx.path_graph(4)
    assert fnx_euler.has_eulerian_path(path) == nx.has_eulerian_path(npath)
    assert fnx_euler.is_semieulerian(path) == nx.is_semieulerian(npath)
