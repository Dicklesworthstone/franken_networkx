"""br-r37-c1-3u2ql: regression tests for spanner + k_edge_augmentation
guard ordering.

nx's @not_implemented_for decorators fire BEFORE the function body,
so wrong-type input with invalid stretch/k still raises
NetworkXNotImplemented. fnx previously validated stretch/k first
and surfaced ValueError on those edge cases.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("cls", [fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph])
@pytest.mark.parametrize("stretch", [0, -1, 1])
def test_spanner_wrong_type_raises_first(cls, stretch):
    g = cls()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.spanner(g, stretch)


@pytest.mark.parametrize("cls", [fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph])
@pytest.mark.parametrize("k", [0, -1, 1])
def test_k_edge_augmentation_wrong_type_raises_first(cls, k):
    g = cls()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.k_edge_augmentation(g, k)


def test_spanner_undirected_invalid_stretch_still_raises_value_error():
    g = fnx.path_graph(3)
    with pytest.raises(ValueError, match="stretch"):
        fnx.spanner(g, 0)


def test_k_edge_augmentation_undirected_invalid_k_still_raises_value_error():
    g = fnx.path_graph(3)
    with pytest.raises(ValueError, match="positive integer"):
        fnx.k_edge_augmentation(g, 0)


def test_spanner_undirected_valid_stretch_returns_subgraph():
    g = fnx.cycle_graph(5)
    sp = fnx.spanner(g, 2)
    assert sp.number_of_nodes() == 5
