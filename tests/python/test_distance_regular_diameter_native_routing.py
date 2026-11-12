"""Differential parity for ``franken_networkx.distance_regular.diameter``."""

from __future__ import annotations

import importlib

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import distance_regular as fnx_dr


@pytest.mark.parametrize("builder,expected", [
    (lambda lib: lib.cycle_graph(6), 3),
    (lambda lib: lib.path_graph(5), 4),
    (lambda lib: lib.complete_graph(5), 1),
    (lambda lib: lib.petersen_graph(), 2),
    (lambda lib: lib.complete_bipartite_graph(3, 3), 2),
])
def test_diameter_values_match_networkx(builder, expected):
    assert fnx_dr.diameter(builder(fnx)) == expected
    assert fnx_dr.diameter(builder(fnx)) == nx.diameter(builder(nx))


def test_diameter_routes_through_fnx_top_level(monkeypatch):
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.distance_regular"
    )
    graph = fnx.path_graph(4)
    sentinel = object()
    calls = []

    def fake_diameter(G, e=None, usebounds=False, weight=None):
        calls.append((G, e, usebounds, weight))
        return sentinel

    monkeypatch.setattr(fnx, "diameter", fake_diameter)

    assert fnx_dr.diameter(graph, usebounds=True, weight="weight") is sentinel
    assert via_algorithms.diameter(graph, e={"x": 1}) is sentinel
    assert calls == [
        (graph, None, True, "weight"),
        (graph, {"x": 1}, False, None),
    ]
