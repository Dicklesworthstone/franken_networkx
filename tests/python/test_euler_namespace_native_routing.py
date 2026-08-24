"""``franken_networkx.euler`` routes to fnx-native Eulerian functions.

``from networkx.algorithms.euler import *`` left is_eulerian,
eulerian_circuit, is_semieulerian, has_eulerian_path and eulerian_path
bound to networkx's implementations instead of fnx's native versions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from functools import lru_cache
from pathlib import Path

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import euler as fnx_euler

_NAMES = [
    "is_eulerian", "eulerian_circuit", "is_semieulerian", "has_eulerian_path",
    "eulerian_path",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_euler_surface"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", _NAMES)
def test_euler_fn_is_not_networkx_version(name):
    fn = getattr(fnx_euler, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


@pytest.mark.parametrize("name", _NAMES)
def test_euler_module_signatures_match_legacy_networkx(name):
    legacy = _legacy_networkx()

    assert str(inspect.signature(getattr(fnx_euler, name))) == str(
        inspect.signature(getattr(legacy.algorithms.euler, name))
    )


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


def test_euler_module_non_eulerian_error_matches_legacy_networkx():
    legacy = _legacy_networkx()
    graph = fnx.star_graph(3)

    with pytest.raises(Exception) as legacy_error:
        list(legacy.algorithms.euler.eulerian_circuit(legacy.star_graph(3)))
    with pytest.raises(type(legacy_error.value)) as fnx_error:
        list(fnx_euler.eulerian_circuit(graph))

    assert str(fnx_error.value) == str(legacy_error.value)
